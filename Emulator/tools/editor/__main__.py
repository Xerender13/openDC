"""openDC desktop workshop: python -m tools.editor [--client PATH]."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .data import ROOT, Artwork, DESCRIPTIONS, Document, IDENTIFIERS, gm, sources
from .translations import english


class ScrollFrame(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        self.canvas=tk.Canvas(self,highlightthickness=0,bg='#202831')
        bar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.body=ttk.Frame(self.canvas)
        self.window=self.canvas.create_window((0,0),window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.window,width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side='left',fill='both',expand=True)
        bar.pack(side='right',fill='y')
        self.canvas.bind('<Button-4>',lambda e:self.canvas.yview_scroll(-3,'units'))
        self.canvas.bind('<Button-5>',lambda e:self.canvas.yview_scroll(3,'units'))
        self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units'))


class GiftBoxDialog:
    """A new gift box (tools/giftbox.py): a car and/or items, each line with its own chance. It writes the server
    tables and both clients' packs (the box is a new item row), so the clients and the emulator need a restart."""
    AMOUNT={'car':'Grade (V)','item':'Count','drift':'Days (0 = permanent)','mito':'Mito','exp':'EXP'}

    def __init__(self,app):
        from tools import giftbox
        self.app,self.gb=app,giftbox
        self.cars={f'{name}  ·  {key}  ·  #{uid}':(uid,grades) for uid,name,key,grades in giftbox.cars()}
        known=giftbox.items()
        self.choices={'car':list(self.cars),
                      'item':[f'{english(n) or n}  ·  {i}' for i,n in sorted(known['item'].items(),key=lambda x:english(x[1]).lower())],
                      'drift':[f'{english(n) or n}  ·  {i}' for i,n in sorted(known['drift'].items(),key=lambda x:english(x[1]).lower())],
                      'mito':[],'exp':[]}
        self.lines=[]
        w=self.win=tk.Toplevel(app.root)
        w.title('New gift box')
        w.geometry('860x640')
        w.configure(bg='#202831')
        w.transient(app.root)
        form=ttk.Frame(w,padding=14)
        form.pack(fill='x')
        self.slug,self.name,self.label,self.price=tk.StringVar(),tk.StringVar(),tk.StringVar(),tk.StringVar(value='0')
        for r,(text,var,hint) in enumerate([('ID',self.slug,'item id = giftbox_<ID> (letters, digits, _)'),
                                            ('Name',self.name,'shown in the inventory'),
                                            ('Icon label',self.label,'written on the gift box picture (16 letters)'),
                                            ('Shop price (Mito)',self.price,'0 = not sold; sell price = a fifth')]):
            ttk.Label(form,text=text).grid(row=r,column=0,sticky='w',pady=3)
            ttk.Entry(form,textvariable=var,width=40).grid(row=r,column=1,sticky='w',padx=8)
            ttk.Label(form,text=hint,foreground='#8fa3b3').grid(row=r,column=2,sticky='w')
        add=ttk.LabelFrame(w,text='  Add a line  ',padding=10)
        add.pack(fill='x',padx=14)
        self.kind,self.query,self.pick,self.amount,self.chance=(tk.StringVar(value='item'),tk.StringVar(),tk.StringVar(),
                                                                 tk.StringVar(value='1'),tk.StringVar(value='100'))
        ttk.Label(add,text='Kind').grid(row=0,column=0,sticky='w')
        kind=ttk.Combobox(add,textvariable=self.kind,values=list(self.AMOUNT),state='readonly',width=8)
        kind.grid(row=1,column=0,sticky='w',padx=(0,8))
        kind.bind('<<ComboboxSelected>>',lambda e:self.kind_changed())
        ttk.Label(add,text='Search').grid(row=0,column=1,sticky='w')
        ttk.Entry(add,textvariable=self.query,width=18).grid(row=1,column=1,sticky='w',padx=(0,8))
        self.query.trace_add('write',lambda *_:self.filter())
        ttk.Label(add,text='Car / item').grid(row=0,column=2,sticky='w')
        self.picker=ttk.Combobox(add,textvariable=self.pick,width=46)
        self.picker.grid(row=1,column=2,sticky='w',padx=(0,8))
        self.amount_label=ttk.Label(add,text=self.AMOUNT['item'])
        self.amount_label.grid(row=0,column=3,sticky='w')
        ttk.Entry(add,textvariable=self.amount,width=10).grid(row=1,column=3,sticky='w',padx=(0,8))
        ttk.Label(add,text='Chance %').grid(row=0,column=4,sticky='w')
        ttk.Entry(add,textvariable=self.chance,width=7).grid(row=1,column=4,sticky='w',padx=(0,8))
        ttk.Button(add,text='Add',command=self.add_line).grid(row=1,column=5)
        ttk.Label(w,text='Each line is rolled on its own: 100 % always comes, 25 % comes one time in four. A car comes with its key '
                       'and full Mittron (the player needs garage space).',wraplength=820,padding=(14,8)).pack(anchor='w')
        self.tree=ttk.Treeview(w,columns=('kind','what','amount','chance'),show='headings',height=9)
        for col,text,width in (('kind','Kind',70),('what','Car / item',420),('amount','Amount',150),('chance','Chance',80)):
            self.tree.heading(col,text=text)
            self.tree.column(col,width=width,stretch=col=='what')
        self.tree.pack(fill='both',expand=True,padx=14)
        bar=ttk.Frame(w,padding=14)
        bar.pack(fill='x')
        ttk.Button(bar,text='Remove line',command=self.remove_line).pack(side='left')
        ttk.Button(bar,text='Create gift box',command=self.create).pack(side='right')
        ttk.Button(bar,text='Close',command=w.destroy).pack(side='right',padx=8)
        self.kind_changed()

    def kind_changed(self):
        kind=self.kind.get()
        self.amount_label.configure(text=self.AMOUNT[kind])
        self.amount.set({'car':'1','item':'1','drift':'0','mito':'10000','exp':'1000'}[kind])
        self.picker.configure(state='normal' if self.choices[kind] else 'disabled')
        self.pick.set('')
        self.filter()

    def filter(self):
        words=self.query.get().lower().split()
        values=[v for v in self.choices[self.kind.get()] if all(x in v.lower() for x in words)]
        self.picker.configure(values=values[:400])
        if len(values)==1: self.pick.set(values[0])

    def add_line(self):
        kind,pick=self.kind.get(),self.pick.get()
        try:
            amount,chance=int(self.amount.get()),float(self.chance.get())
        except ValueError:
            messagebox.showerror('Gift box','Amount must be a whole number and chance a number.',parent=self.win); return
        if kind!='mito' and kind!='exp' and pick not in self.choices[kind]:
            messagebox.showerror('Gift box','Pick a car or item from the list (type in Search to narrow it).',parent=self.win); return
        if kind=='car':
            uid,grades=self.cars[pick]
            line=dict(kind=kind,id=uid,grade=amount,chance=chance)
            shown=f'V{amount}'
        elif kind in ('item','drift'):
            line=dict(kind=kind,id=pick.rsplit('  ·  ',1)[1],count=amount if kind=='item' else 1,days=amount if kind=='drift' else 0,chance=chance)
            shown=(f'{amount} days' if amount else 'permanent') if kind=='drift' else f'x {amount}'
        else:
            line=dict(kind=kind,count=amount,chance=chance)
            pick,shown=kind.capitalize(),f'{amount:,}'
        try:
            self.gb.check([line])
        except ValueError as e:
            messagebox.showerror('Gift box',str(e).replace('line 1: ',''),parent=self.win); return
        self.lines.append(line)
        self.tree.insert('','end',iid=str(len(self.lines)-1),values=(kind,pick,shown,f'{chance:g} %'))
        if kind=='car' and not self.name.get():
            name=pick.split('  ·  ')[0]
            self.name.set(f'{name} GiftBox（V{amount}）')
            self.label.set(self.label.get() or name)
            self.slug.set(self.slug.get() or f'{pick.split("  ·  ")[1]}_v{amount}')

    def remove_line(self):
        for iid in self.tree.selection():
            self.lines[int(iid)]=None
            self.tree.delete(iid)

    def create(self):
        lines=[l for l in self.lines if l]
        try:
            price=int(self.price.get() or 0)
        except ValueError:
            messagebox.showerror('Gift box','The price must be a whole number.',parent=self.win); return
        if not messagebox.askyesno('Create gift box','This adds a new item to the server tables and to both clients (US and EU packs; '
                                   'the originals stay in client_backup). Restart the emulator and the clients afterwards. Create it?',parent=self.win):
            return
        out=[]
        slug,name,label=self.slug.get().strip(),self.name.get().strip(),self.label.get().strip()
        def done(box):
            self.app.status.set(f'{box} created · restart the emulator and the clients')
            messagebox.showinfo('Gift box','\n'.join(out[-1:])+'\n\nGive it with GM: item NAME '+box,parent=self.win)
            self.win.destroy()
        self.app.async_job(lambda:self.gb.make(slug,name,label,lines,price,log=out.append),done)


class Workshop:
    def __init__(self,root,client):
        self.root=root
        self.client=client
        self.document=None
        self.selected=None
        self.fields=[]
        self.loading=False
        self.original_text=tk.BooleanVar(value=False)
        self.executor=ThreadPoolExecutor(max_workers=1)
        self.art=None
        self.icon=None
        self.history=[]
        self.history_pos=0
        root.title('openDC · Server Workshop')
        root.geometry('1240x820')
        root.minsize(900,600)
        self.style()
        top=ttk.Frame(root,padding=(20,16))
        top.pack(fill='x')
        ttk.Label(top,text='openDC  /  SERVER WORKSHOP',font=('DejaVu Sans',18,'bold')).pack(side='left')
        ttk.Button(top,text='Restart emulator',command=self.restart).pack(side='right')
        ttk.Button(top,text='Help',command=self.help).pack(side='right',padx=8)
        self.status=tk.StringVar(value='Loading game artwork…')
        ttk.Label(root,textvariable=self.status,padding=(20,8)).pack(side='bottom',fill='x')
        self.tabs=ttk.Notebook(root)
        self.tabs.pack(fill='both',expand=True,padx=16)
        self.source_map=sources()
        for group in self.source_map:
            tab=ttk.Frame(self.tabs)
            self.tabs.add(tab,text='  '+group+'  ')
            self.build_editor(tab,group)
        self.console_tab=ttk.Frame(self.tabs,padding=16)
        self.tabs.add(self.console_tab,text='  GM Console  ')
        self.build_console()
        self.account_tab=ttk.Frame(self.tabs,padding=16)
        self.tabs.add(self.account_tab,text='  Accounts  ')
        self.build_accounts()
        self.tabs.bind('<<NotebookTabChanged>>',self.tab_change)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.bind('<Control-s>',lambda e:self.save())
        self.jobs=[]
        self.async_job(lambda:Artwork(client,ROOT.parent/'Drift City Item Catalog.zip'),self.art_loaded)
        self.root.after(30,self.poll)
        self.open_source('Items')

    def style(self):
        s=ttk.Style()
        s.theme_use('clam')
        s.configure('.',background='#202831',foreground='#e4edf4',font=('DejaVu Sans',10),fieldbackground='#131a21')
        s.configure('TNotebook',background='#131a21',borderwidth=0)
        s.configure('TNotebook.Tab',padding=(14,10),background='#28343f')
        s.map('TNotebook.Tab',background=[('selected','#087f8c')])
        s.configure('TButton',padding=(10,7),background='#344653')
        s.map('TButton',background=[('active','#087f8c')])
        s.configure('Treeview',background='#131a21',fieldbackground='#131a21',rowheight=32)
        s.map('Treeview',background=[('selected','#087f8c')])
        s.configure('TEntry',padding=5)
        self.root.configure(bg='#131a21')

    def async_job(self,work,done):
        self.jobs.append((self.executor.submit(work),done))

    def poll(self):
        for job,done in list(self.jobs):
            if job.done():
                self.jobs.remove((job,done))
                try:
                    result=job.result()
                    done(result)
                except Exception as e:
                    self.status.set(str(e))
                    messagebox.showerror('Workshop',str(e),parent=self.root)
        self.root.after(50,self.poll)

    def art_loaded(self,art):
        self.art=art
        self.status.set(f'Ready · {len(art.images):,} game pictures · edits affect server data; restart to apply cached tables')
        if self.selected is not None:
            self.preview(self.selected)

    def build_editor(self,tab,group):
        toolbar=ttk.Frame(tab,padding=10)
        toolbar.pack(fill='x')
        src=tk.StringVar()
        names=[p.name for p in self.source_map[group]]
        select=ttk.Combobox(toolbar,textvariable=src,values=names,state='readonly',width=32)
        select.pack(side='left')
        if names: src.set(names[0])
        select.bind('<<ComboboxSelected>>',lambda e:self.open_source(group))
        ttk.Button(toolbar,text='Save changes  Ctrl+S',command=self.save).pack(side='right')
        ttk.Button(toolbar,text='Reload',command=lambda:self.open_source(group)).pack(side='right',padx=8)
        if group=='Modes & rewards':
            ttk.Button(toolbar,text='Duplicate reward row',command=self.duplicate_reward).pack(side='right',padx=4)
        if group in ('Items','Cars'):
            ttk.Button(toolbar,text='New gift box…',command=lambda:GiftBoxDialog(self)).pack(side='right',padx=4)
        query=tk.StringVar()
        searchbar=ttk.Frame(tab,padding=(10,0,10,8))
        searchbar.pack(fill='x')
        ttk.Label(searchbar,text='Search').pack(side='left',padx=(0,8))
        ttk.Entry(searchbar,textvariable=query,width=32).pack(side='left',fill='x',expand=True)
        query.trace_add('write',lambda *_:self.filter(group))
        ttk.Checkbutton(searchbar,text='Original table text',variable=self.original_text,command=self.text_view).pack(side='left',padx=12)
        body=ttk.Panedwindow(tab,orient='horizontal')
        body.pack(fill='both',expand=True)
        left=ttk.Frame(body)
        tree=ttk.Treeview(left,columns=('row','name'),show='headings',selectmode='browse')
        tree.heading('row',text='Row')
        tree.heading('name',text='Name / identifier')
        tree.column('row',width=60,stretch=False)
        tree.column('name',width=300)
        sb=ttk.Scrollbar(left,command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left',fill='both',expand=True)
        sb.pack(side='right',fill='y')
        tree.bind('<<TreeviewSelect>>',lambda e:self.select_row(group))
        right=ttk.Frame(body,padding=(16,8))
        picture=ttk.Label(right)
        picture.pack(anchor='w')
        desc=tk.StringVar()
        ttk.Label(right,textvariable=desc,wraplength=660,justify='left',padding=(0,6)).pack(fill='x')
        scroll=ScrollFrame(right)
        scroll.pack(fill='both',expand=True)
        body.add(left,weight=2)
        body.add(right,weight=4)
        tab.editor={'group':group,'source':src,'query':query,'tree':tree,'desc':desc,'picture':picture,'form':scroll.body}

    def current_editor(self):
        widget=self.root.nametowidget(self.tabs.select())
        return getattr(widget,'editor',None)

    def get_editor(self,group):
        for tab in self.tabs.tabs():
            widget=self.root.nametowidget(tab)
            if getattr(widget,'editor',{}).get('group')==group:
                return widget.editor

    def tab_change(self,event=None):
        ed=self.current_editor()
        if ed and (not self.document or self.document.path.name!=ed['source'].get()):
            self.open_source(ed['group'])

    def pending(self):
        if self.document and self.document.changes:
            return messagebox.askyesno('Discard edits?',f'Discard {len(self.document.changes)} unsaved cell changes?',parent=self.root)
        return True

    def open_source(self,group):
        ed=self.get_editor(group)
        if not self.pending():
            if self.document:
                for tab in self.tabs.tabs():
                    previous=self.root.nametowidget(tab)
                    pe=getattr(previous,'editor',{})
                    if any(p==self.document.path for p in self.source_map.get(pe.get('group'),[])):
                        pe['source'].set(self.document.path.name)
                        self.tabs.select(tab)
                        break
            return
        try:
            path=next(p for p in self.source_map[group] if p.name==ed['source'].get())
            self.document=Document(path)
            self.selected=None
            self.fields=[]
            for child in ed['form'].winfo_children(): child.destroy()
            ed['picture'].configure(image='',text='')
            ed['desc'].set(DESCRIPTIONS.get(path.name,'Game parameters in the original table. Unmapped columns retain their original names or column numbers.'))
            self.filter(group)
            self.status.set(f'{path.relative_to(ROOT)} · {len(self.document.rows)-self.document.start:,} rows · server copy')
        except Exception as e:
            messagebox.showerror('Open table',str(e),parent=self.root)

    def filter(self,group):
        ed=self.get_editor(group)
        doc=self.document
        if not doc or ed['source'].get()!=doc.path.name: return
        tree=ed['tree']
        tree.delete(*tree.get_children())
        q=ed['query'].get().lower().strip()
        for i,row in enumerate(doc.rows):
            if i<doc.start or not any(c.strip() for c in row): continue
            if q and not doc.matches(i,q): continue
            tree.insert('','end',iid=str(i),values=(i,doc.title(i,self.original_text.get())))

    def text_view(self):
        ed=self.current_editor()
        if not ed or not self.document: return
        for col,var,entry in self.fields:
            if entry.cget('state')!='readonly':
                self.cell(col,var,original=not self.original_text.get())
        selected=self.selected
        self.filter(ed['group'])
        if selected is not None and ed['tree'].exists(str(selected)):
            ed['tree'].selection_set(str(selected))
            ed['tree'].see(str(selected))
            self.show_fields(ed)

    def select_row(self,group):
        ed=self.get_editor(group)
        selection=ed['tree'].selection()
        if not selection: return
        self.selected=int(selection[0])
        self.show_fields(ed)

    def show_fields(self,ed):
        self.loading=True
        form=ed['form']
        for w in form.winfo_children(): w.destroy()
        doc=self.document
        row=doc.rows[self.selected]
        self.fields=[]
        for col,original in enumerate(row):
            label=doc.label(col)
            ttk.Label(form,text=f'{col:02}  {label}',wraplength=230).grid(row=col,column=0,sticky='nw',pady=5,padx=(0,10))
            var=tk.StringVar(value=doc.display_value(self.selected,col,self.original_text.get()))
            locked=col in IDENTIFIERS.get(doc.path.name,set()) or (doc.is_text and doc.path.suffix=='.ini' and col<2) or (doc.path.name=='mode_tuning.txt' and col!=3)
            entry=ttk.Entry(form,textvariable=var,state='readonly' if locked else 'normal')
            entry.grid(row=col,column=1,sticky='ew',pady=3)
            # Commit only on focus out / Enter; validation errors never become pending edits.
            entry.bind('<FocusOut>',lambda e,c=col,v=var,d=doc,r=self.selected,o=self.original_text.get():self.cell(c,v,d,r,o))
            entry.bind('<Return>',lambda e,c=col,v=var,d=doc,r=self.selected,o=self.original_text.get():self.cell(c,v,d,r,o))
            self.fields.append((col,var,entry))
        form.columnconfigure(1,weight=1)
        self.loading=False
        self.preview(self.selected)

    def cell(self,col,var,doc=None,row=None,original=None):
        if self.loading or self.selected is None: return
        doc=doc or self.document
        row=self.selected if row is None else row
        original=self.original_text.get() if original is None else original
        try:
            doc.set_display(row,col,var.get(),original)
            self.status.set(f'{doc.path.name} · {len(doc.changes)} pending cell changes')
        except ValueError as e:
            var.set(doc.display_value(row,col,original))
            self.status.set(str(e))

    def preview(self,row):
        ed=self.current_editor()
        if not ed or not self.document: return
        doc=self.document
        translate=(lambda text:text) if self.original_text.get() else english
        item=doc.item_id(row)
        fields=doc.rows[row]
        key=''
        if doc.path.name in ('ItemClient.tdf','UseItemClient.tdf') and len(fields)>3:
            key=fields[3]
        if doc.path.name=='VehicleList.xlt':
            key=fields[8].rsplit('.',1)[0]
        elif doc.path.name=='VehicleUpgrade.xlt':
            path=ROOT/'server_data/Init/VehicleList.xlt'
            for r in Document(path).rows[4:]:
                if len(r)>9 and r[9]==fields[1]:
                    key=r[8].rsplit('.',1)[0]
                    break
        description=DESCRIPTIONS.get(doc.path.name,'Original game table. Columns marked raw parameter have no verified description yet.')
        description+='\n\n'+doc.title(row,self.original_text.get())
        for c in range(len(fields)):
            if doc.label(c).lower() in ('description','desc (tooltip)','objective') and fields[c] not in ('n/a',''):
                description+='\n'+translate(doc.value(row,c))
        if doc.is_text:
            description+='\n'+translate(doc.hints.get(row,''))
            if doc.path.name=='mode_tuning.txt' and len(fields)>4:
                description+='\n'+fields[4]
        img=self.art.get(key,item) if self.art else None
        if self.art and item in self.art.catalog and not any(doc.label(c).lower()=='description' for c in range(len(fields))):
            description+='\n'+translate(self.art.catalog[item].get('desc',''))
        if img:
            from PIL import ImageTk
            img=img.copy()
            img.thumbnail((260,100))
            self.icon=ImageTk.PhotoImage(img,master=self.root)
            ed['picture'].configure(image=self.icon,text='')
        else:
            self.icon=None
            ed['picture'].configure(image='',text='No game picture mapped for this entry')
        ed['desc'].set(description)

    def save(self):
        ed=self.current_editor()
        if not ed or not self.document: return
        # Flush the active row even when Save is clicked without changing focus.
        for col,var,entry in self.fields:
            if entry.cget('state')!='readonly': self.cell(col,var)
        if not self.document.changes:
            self.status.set('No pending changes')
            return
        try:
            backup=self.document.save()
            self.status.set(f'Saved · backup: {backup} · restart emulator to apply cached data')
        except Exception as e:
            messagebox.showerror('Save failed',str(e),parent=self.root)

    def duplicate_reward(self):
        doc=self.document
        if not doc or doc.path.name not in ('delivery_rewards.txt','patrol_rewards.txt') or self.selected is None:
            messagebox.showinfo('Reward rows','Select a row in delivery_rewards.txt or patrol_rewards.txt to add another item prize.')
            return
        doc.duplicate(self.selected)
        self.filter('Modes & rewards')
        ed=self.get_editor('Modes & rewards')
        key=str(len(doc.rows)-1)
        ed['tree'].selection_set(key)
        ed['tree'].see(key)

    def build_console(self):
        ttk.Label(self.console_tab,text='LOCAL SERVER CONSOLE',font=('DejaVu Sans',14,'bold')).pack(anchor='w')
        ttk.Label(self.console_tab,text='Commands execute through 127.0.0.1 on the emulator’s GM control port. Select a template, replace its arguments, then run.',wraplength=1000).pack(anchor='w',pady=8)
        templates=['who','item NAME ITEM-ID 1','drift NAME DRIFT-ITEM-ID 7','level NAME 81','exp NAME 1000','money NAME 10000','coin ACCOUNT 100','kick NAME','block NAME 1','unblock NAME','chatblock NAME 10','ban ACCOUNT','unban ACCOUNT','realmatch status','realmatch open','realmatch close','cbattle status','cbattle now 2 20','cbattle stakes on','partytest NAME on','vchasetest NAME on','uctest NAME on 1','cbtest NAME on','getrushtime','rushtimenow','rushend','gate off']
        self.command=tk.StringVar(value='who')
        entry=ttk.Combobox(self.console_tab,textvariable=self.command,values=templates)
        entry.pack(fill='x',pady=8)
        entry.bind('<Return>',lambda e:self.run_command())
        entry.bind('<Up>',lambda e:self.recall(-1))
        entry.bind('<Down>',lambda e:self.recall(1))
        ttk.Button(self.console_tab,text='Run command',command=self.run_command).pack(anchor='w')
        self.output=tk.Text(self.console_tab,bg='#111820',fg='#72dec8',font=('DejaVu Sans Mono',11),state='disabled',wrap='word')
        self.output.pack(fill='both',expand=True,pady=12)

    def recall(self,direction):
        if self.history:
            self.history_pos=max(0,min(len(self.history)-1,self.history_pos+direction))
            self.command.set(self.history[self.history_pos])
        return 'break'

    def log(self,value):
        self.output.configure(state='normal')
        self.output.insert('end',value+'\n\n')
        self.output.see('end')
        self.output.configure(state='disabled')

    def run_command(self):
        text=self.command.get().strip()
        if text.split()[:1] and text.split()[0] in ('account-create','account-password'):
            messagebox.showinfo('Credentials','Use the Accounts tab for credential changes; it keeps passwords out of command history.')
            return
        self.history.append(text)
        self.history_pos=len(self.history)
        self.log('> '+text)
        self.async_job(lambda:gm(text),self.log)

    def build_accounts(self):
        bar=ttk.Frame(self.account_tab)
        bar.pack(fill='x')
        self.account_query=tk.StringVar()
        ttk.Entry(bar,textvariable=self.account_query,width=32).pack(side='left')
        ttk.Button(bar,text='Search accounts',command=self.accounts).pack(side='left',padx=8)
        ttk.Button(bar,text='Create account',command=self.create_account).pack(side='right')
        self.account_tree=ttk.Treeview(self.account_tab,columns=('account','valid','joined'),show='headings',height=8,selectmode='browse')
        for col in ('account','valid','joined'): self.account_tree.heading(col,text=col.title())
        self.account_tree.pack(fill='x',pady=12)
        self.account_tree.bind('<<TreeviewSelect>>',lambda e:self.account_detail())
        actions=ttk.Frame(self.account_tab)
        actions.pack(fill='x')
        for text,action in [('Ban',lambda:self.account_action('ban')),('Unban',lambda:self.account_action('unban')),('Reset password',self.reset_password),('Grant GM',lambda:self.role('A')),('Revoke GM',lambda:self.role('N')),('Add G Coin',self.coins)]:
            ttk.Button(actions,text=text,command=action).pack(side='left',padx=(0,6))
        self.account_info=tk.StringVar(value='Search to connect to the running emulator. Account details include characters, balances, roles and online status.')
        ttk.Label(self.account_tab,textvariable=self.account_info,justify='left',wraplength=1000).pack(anchor='w',pady=16)
        ttk.Label(self.account_tab,text='Password and role changes require the account to leave both the game and lobby. GM roles apply to existing characters. Ban disconnects the account.',wraplength=1000).pack(anchor='w',pady=8)

    @staticmethod
    def json_reply(reply):
        if not reply.startswith('OK '): raise ValueError(reply)
        return json.loads(reply[3:])

    def accounts(self):
        def done(reply):
            rows=self.json_reply(reply)
            self.account_tree.delete(*self.account_tree.get_children())
            for r in rows:
                self.account_tree.insert('','end',iid=r['account'],values=(r['account'],r['valid'],r['joined']))
            self.status.set(f'{len(rows)} accounts · maximum 300 per search')
        query=self.account_query.get()
        self.async_job(lambda:gm('accounts '+query),done)

    def selected_account(self):
        rows=self.account_tree.selection()
        if not rows: raise ValueError('Select an account first.')
        return rows[0]

    def account_detail(self):
        try: member=self.selected_account()
        except ValueError: return
        def done(reply):
            r=self.json_reply(reply)
            lines=[f"{r['account']}  ·  {'Active' if r['valid']=='y' else 'Banned'}  ·  G Coin: {r['coins']}"]
            for c in r['characters']:
                lines.append(f"{c['name']}  ·  level {c['level']}  ·  {c['mito']} Mito  ·  role {c['role']}  ·  {('Online' if c['online'] else 'Offline')}  ·  state {c['state']}")
            if not r['characters']: lines.append('No characters yet')
            self.account_info.set('\n\n'.join(lines))
        self.async_job(lambda:gm('account '+member),done)

    def account_action(self,cmd,arg=''):
        try: member=self.selected_account()
        except ValueError as e:
            messagebox.showinfo('Accounts',str(e)); return
        self.async_job(lambda:gm(f'{cmd} {member} {arg}'.strip()),self.account_result)

    def account_result(self,reply):
        self.status.set(reply)
        self.account_detail()
        if not reply.startswith('OK'): messagebox.showerror('Account action',reply,parent=self.root)

    def password(self):
        value=simpledialog.askstring('Password','New password (1–63 UTF-8 bytes, no whitespace):',show='*',parent=self.root)
        if value is None: return None
        if not value or any(c.isspace() for c in value) or len(value.encode())>63:
            messagebox.showerror('Password','Use 1–63 UTF-8 bytes without whitespace.'); return None
        again=simpledialog.askstring('Confirm password','Repeat new password:',show='*',parent=self.root)
        if value!=again:
            messagebox.showerror('Password','Passwords do not match.'); return None
        return value

    def create_account(self):
        member=simpledialog.askstring('Create account','Account ID (letters, digits, _, . or -):',parent=self.root)
        if not member: return
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',member):
            messagebox.showerror('Account ID','Use 1–32 letters, digits, _, . or -.'); return
        password=self.password()
        if password:
            self.async_job(lambda:gm(f'account-create {member} {password}'),lambda r:(self.status.set(r),self.accounts(),messagebox.showinfo('Create account',r)))

    def reset_password(self):
        try: self.selected_account()
        except ValueError as e:
            messagebox.showinfo('Accounts',str(e)); return
        password=self.password()
        if password: self.account_action('account-password',password)

    def role(self,value):
        self.account_action('account-role',value)

    def coins(self):
        value=simpledialog.askinteger('G Coin','Amount to add (negative subtracts):',parent=self.root)
        if value is not None: self.account_action('coin',str(value))

    def restart(self):
        if not messagebox.askyesno('Restart emulator','Restart the emulator now? Connected players will be disconnected.',parent=self.root): return
        import subprocess,os
        def work():
            if os.name=='nt':
                cmd=['powershell','-ExecutionPolicy','Bypass','-File',str(ROOT/'launch.ps1'),'restart-emu']
            else: cmd=['bash',str(ROOT/'launch.sh'),'restart-emu']
            p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90)
            return (p.stdout+p.stderr).strip()
        self.async_job(work,lambda r:(self.log(r),self.status.set('Restart finished; check GM Console for output')))

    def help(self):
        messagebox.showinfo('Server Workshop',
            'Items / Cars: choose a table, search and select a row, then edit the named fields. Row numbers and linked IDs stay fixed.\n\n'
            'Korean item names, tooltips and table headings display in English. Search accepts English and Korean. Original table text shows the source values. Display translations are never saved automatically; only explicit field edits change a table. Unmapped historical text keeps its original wording.\n\n'
            'Modes & rewards: all available server tables, reward files, schedules, and gameplay sections of emulator.ini. Select a setting to read its existing comments. Unknown fields are marked raw parameter; mechanics hardcoded in Python are outside table editing.\n\n'
            'Save creates an exact backup in Emulator/editor_backups and rejects edits if another process changed the file. Ctrl+S saves the current table. Reload discards changes after confirmation.\n\n'
            'Server table changes require an emulator restart; delivery / patrol item rewards reload automatically. Client prices, names and physics can also be cached in client packs. This tool edits server copies; client packs need their own deliberate synchronization.\n\n'
            'GM Console / Accounts require the running emulator. Use level / exp / money for online characters. Account role and password changes require full logout.\n\n'
            'Artwork comes from Client US and the optional Drift City Item Catalog.zip. No client archives are changed.',parent=self.root)

    def close(self):
        if self.pending():
            self.executor.shutdown(wait=False,cancel_futures=True)
            self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',type=Path,default=ROOT.parent/'Client US')
    parser.add_argument('--smoke-test',action='store_true',help='Build the UI and close it after artwork loads (no data writes)')
    args=parser.parse_args()
    try:
        import PIL  # noqa: F401
    except ImportError:
        parser.exit(1,'Install editor dependencies: python -m pip install -r tools/editor/requirements.txt\n')
    root=tk.Tk()
    app=Workshop(root,args.client)
    if args.smoke_test:
        def finish():
            if app.jobs:
                root.after(100,finish)
            else:
                for index,group,filename in [(0,'Items','UseItemClient.tdf'),(1,'Cars','VehicleUpgrade.xlt'),(2,'Modes & rewards','mode_tuning.txt')]:
                    app.tabs.select(index)
                    root.update()
                    ed=app.get_editor(group)
                    ed['source'].set(filename)
                    app.open_source(group)
                    keys=ed['tree'].get_children()
                    assert keys, filename
                    ed['tree'].selection_set(keys[0])
                    root.update()
                    assert app.fields, filename
                    assert not app.document.changes, filename
                app.tabs.select(0)
                root.update()
                ed=app.get_editor('Items')
                row=next(i for i,r in enumerate(app.document.rows) if r[2]=='개인 수리 키트 Ⅰ')
                ed['tree'].selection_set(str(row))
                root.update()
                assert app.fields[2][1].get()=='Personal Repair Kit Ⅰ'
                app.original_text.set(True)
                app.text_view()
                root.update()
                assert app.fields[2][1].get()=='개인 수리 키트 Ⅰ'
                app.original_text.set(False)
                app.text_view()
                root.update()
                for col,var,entry in app.fields:
                    app.cell(col,var)
                assert not app.document.changes, 'Display translations must not become edits'
                root.update()
                if app.art:
                    assert app.art.get('ac01_01_a') is not None, 'Car picture did not load'
                    assert app.art.get('ig_p_1q','i_s_000001') is not None, 'Item picture did not load'
                print('Desktop smoke test passed: forms, artwork, English/original views, no implicit edits; no writes')
                app.close()
        root.after(200,finish)
    root.mainloop()


if __name__=='__main__':
    main()
