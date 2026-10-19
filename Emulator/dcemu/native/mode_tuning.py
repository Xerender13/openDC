"""Editable gameplay constants, restricted to an explicit list of reward/timer fields.

mode_tuning.txt preserves all existing defaults. Apply once during startup, before any
players connect. Protocol sizes, IDs and session state cannot be overridden here.
"""
import importlib
import math
from pathlib import Path

FIELDS = {
 'undercity': {
  'FEES':'Entry fee in Mito; city 1 Moon Palace, 2 Koinonia, 3 Cras, 4 Oros',
  'AGREE_SECONDS':'Seconds for party members to agree to entry',
  'PATROL_REWARD':'Per city: 0 EXP per HUB, 1 Mito per HUB, 2 Mito per red HUB',
  'MAIN_HUB_EXP':'Main HUB completion EXP by city',
  'MIDDLE_REWARD':'Per city: 0 EXP per caught HUV, 1 Mito per caught HUV',
  'BOSS_EXP':'Per city boss EXP coefficients; see game/undercity.py reward formula',
  'BOSS_SHARE':'Boss EXP sharing ratio by party size',
  'WAVE_SECONDS':'Seconds before the next HUV wave, by wave number',
  'BOSS_SECONDS':'Boss chase time in seconds',
 },
 'rush': {
  'CITY_MONEY':'Winner Mito prize by city',
  'WIN_ITEMS':'Winner item prizes: each pair is item ID then count',
 },
 'vchase': {
  'CITY_ITEMS':'Winner enhancer by city: item ID then count',
  'SUGGEST_SECONDS':'Party registration agreement timeout in seconds',
 },
 'chase': {
  'TIME_TABLE':'HUV chase time table; rows are level bands and columns are stage indices',
 },
 'daymission': {
  'TOKEN':'Daily mission reward token item ID',
 },
}


def leaves(value,path=()):
    if isinstance(value,dict):
        for key,child in value.items():
            yield from leaves(child,path+(str(key),))
    elif isinstance(value,(list,tuple)):
        for i,child in enumerate(value):
            yield from leaves(child,path+(str(i),))
    elif isinstance(value,(int,float,str)) and not isinstance(value,bool):
        yield path,value


def replace(value,path,new):
    if not path: return new
    key=path[0]
    if isinstance(value,dict):
        out=dict(value)
        k=next(k for k in out if str(k)==key)
        out[k]=replace(out[k],path[1:],new)
        return out
    out=list(value)
    k=int(key)
    out[k]=replace(out[k],path[1:],new)
    return tuple(out) if isinstance(value,tuple) else out


def parse(text,defaults):
    """Validate every override before returning any modifications."""
    changes={}
    for i,line in enumerate(text.splitlines(),1):
        line=line.split('#',1)[0].strip()
        if not line: continue
        parts=line.split('\t')
        if len(parts)<4:
            raise ValueError(f'mode_tuning line {i}: expected mode, field, index, value')
        module,field,index,raw=parts[:4]
        path=tuple(index.split('.')) if index!='-' else ()
        key=(module,field,path)
        if key not in defaults:
            raise ValueError(f'mode_tuning line {i}: unknown gameplay parameter {key}')
        old=defaults[key]
        try:
            if isinstance(old,str):
                if not raw or any(c.isspace() for c in raw): raise ValueError()
                new=raw
            elif isinstance(old,int):
                new=int(raw)
                if not 0<=new<=2147483647: raise ValueError()
            else:
                new=float(raw)
                if not math.isfinite(new) or not 0<=new<=2147483647: raise ValueError()
        except ValueError:
            raise ValueError(f'mode_tuning line {i}: invalid value {raw!r}') from None
        if ('SECONDS' in field or field=='TIME_TABLE') and float(new)<=0:
            raise ValueError(f'mode_tuning line {i}: duration must be positive')
        if field=='BOSS_SHARE' and not 0<=new<=1:
            raise ValueError(f'mode_tuning line {i}: sharing ratio must be 0–1')
        if key in changes:
            raise ValueError(f'mode_tuning line {i}: duplicate parameter')
        changes[key]=new
    return changes


def apply(root):
    path=Path(root)/'mode_tuning.txt'
    if not path.exists(): return
    modules={name:importlib.import_module('.game.'+name,__package__) for name in FIELDS}
    defaults={(name,field,p):v for name,fields in FIELDS.items() for field in fields
              for p,v in leaves(getattr(modules[name],field))}
    changes=parse(path.read_text(encoding='utf-8'),defaults)
    for (name,field,p),value in changes.items():
        module=modules[name]
        setattr(module,field,replace(getattr(module,field),p,value))
