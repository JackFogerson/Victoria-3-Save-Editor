from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from autocomplete import LiveSuggestions
from culture_definitions import definitions, save_changes
from state_homelands import resolve_state
from state_resources import DEFAULT_REGION_FOLDER, scan_regions, resource_values, replace_resources, nonnegative


class StateResourceTab(ttk.Frame):
    def __init__(self, notebook, editor):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='State Editor')
        self.editor = editor
        self.region = None
        self.folder = tk.StringVar(value=str(DEFAULT_REGION_FOLDER))
        self.land = tk.StringVar(value='0')
        self.status = tk.StringVar(value='Select a save and enter its State ID above, then load the state.')
        ttk.Label(self, text='Edits map definitions for new games; creates a backup when saving.').pack(anchor='w')
        row = ttk.Frame(self); row.pack(fill='x', pady=4)
        ttk.Entry(row, textvariable=self.folder, state='readonly').pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse Folder…', command=self.browse).pack(side='left')
        row = ttk.Frame(self); row.pack(fill='x', pady=4)
        ttk.Button(row, text='Load State', command=self.load).pack(side='left', padx=6)
        ttk.Label(row, text='Arable land:').pack(side='left')
        ttk.Entry(row, textvariable=self.land, width=10).pack(side='left', padx=4)
        ttk.Label(self, textvariable=self.status, wraplength=740).pack(anchor='w', pady=4)
        columns = ttk.Frame(self); columns.pack(fill='both', expand=True)
        self.queries, self.pickers, self.options, self.suggestions = {}, {}, {}, []
        self.lists = {}
        for key, label in [('arable_resources', 'Arable resources'), ('capped_resources', 'Capped resources')]:
            frame = ttk.LabelFrame(columns, text=label, padding=5)
            frame.pack(side='left', fill='both', expand=True, padx=3)
            box = tk.Listbox(frame, exportselection=False, height=8)
            box.pack(fill='both', expand=True)
            scroll = ttk.Scrollbar(frame, orient='horizontal', command=box.xview)
            scroll.pack(fill='x'); box.configure(xscrollcommand=scroll.set)
            self.lists[key] = box
            self.queries[key] = tk.StringVar()
            self.options[key] = []
            combo = ttk.Combobox(frame, textvariable=self.queries[key], width=30)
            combo.pack(fill='x', pady=4)
            self.pickers[key] = combo
            callback = lambda k=key: self.search(k)
            combo.configure(postcommand=callback)
            self.suggestions.append(LiveSuggestions(combo, self.queries[key], callback))
            box.bind('<<ListboxSelect>>', lambda event, k=key: self.select(k))
            row = ttk.Frame(frame); row.pack(fill='x')
            if key == 'capped_resources':
                self.level = tk.StringVar(value='1')
                ttk.Label(row, text='Level:').pack(side='left')
                ttk.Entry(row, textvariable=self.level, width=7).pack(side='left')
            ttk.Button(row, text='Add / Update' if key == 'capped_resources' else 'Add', command=lambda k=key: self.add(k)).pack(side='left')
            ttk.Button(row, text='Remove', command=lambda k=key: self.remove(k)).pack(side='left')
        self.save_button = ttk.Button(self, text='Save State Resources (creates backup)', command=self.save, state='disabled')
        self.save_button.pack(anchor='w', pady=6)

    def search(self, key):
        query = self.queries[key].get().casefold()
        self.pickers[key].configure(values=[name for name in self.options[key] if query in name.casefold()])

    def values(self):
        return {'arable_land': self.land.get(), 'arable_resources': list(self.arable), 'capped_resources': dict(self.capped)}

    def discard(self):
        return self.region is None or self.values() == self.initial or messagebox.askyesno('Unsaved State Changes', 'Discard unsaved state resource changes?')

    def browse(self):
        if not self.discard():
            return
        folder = filedialog.askdirectory(initialdir=self.folder.get())
        if folder:
            self.folder.set(folder)
            self.region = None
            self.save_button.configure(state='disabled')
            for box in self.lists.values(): box.delete(0, 'end')
            self.status.set('Click Load State to read this folder.')

    def selection_context(self):
        return (self.folder.get(), self.editor.state_id.get().strip(), self.editor.file_path.get())

    def load(self):
        if not self.discard():
            return
        try:
            context = self.selection_context()
            folder, sid, save = context
            if not sid.isdecimal(): raise ValueError('Enter a numeric State ID above.')
            regions, arable_options, capped_options = scan_regions(folder)
            region = resolve_state(save, sid)
            if region not in regions: raise ValueError(f'{region} is not present in this folder.')
            path, rid = regions[region]
            original = path.read_bytes()
            text = original.decode('utf-8-sig')
            values = resource_values(definitions(text)[region])
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Load State', str(exc)); return
        self.region, self.context, self.path = region, context, path
        self.original, self.text = original, text
        self.land.set(values['arable_land'])
        self.arable, self.capped = values['arable_resources'], values['capped_resources']
        self.initial = self.values()
        self.options = {'arable_resources': arable_options, 'capped_resources': capped_options}
        for key in self.queries:
            self.queries[key].set(''); self.search(key)
        self.refresh()
        self.status.set(f'State ID {sid} → {region} — {path.name}. Select a capped building to change its level, then click Add / Update.')
        self.save_button.configure(state='normal')

    def refresh(self):
        for box in self.lists.values(): box.delete(0, 'end')
        for name in self.arable: self.lists['arable_resources'].insert('end', name)
        for name, level in self.capped.items(): self.lists['capped_resources'].insert('end', f'{name} = {level}')

    def select(self, key):
        indices = self.lists[key].curselection()
        if self.region is None or not indices: return
        name = (self.arable if key == 'arable_resources' else list(self.capped))[indices[0]]
        self.queries[key].set(name)
        if key == 'capped_resources': self.level.set(self.capped[name])

    def add(self, key):
        if self.region is None:
            messagebox.showerror('Load State', 'Load a state first.'); return
        import re
        name = self.queries[key].get().strip()
        try:
            if not re.fullmatch(r'building_\w+', name): raise ValueError('Enter a building key, such as building_iron_mine.')
            if key == 'capped_resources': self.capped[name] = nonnegative(self.level.get())
            elif name not in self.arable: self.arable.append(name)
        except ValueError as exc:
            messagebox.showerror('Invalid Resource', str(exc)); return
        self.refresh()

    def remove(self, key):
        if self.region is None: return
        indices = self.lists[key].curselection()
        if indices:
            if key == 'arable_resources': del self.arable[indices[0]]
            else: del self.capped[list(self.capped)[indices[0]]]
            self.refresh()

    def save(self):
        if self.region is None: return
        if self.context != self.selection_context():
            messagebox.showerror('Selection Changed', 'Reload the state before saving this selection.'); return
        try:
            values = self.values()
            values['arable_land'] = nonnegative(values['arable_land'])
            changes = {key: value for key, value in values.items() if value != self.initial[key]}
            if not changes: return
            updated = replace_resources(self.text, self.region, changes)
            encoded = (b'\xef\xbb\xbf' if self.original.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
            backup = save_changes(self.path, self.original, encoded)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Save State', str(exc)); return
        self.original, self.text = encoded, updated
        self.land.set(values['arable_land'])
        self.initial = self.values()
        self.status.set(f'Saved {self.region}. Backup: {backup.name}')
        self.editor.select_latest_save()
