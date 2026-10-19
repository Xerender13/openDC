"""Lossless table editing, backups, game artwork and the local GM connection.

Row positions and identifiers stay fixed: the wire protocol uses table row indices.
Only server copies are edited. Client archives are read solely for artwork.
"""
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import tempfile
import zipfile
from datetime import datetime

from dcemu.native.data import read_tdf, read_xlt
from tools.eu_client import tdf_set
from .translations import english

ROOT = Path(__file__).resolve().parents[2]

# Names below reflect columns actually read by native/data.py and game handlers.
SCHEMAS = {
 'ItemClient.tdf': {0:'Part kind',1:'Set ID',2:'Item ID',3:'Icon key',4:'Name',5:'Description',6:'Grade',7:'Required level',8:'Required V grade',9:'Base stat',12:'Buy price (Mito)',13:'Sell price (Mito)',15:'In shop',17:'Tradeable'},
 'UseItemClient.tdf': {0:'Item ID',1:'Use effect',2:'Name',3:'Icon / reward group',4:'Extra parameter',5:'Stack limit',6:'Description',7:'Buy price (Mito)',8:'Sell price (Mito)',9:'Effect value',10:'Duration (seconds)',13:'In shop',15:'Tradeable'},
 'ArbeitClient.tdf': {0:'Job ID',3:'Giver post',4:'Title',5:'Description',28:'Gold EXP',29:'Gold Mito',30:'Gold time (seconds)',31:'Silver EXP',32:'Silver Mito',33:'Silver time (seconds)',34:'Bronze EXP',35:'Bronze Mito',36:'Bronze time (seconds)',37:'No medal EXP',38:'No medal Mito'},
 'Instant_Client.tdf': {0:'Category',1:'Minimum level',2:'Maximum level',5:'Title',6:'Description',8:'Time limit',10:'Mission type',13:'EXP reward',14:'Mito reward',16:'Patrol posts',17:'Giver post'},
 'QuestClient.tdf': {0:'Quest ID',1:'Quest number',2:'Quest kind',4:'Previous quest',6:'Minimum level',7:'Maximum level (repeatable)',9:'Giver post',10:'Title',11:'Start dialogue',13:'Finish dialogue',14:'Objective',75:'EXP reward',76:'Mito reward'},
}
XLT_HEADER = {'VehicleList.xlt':3,'VisualItem.xlt':5,'VehicleDisplay.xlt':3}
IDENTIFIERS = {'ItemClient.tdf':{2},'UseItemClient.tdf':{0},'QuestClient.tdf':{0,1},'ArbeitClient.tdf':{0},'VehicleList.xlt':{0,9},'VehicleUpgrade.xlt':{0,1,19},'VisualItem.xlt':{3,4},'VShopItem.xlt':{0,2,3}}
DESCRIPTIONS = {
 'ItemClient.tdf':'Car parts, option parts and docking parts. Prices, requirements, stats and shop flags.',
 'UseItemClient.tdf':'Consumables: effect, duration, stacking, prices and the tooltip shown in game.',
 'VisualItem.xlt':'Drift items: names, effects, categories and which car models can equip them.',
 'VShopItem.xlt':'Drift shop: tooltips, Mito / G Coin / mileage prices, durations and bonuses.',
 'VehicleList.xlt':'Car models, names, base attributes, dimensions, slots and driving properties.',
 'VehicleUpgrade.xlt':'Each car at each V grade: stats, buy / sell / upgrade costs, fuel and requirements.',
 'ArbeitClient.tdf':'Delivery jobs: destinations, medal times, EXP and Mito. Item prizes are in delivery_rewards.txt.',
 'Instant_Client.tdf':'Solo / party patrol, city missions and Mission Battles: requirements, objectives, EXP and Mito.',
 'QuestClient.tdf':'Main and repeatable quests: dialogue, objectives, prerequisites, EXP and Mito.',
 'RewardGroup.xlt':'Item reward pools used by patrol, lucky bags, events and other game modes.',
 'HuvTable.tdf':'HUV chase attributes and EXP / Mito rewards by level.',
 'PVPTrackInfo.xlt':'Battle Zone and Lap Time tracks and race parameters.',
 'MotherQuest.xlt':'Mother quests: main mission progression and rewards.',
 'License.xlt':'License tests and their requirements.',
 'pvpexpbase.txt':'Battle race EXP base by player level.', 'pvpexprate.txt':'Battle race EXP multipliers.',
 'pvpmoneybase.txt':'Battle race Mito base by player level.', 'pvpmoneyrate.txt':'Battle race Mito multipliers.',
 'gate_rewards.txt':'Solo race gate power-up chances by player count, position and clean driving.',
 'team_gate_rewards.txt':'Team race gate power-up probabilities.',
 'delivery_rewards.txt':'Delivery item prizes by job ID and medal. Add rows for multiple item prizes.',
 'patrol_rewards.txt':'Patrol item prizes by table row. Add rows for multiple item prizes.',
 'laptimeinfo.txt':'Lap Time limits and reward settings.', 'realmatchtable.txt':'Real Match weekly opening schedule.',
 'comboexp.txt':'Combo driving EXP rewards.', 'rushtimetable.txt':'Rush Time schedule.',
 'mode_tuning.txt':'Undercity fees, stage EXP / Mito and timers; Rush Time winner prizes; Virtual HUV item prizes; chase timers and daily mission tokens. Index meanings appear in each row.',
}


def atomic_save(path, original, replacement, backup_root=ROOT/'editor_backups'):
    """Reject stale edits; retain exact original bytes before atomic replacement."""
    path = Path(path)
    if path.read_bytes() != original:
        raise ValueError('File changed since it was opened. Reload before saving.')
    if original == replacement:
        return None
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        relative = Path(path.name)
    backup = Path(backup_root)/datetime.now().strftime('%Y%m%d-%H%M%S-%f')/relative
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(original)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(replacement)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, path.stat().st_mode)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return backup


class Document:
    def __init__(self,path):
        self.path=Path(path)
        self.original=self.path.read_bytes()
        self.changes={}
        self.is_tdf=self.path.suffix.lower()=='.tdf'
        self.is_text=self.path.suffix.lower() in ('.txt','.ini')
        self.hints={}
        if self.is_text:
            self._text_load()
            return
        self.rows=read_tdf(self.path) if self.is_tdf else read_xlt(self.path)
        self.start=0
        self.headers=[]
        if not self.is_tdf:
            h=XLT_HEADER.get(self.path.name,2)
            # Several auxiliary tables have their header at a different offset.
            if h >= len(self.rows):
                h=0
            self.headers=self.rows[h]
            self.start=h+1
        self.schema=SCHEMAS.get(self.path.name,{})

    def _text_load(self):
        self.encoding='utf-8-sig'
        try:
            self.text=self.original.decode(self.encoding)
        except UnicodeDecodeError:
            self.encoding='cp949'  # Original 2008 Korean server files, e.g. laptimeinfo.txt.
            self.text=self.original.decode(self.encoding)
        self.lines=self.text.splitlines(keepends=True)
        self.rows=[]
        self.line_numbers=[]
        section=''
        comments=[]
        self.headers=['Section','Setting','Value'] if self.path.suffix=='.ini' else []
        self.schema={}
        self.start=0
        for i,line in enumerate(self.lines):
            s=line.strip()
            if not s:
                continue
            if s.startswith(('#',';')):
                comments.append(s[1:].strip())
                if '\t' in s and self.path.suffix=='.txt':
                    self.headers=s[1:].strip().split('\t')
                continue
            if s.startswith('['):
                section=s.split(']',1)[0][1:]
                continue
            if self.path.suffix=='.ini':
                if '=' not in line:
                    continue
                key,value=line.split('=',1)
                value=re.split(r'\s+[;#]',value,maxsplit=1)[0].strip()
                if section in ('database','services','emulator','native'):
                    comments=[]
                    continue
                self.rows.append([section,key.strip(),value])
            else:
                value=line.split('#',1)[0].strip()
                self.rows.append(value.split('\t') if '\t' in value else value.split())
            self.line_numbers.append(i)
            self.hints[len(self.rows)-1]='\n'.join(comments)
            comments=[]

    def label(self,col):
        s=self.schema.get(col)
        if not s and col<len(self.headers):
            s=self.headers[col].strip()
        return english(s) if s else f'Column {col} (raw parameter)'

    def value(self,row,col):
        return self.changes.get((row,col),self.rows[row][col])

    def display_value(self,row,col,original=False):
        value=self.value(row,col)
        return value if original else english(value)

    def set_display(self,row,col,value,original=False):
        # Leaving an English display value untouched must never rewrite its Korean source.
        if value==self.display_value(row,col,original):
            return
        self.set(row,col,value)

    def matches(self,row,query):
        raw='\t'.join(self.rows[row])
        return query in raw.lower() or query in '\t'.join(english(cell) for cell in self.rows[row]).lower()

    def set(self,row,col,value):
        if self.path.name=='mode_tuning.txt' and col!=3:
            raise ValueError('Only the value column is editable; gameplay keys and descriptions are fixed.')
        if self.is_text and self.path.suffix=='.ini' and col<2:
            raise ValueError('Section and setting names are fixed.')
        if row < self.start or col in IDENTIFIERS.get(self.path.name,set()):
            raise ValueError('This identifier is fixed because the client and server reference it.')
        old=self.rows[row][col]
        if '\0' in value or (not self.is_tdf and ('\t' in value or '\n' in value or '\r' in value)) or (self.is_text and ('#' in value or ';' in value)):
            raise ValueError('This cell cannot contain NUL or table separators.')
        if re.fullmatch(r'[+-]?\d+(?:\.\d+)?',old.strip()):
            try:
                number=float(value)
                if not math.isfinite(number) or (re.fullmatch(r'[+-]?\d+',old.strip()) and not re.fullmatch(r'[+-]?\d+',value.strip())):
                    raise ValueError()
            except ValueError:
                raise ValueError('Enter a finite number of the same type as the original.') from None
        if old.lower() in ('true','false') and value.lower() not in ('true','false'):
            raise ValueError('Enter True or False.')
        if value==old:
            self.changes.pop((row,col),None)
        else:
            self.changes[row,col]=value

    def encoded(self):
        if self.is_tdf:
            return tdf_set(self.original,self.changes)
        if self.is_text:
            lines=list(self.lines)
            for row in {r for r,c in self.changes}:
                at=self.line_numbers[row]
                line=lines[at]
                ending='\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
                if self.path.suffix=='.ini':
                    prefix=line[:line.index('=')+1]
                    match=re.search(r'\s+[;#].*',line.rstrip('\r\n'))
                    tail=match.group(0) if match else ''
                    lines[at]=prefix+' '+self.value(row,2)+tail+ending
                else:
                    comment='#'+line.split('#',1)[1].rstrip('\r\n') if '#' in line else ''
                    lines[at]='\t'.join(self.value(row,c) for c in range(len(self.rows[row])))+(' '+comment if comment else '')+ending
            encoding='utf-8' if self.encoding=='utf-8-sig' and not self.original.startswith(b'\xef\xbb\xbf') else self.encoding
            return ''.join(lines).encode(encoding)
        # Preserve BOM, line endings, and all untouched lines/cells verbatim.
        text=self.original.decode('utf-16-le')
        bom='\ufeff' if text.startswith('\ufeff') else ''
        lines=text.lstrip('\ufeff').split('\r\n')
        for row,col in self.changes:
            cells=lines[row].split('\t')
            cells[col]=self.changes[row,col]
            lines[row]='\t'.join(cells)
        return (bom+'\r\n'.join(lines)).encode('utf-16-le')

    def duplicate(self,row):
        if self.path.name not in ('delivery_rewards.txt','patrol_rewards.txt'):
            raise ValueError('Only item reward lists support adding rows.')
        cells=[self.value(row,c) for c in range(len(self.rows[row]))]
        if self.lines and not self.lines[-1].endswith(('\r','\n')):
            self.lines[-1]+='\n'
        self.line_numbers.append(len(self.lines))
        self.lines.append('\t'.join(cells)+'\n')
        self.rows.append(cells)
        self.changes[len(self.rows)-1,0]=cells[0]

    def save(self,backup_root=ROOT/'editor_backups'):
        data=self.encoded()
        if self.path.name=='mode_tuning.txt':
            from dcemu.native.mode_tuning import parse
            defaults={(r[0],r[1],tuple(r[2].split('.')) if r[2]!='-' else ()): (int(r[3]) if re.fullmatch(r'\d+',r[3]) else float(r[3]) if re.fullmatch(r'\d+\.\d+',r[3]) else r[3]) for r in self.rows}
            parse(data.decode(self.encoding),defaults)
        backup=atomic_save(self.path,self.original,data,backup_root)
        self.__init__(self.path)
        return backup

    def title(self,i,original=False):
        row=self.rows[i]
        if self.is_text:
            text=f'[{row[0]}] {row[1]}' if self.path.suffix=='.ini' else ' · '.join(row[:3])
            return text if original else english(text)
        namecol={'ItemClient.tdf':4,'UseItemClient.tdf':2,'ArbeitClient.tdf':4,'Instant_Client.tdf':5,'QuestClient.tdf':10,'VehicleList.xlt':6,'VehicleUpgrade.xlt':4,'VisualItem.xlt':5,'VShopItem.xlt':4}.get(self.path.name,0)
        text=row[namecol].strip() if namecol<len(row) else str(i)
        return text if original else english(text)

    def item_id(self,i):
        col={'ItemClient.tdf':2,'UseItemClient.tdf':0,'VisualItem.xlt':3,'VShopItem.xlt':3}.get(self.path.name)
        return self.rows[i][col] if col is not None else ''


def sources(root=ROOT):
    root=Path(root)
    result={'Items':[], 'Cars':[], 'Modes & rewards':[]}
    for sub in ['Init','tables']:
        for p in sorted((root/'server_data'/sub).glob('*')):
            if p.suffix.lower() not in ('.xlt','.tdf','.txt','.ini'):
                continue
            group='Items' if p.name in ('ItemClient.tdf','UseItemClient.tdf','VisualItem.xlt','VShopItem.xlt') else 'Cars' if p.name.startswith(('Vehicle','AICar','TrafficFlow')) else 'Modes & rewards'
            result[group].append(p)
    result['Modes & rewards'] += sorted((root/'server_data').glob('*.txt'))
    # Server addresses and GM IDs belong to deployment settings, not game modes.
    result['Modes & rewards']=[p for p in result['Modes & rewards'] if p.name not in ('adminlist.txt','serverlist.txt')]
    result['Modes & rewards'].insert(0,root/'emulator.ini')
    return result


class Artwork:
    """Resolve named game.nui pictures into DDS pieces, with catalog atlas fallback."""
    def __init__(self,client,catalog=None):
        from tools import agt
        from tools.ui_texture import entries
        self.images={}
        self.pictures={}
        self.catalog={}
        self.atlases={}
        self.cache={}
        client=Path(client)
        nui=client/'Data_US/gameui/game.nui'
        if nui.exists():
            for tag in re.findall(r'<INFO\s+[^>]+>',nui.read_text(encoding='latin-1')):
                attrs=dict(re.findall(r'(\w+)="([^"]*)"',tag))
                if 'NM' in attrs and 'I1_1' in attrs:
                    self.pictures[attrs['NM'].lower()]=attrs['I1_1'].lower()
        pack=client/'Data_US/gameui/uitex.agt'
        if pack.exists():
            raw,idx=agt.index(pack)
            for e in idx:
                if e[0].lower().endswith('.ntx'):
                    blob=agt.extract(raw,e)
                    for name,off,size in entries(blob):
                        self.images[name.lower()]=blob[off+72:off+72+size]
        if catalog and Path(catalog).exists():
            with zipfile.ZipFile(catalog) as z:
                meta=json.loads(z.read('items.json'))
                self.cell,self.cols=meta['cell'],meta['cols']
                self.catalog={r['id']:r for r in meta['items']}
                self.atlases={k:z.read('icons-'+k+'.webp') for k in ['parts','use','visual']}

    def get(self,key='',item_id=''):
        from PIL import Image
        token=(key,item_id)
        if token in self.cache:
            return self.cache[token]
        name=self.pictures.get(key.lower(),key.lower())
        img=None
        if name in self.images:
            img=Image.open(io.BytesIO(self.images[name])).convert('RGBA')
        elif item_id in self.catalog:
            icon=self.catalog[item_id].get('icon')
            if icon:
                sec,n=icon
                atlas=Image.open(io.BytesIO(self.atlases[sec]))
                x,y=n%self.cols*self.cell,n//self.cols*self.cell
                img=atlas.crop((x,y,x+self.cell,y+self.cell)).convert('RGBA')
        self.cache[token]=img
        return img


def gm(command,config=ROOT/'emulator.ini'):
    from dcemu.__main__ import load_config
    if not command.strip() or '\n' in command or '\r' in command:
        raise ValueError('Enter one GM command.')
    port=load_config(config).getint('emulator','control_port')
    try:
        sock=socket.create_connection(('127.0.0.1',port),timeout=8)
    except ConnectionRefusedError:
        if os.name!='nt':
            raise ConnectionError('Emulator GM port is unavailable. Start the emulator first.') from None
        # Windows runs the emulator in Docker. Its GM port stays loopback-only INSIDE
        # the container: use stdin rather than publishing this unauthenticated port.
        import subprocess
        script=("import socket,sys; from dcemu.__main__ import load_config; "
                "s=socket.create_connection(('127.0.0.1',int(load_config('emulator.ini')['emulator']['control_port'])),8); "
                "s.sendall(sys.stdin.buffer.read()); "
                "out=s.makefile('rb').read(); sys.stdout.buffer.write(out)")
        result=subprocess.run(['docker','compose','exec','-T','emulator','python','-c',script],
                              input=(command+'\n').encode(),cwd=ROOT,capture_output=True,timeout=20)
        if result.returncode:
            raise ConnectionError('Docker emulator GM connection failed: '+result.stderr.decode('utf-8','replace'))
        return result.stdout.decode('utf-8','replace').strip()
    with sock:
        sock.sendall((command+'\n').encode())
        chunks=[]
        while data:=sock.recv(8192):
            chunks.append(data)
    return b''.join(chunks).decode('utf-8','replace').strip()
