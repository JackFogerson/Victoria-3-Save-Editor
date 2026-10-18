"""Shared state selection, with independent scrolling panels in existing tabs."""
from pathlib import Path
from types import SimpleNamespace
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from batch_tab import BatchTab, StateCard
from batch_states import load_batch, apply_batch
from autocomplete import LiveSuggestions
from mass_migration import signature, field
from save_resources import resources_from_records
from state_resource_tab import StateResourceTab
from state_resources import scan_regions, DEFAULT_REGION_FOLDER


class PanelHost(ttk.Frame):
    def add(self, child, **kwargs):
        child.pack(fill='x', expand=True)


class ResourceCard(ttk.LabelFrame):
    def __init__(self, parent, owner, sid):
        super().__init__(parent, text=owner.label(sid), padding=6)
        self.pack(fill='x', padx=6, pady=6)
        self.panel = None
        from settlement_checklist import checklist
        catalog = owner.snapshot.get('settlement_catalog')
        frame = ttk.LabelFrame(self, text='Settlement checklist', padding=5)
        frame.pack(fill='x', pady=5)
        if catalog:
            table = ttk.Treeview(frame, columns=('type','town','status','building'), show='headings', height=5)
            for key, title, width in [('type','Hub',65),('town','Town',140),('status','Status',135),('building','Existing building / what to build',480)]:
                table.heading(key,text=title); table.column(key,width=width,minwidth=55)
            table.pack(fill='x')
            for row in checklist(owner.snapshot,sid,catalog): table.insert('', 'end', values=row)
        else: ttk.Label(frame,text='Reload all states to load settlement definitions.').pack(anchor='w')
        ttk.Label(frame,text='Checks built levels in this state, not resource capacity or queued construction. Building present does not verify map visibility.\nSuggested buildings still need suitable resources/technology. Reload all states after construction and a new save.',wraplength=900).pack(anchor='w')
        try:
            loaded = resources_from_records(owner.snapshot['path'], owner.snapshot['signature'], sid,
                                            owner.snapshot['state_records'], owner.snapshot['regions'])
        except ValueError as exc:
            ttk.Label(self, text=str(exc)).pack(anchor='w'); return
        host = PanelHost(self); host.pack(fill='x')
        proxy = SimpleNamespace(state_id=tk.StringVar(value=sid), file_path=owner.editor.file_path)
        panel = self.panel = StateResourceTab(host, proxy)
        # The shared selector and loader replace the single-state navigation controls.
        children = panel.winfo_children()
        for child in children[:3]: child.pack_forget()
        for child in children[3].winfo_children():
            if isinstance(child, ttk.Button): child.pack_forget()
        panel.save_button.pack_forget()
        panel.region = loaded['region']; panel.save_data = loaded
        panel.land.set(loaded['values']['arable_land'])
        panel.arable = list(loaded['values']['arable_resources'])
        panel.capped = dict(loaded['values']['capped_resources'])
        panel.undiscovered = dict(loaded['undiscovered']); panel.converted = set()
        panel.options = owner.resource_options
        panel.initial = panel.values()
        panel.status.set('Region totals; split-state portions share these resources. Changes are staged until Apply.')
        panel.refresh()
        for key in panel.queries: panel.search(key)

    def plan(self):
        if self.panel and self.panel.values() != self.panel.initial:
            return {'resources': self.panel.values()}
        return {}


class MigrationCard(ttk.LabelFrame):
    def __init__(self, parent, owner, sid):
        super().__init__(parent, text=owner.label(sid), padding=10)
        self.pack(fill='x', padx=6, pady=6)
        self.owner = owner
        self.enabled = tk.BooleanVar()
        self.culture = tk.StringVar(); self.source = tk.StringVar(); self.days = tk.StringVar(value='365')
        self.suggestions = []
        self.sources = {f'{cid} ({name})': cid for cid, name in owner.snapshot['countries'].items() if name}
        ttk.Checkbutton(self, text='Create a mass migration to this state', variable=self.enabled).pack(anchor='w')
        self.combo('Migrating culture', self.culture, owner.culture_labels)
        self.combo('Source country', self.source, self.sources)
        row = ttk.Frame(self); row.pack(fill='x', pady=4)
        ttk.Label(row, text='Duration in days', width=22).pack(side='left')
        ttk.Entry(row, textvariable=self.days, width=10).pack(side='left')
        occupied = field(owner.snapshot['state_records'][sid][2], 'mass_migration') is not None
        ttk.Label(self, text='An existing migration is present; a second event will be rejected.' if occupied else 'Destination: ' + owner.label(sid) + '. Tick the box to include this event.').pack(anchor='w')

    def combo(self, label, variable, choices):
        row = ttk.Frame(self); row.pack(fill='x', pady=4)
        ttk.Label(row, text=label, width=22).pack(side='left')
        picker = ttk.Combobox(row, textvariable=variable, width=50); picker.pack(side='left', fill='x', expand=True)
        def search(): picker.configure(values=[v for v in choices if variable.get().casefold().strip() in v.casefold()])
        picker.configure(postcommand=search); search()
        self.suggestions.append(LiveSuggestions(picker, variable, search))

    def plan(self):
        if not self.enabled.get(): return {}
        source = self.source.get().strip(); source = self.sources.get(source, source)
        if source not in self.owner.snapshot['countries']: raise ValueError('Choose a source country for each enabled migration.')
        return {'migration': {'culture': self.owner.resolve_culture(self.culture.get()), 'source': source, 'days': int(self.days.get())}}


class MultiStateWorkspace(BatchTab):
    sections = {'Modify Workforces': 'workforce', 'Change Culture': 'culture', 'Change Religion': 'religion',
                'State Homelands': 'homelands', 'State Editor': 'resources', 'Mass Migration': 'migration'}

    def __init__(self, parent, notebook, editor):
        ttk.Frame.__init__(self, parent)
        self.pack(fill='x')
        self.editor, self.snapshot = editor, None
        self.cards, self.state_labels, self.culture_labels = {}, {}, {}
        self.busy = False; self.results = queue.Queue(); self.pending = None
        self.query = tk.StringVar(); self.status = tk.StringVar(value='Load the save, then add states. The same list appears in every state tab.')
        self.resource_options = {'arable_resources': [], 'capped_resources': []}
        self.restore_ids = []
        self.refresh_requested = False
        row = ttk.Frame(self); row.pack(fill='x')
        self.load_button = ttk.Button(row, text='Load / Refresh (Keep Edits)', command=self.load); self.load_button.pack(side='left')
        self.picker = ttk.Combobox(row, textvariable=self.query, width=30, postcommand=self.search); self.picker.pack(side='left', padx=5)
        self.suggestions = LiveSuggestions(self.picker, self.query, self.search)
        ttk.Button(row, text='Add State', command=self.add).pack(side='left')
        ttk.Button(row, text='Remove Selected State', command=self.remove_selected).pack(side='left', padx=5)
        ttk.Button(row, text='Clear States', command=self.clear_selection).pack(side='left')
        self.selection = tk.Listbox(self, height=2, exportselection=False)
        self.selection.pack(fill='x', pady=3)
        ttk.Label(self, textvariable=self.status, wraplength=940).pack(anchor='w')
        self.pages, self.bodies = {}, {}
        for tab in list(notebook.tabs()):
            title = notebook.tab(tab, 'text')
            if title not in self.sections: continue
            position = notebook.index(tab); notebook.hide(tab)
            page = ttk.Frame(notebook); notebook.insert(position, page, text=title)
            section = self.sections[title]; self.pages[section] = page
            ttk.Label(page, text='All selected states are below. Edit each independently, then Apply All State Changes.', padding=6).pack(anchor='w')
            if section == 'culture':
                ttk.Label(page, text='Percentages change workers + dependents before culture conversions.').pack(anchor='w', padx=6)
            if section == 'workforce':
                ttk.Button(page, text='Estimate shortages for all selected states', command=self.estimate_all).pack(anchor='w', padx=6)
            area = ttk.Frame(page); area.pack(fill='both', expand=True)
            canvas = tk.Canvas(area, highlightthickness=0)
            scroll = ttk.Scrollbar(area, command=canvas.yview); scroll.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True); canvas.configure(yscrollcommand=scroll.set)
            body = ttk.Frame(canvas); window = canvas.create_window((0,0), window=body, anchor='nw')
            body.bind('<Configure>', lambda e,c=canvas: c.configure(scrollregion=c.bbox('all')))
            canvas.bind('<Configure>', lambda e,c=canvas,w=window: c.itemconfigure(w,width=e.width))
            self.bodies[section] = body
            def wheel(event, c=canvas, p=page):
                if str(event.widget).startswith(str(p)) and not isinstance(event.widget, (ttk.Combobox, tk.Listbox)):
                    c.yview_scroll(-int(event.delta / 120), 'units')
            page.winfo_toplevel().bind('<MouseWheel>', wheel, add='+')
        notebook.select(self.pages['workforce'])
        self.apply_button = ttk.Button(self, text='Apply All State Changes', command=self.apply)
        self.apply_button.pack(anchor='e')
        self.trace = editor.file_path.trace_add('write', self.file_changed)
        self.bind('<Destroy>', self.cleanup, add='+')

    def file_changed(self, *_):
        if self.snapshot is None: return
        try:
            current = Path(self.editor.file_path.get()).resolve()
            if current != Path(self.snapshot['path']):
                self.status.set('Drafts kept for ' + Path(self.snapshot['path']).name + '. Select that save again to continue. Refresh will not discard them.')
                self.apply_button.configure(state='disabled'); return
            if signature(current) == self.snapshot['signature']:
                if not self.busy: self.apply_button.configure(state='normal')
                return
        except OSError as exc:
            self.status.set('Drafts kept. Cannot read save: ' + str(exc)); return
        if self.busy:
            self.refresh_requested = True
            return
        self.refresh_drafts()

    def refresh_drafts(self):
        if self.busy or self.snapshot is None: return
        previous = self.snapshot
        path = self.editor.file_path.get()
        if Path(path).resolve() != Path(previous['path']):
            self.status.set('Drafts kept for ' + Path(previous['path']).name + '. Select the original save or explicitly Clear States first.')
            return
        ids = list(self.cards)
        def refresh():
            from state_drafts import rebase_drafts
            fresh = load_batch(path, include_settlements=True)
            return rebase_drafts(previous, fresh, ids)
        self.refresh_requested = False
        self.run('refresh', path, refresh)
        self.status.set('Refreshing save data; keeping all pending state edits...')

    def label(self, sid):
        return f'{sid} ({self.snapshot["states"][sid]["region"].removeprefix("STATE_").replace("_", " ").title()})'

    def clear_cards(self):
        for panels in self.cards.values():
            for panel in panels.values(): panel.destroy()
        self.cards.clear(); self.selection.delete(0,'end')
        self.reset_views()

    def reset_views(self):
        for body in self.bodies.values():
            canvas = body.master
            canvas.yview_moveto(0)
            canvas.xview_moveto(0)

    def clear_selection(self):
        if self.busy: return
        if self.cards and not messagebox.askyesno('Clear States', 'Remove all states and their queued edits?'): return
        self.clear_cards()

    def remove_selected(self):
        chosen = self.selection.curselection()
        if chosen: self.remove(list(self.cards)[chosen[0]])

    def remove(self, sid):
        if self.busy: return
        if not messagebox.askyesno('Remove State', 'Remove this state and its queued edits from all tabs?'): return
        for card in self.cards.pop(sid).values(): card.destroy()
        self.refresh_selection()
        self.reset_views()

    def refresh_selection(self):
        self.selection.delete(0,'end')
        for sid in self.cards: self.selection.insert('end',self.label(sid))

    def add(self):
        if self.busy or self.snapshot is None: return
        value = self.query.get().strip(); sid = self.state_labels.get(value,value)
        if sid not in self.snapshot['states']:
            messagebox.showerror('Choose State','Choose a state by name or save ID.'); return
        if sid not in self.cards:
            panels = self.cards[sid] = {}
            for section, body in self.bodies.items():
                if section == 'resources': panels[section] = ResourceCard(body,self,sid)
                elif section == 'migration': panels[section] = MigrationCard(body,self,sid)
                else:
                    card = StateCard(body,self,sid); panels[section] = card
                    # Show only the controls belonging to this existing tab.
                    for index, child in enumerate(card.winfo_children()):
                        wanted = {'homelands':1,'culture':2,'religion':3,'workforce':4}[section]
                        if index != wanted: child.pack_forget()
            self.refresh_selection()
        self.query.set('')

    def plans(self):
        plans = {}
        for sid, panels in self.cards.items():
            plan = {}
            for section, panel in panels.items():
                if section in ('resources','migration'): plan.update(panel.plan()); continue
                keys = {'culture':('percentages','cultures'), 'religion':('religions',), 'workforce':('workforce',), 'homelands':('homelands',)}[section]
                values = panel.plan()
                plan.update({k:values[k] for k in keys if k in values})
            plans[sid] = plan
        return plans

    def load(self):
        if self.busy: return
        if self.cards and self.snapshot is not None:
            self.refresh_drafts(); return
        self.restore_ids = list(self.cards)
        path = self.editor.file_path.get()
        if not Path(path).is_file(): messagebox.showerror('Select Save','Select a text save first.'); return
        self.run('load',path,lambda: load_batch(path, include_settlements=True))

    def apply(self):
        if self.busy or self.snapshot is None: return
        try:
            if Path(self.editor.file_path.get()).resolve() != Path(self.snapshot['path']) or signature(self.snapshot['path']) != self.snapshot['signature']:
                raise ValueError('Save changed. Use Load / Refresh (Keep Edits); your drafts remain intact.')
            plans = self.plans()
            if not plans: raise ValueError('Add at least one state.')
        except (OSError,ValueError) as exc: messagebox.showerror('Cannot Apply',str(exc)); return
        self.restore_ids = list(self.cards); snapshot = self.snapshot
        def write():
            result = apply_batch(snapshot,plans)
            # A successful write must never be mistaken for a failure if reloading fails.
            try: refreshed, error = load_batch(snapshot['path'], include_settlements=True), None
            except Exception as exc: refreshed, error = None, str(exc)
            return result, refreshed, error
        self.run('apply',snapshot['path'],write)

    def set_busy(self,busy):
        self.busy=busy
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child,(ttk.Button,ttk.Entry,ttk.Combobox,ttk.Checkbutton,tk.Listbox)):
                    child.configure(state='disabled' if busy else 'normal')
                walk(child)
        walk(self)
        for page in self.pages.values(): walk(page)

    def populate(self, snapshot):
        self.clear_cards(); self.snapshot=snapshot
        self.state_labels={self.label(sid):sid for sid in snapshot['states']}
        self.culture_labels={self.culture_label(cid):cid for cid in snapshot['cultures']}
        self.religion_options=sorted({r for s in snapshot['states'].values() for r in s['religions']})
        try:
            _, arable, capped=scan_regions(DEFAULT_REGION_FOLDER)
            self.resource_options={'arable_resources':arable,'capped_resources':capped}
        except (OSError,ValueError): pass
        for sid in self.restore_ids:
            if sid in snapshot['states']: self.query.set(sid); self.add()
        self.query.set(''); self.search()
        self.reset_views()

    def estimate_all(self):
        if self.busy or not self.snapshot or not self.cards: return
        from shortage_estimator import estimate
        self.run('estimate',self.snapshot['path'],lambda:estimate(self.snapshot['path']))

    def poll(self):
        self.pending=None
        try: action,path,result,error=self.results.get_nowait()
        except queue.Empty: self.pending=self.after(100,self.poll); return
        self.set_busy(False)
        if error:
            self.status.set('Drafts kept. '+error)
            if action == 'refresh': self.apply_button.configure(state='disabled')
            return
        if Path(path).resolve()!=Path(self.editor.file_path.get()).resolve():
            self.status.set('Save selection changed. Existing state drafts are kept for the original save.'); self.apply_button.configure(state='disabled'); return
        if action=='refresh':
            self.snapshot = result
            self.status.set('Save data refreshed. All pending state edits are preserved; Apply All State Changes is ready.')
            # Keep the existing widgets, including partially typed values and selections.
            if self.refresh_requested or signature(path) != result['signature']: self.refresh_drafts()
        elif action=='load':
            self.populate(result); self.status.set('Loaded. Add states by name or ID; all state tabs share this list.')
        elif action=='estimate':
            from shortage_autofill import ShortageAutofill
            for sid,panels in self.cards.items():
                card=panels['workforce']; status=tk.StringVar()
                proxy=SimpleNamespace(editor=SimpleNamespace(job_inputs=card.workforce),status=status)
                ShortageAutofill.fill(proxy,result,sid)
                ttk.Label(card,text=status.get(),wraplength=900).pack(anchor='w')
            self.status.set('Estimates filled for all selected states where data was sufficient. Review before applying.')
        else:
            changes,snapshot,reload_error=result
            if snapshot: self.populate(snapshot)
            else:
                self.snapshot=None; self.clear_cards()
            self.status.set(f'Saved {changes["records"]} records. No backups created. Reload the save in-game.'+ (' Reload editor data: '+reload_error if reload_error else ''))
            # Refresh global tabs after offsets changed; preserve this workspace's fresh snapshot.
            fresh=self.snapshot; self.snapshot=None
            self.editor.select_latest_save()
            self.snapshot=fresh if Path(self.editor.file_path.get()).resolve()==Path(path).resolve() else None
