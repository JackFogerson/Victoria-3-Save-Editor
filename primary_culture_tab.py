import tkinter as tk
from tkinter import ttk, messagebox
from autocomplete import LiveSuggestions
from primary_cultures import culture_ids, read_country, save_primary_cultures


class PrimaryCultureTab(ttk.Frame):
    def __init__(self, notebook, editor):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='Primary Cultures')
        self.editor = editor
        self.loader = editor.migration_tab
        self.index = None
        self.country_id = None
        self.ids = []
        self.labels = {}
        self.variables, self.pickers, self.choices, self.suggestions = {}, {}, {}, []
        ttk.Label(self, text='Edit a nation’s primary cultures in the selected save.').pack(anchor='w')
        ttk.Button(self, text='Reload Choices', command=self.loader.load).pack(anchor='w', pady=8)
        for key, title in [('country', 'Nation (ID or tag)'), ('culture', 'Culture (ID or name)')]:
            row = ttk.Frame(self); row.pack(fill='x', pady=6)
            ttk.Label(row, text=title, width=24).pack(side='left')
            self.variables[key] = tk.StringVar()
            self.choices[key] = {}
            refresh = lambda k=key: self.search(k)
            picker = ttk.Combobox(row, textvariable=self.variables[key], postcommand=refresh, width=55)
            picker.pack(side='left', fill='x', expand=True)
            self.pickers[key] = picker
            self.suggestions.append(LiveSuggestions(picker, self.variables[key], refresh))
        self.variables['country'].trace_add('write', self.select_country)
        ttk.Label(self, text='Current primary cultures:').pack(anchor='w', pady=(12, 4))
        self.listbox = tk.Listbox(self, height=9, selectmode='extended', exportselection=False)
        self.listbox.pack(fill='x')
        row = ttk.Frame(self); row.pack(fill='x', pady=8)
        ttk.Button(row, text='Add Culture', command=self.add).pack(side='left')
        ttk.Button(row, text='Remove Selected', command=self.remove).pack(side='left', padx=8)
        self.save_button = ttk.Button(row, text='Save Primary Cultures', command=self.save, state='disabled')
        self.save_button.pack(side='left')
        ttk.Label(self, text='Keep at least one primary culture. Saving does not create a backup.\nReload the edited save in-game to apply the change.', wraplength=900).pack(anchor='w')
        self.status = tk.StringVar(value='Choices load automatically from the selected save.')
        ttk.Label(self, textvariable=self.status, wraplength=900).pack(anchor='w', pady=8)
        self.loader.bind('<<MigrationChoicesLoaded>>', self.loaded, add='+')
        self.file_trace = editor.file_path.trace_add('write', self.reset)
        self.bind('<Destroy>', self.cleanup, add='+')

    def cleanup(self, event):
        if event.widget == self:
            self.editor.file_path.trace_remove('write', self.file_trace)

    def reset(self, *_):
        self.index = None
        self.country_id = None
        self.ids = []
        self.listbox.delete(0, 'end')
        self.save_button.configure(state='disabled')
        for key in self.choices:
            self.choices[key] = {}
            self.variables[key].set('')
            self.search(key)
        self.status.set('Loading choices from the selected save…')

    def loaded(self, event=None):
        self.reset()
        self.index = self.loader.index
        self.choices['country'] = dict(self.loader.choices['source'])
        self.choices['culture'] = dict(self.loader.choices['culture'])
        self.labels = {cid: label for label, cid in self.choices['culture'].items()}
        for key in self.choices:
            self.search(key)
        self.status.set('Choose a nation to view its primary cultures.')

    def search(self, key):
        query = self.variables[key].get().strip().casefold()
        self.pickers[key].configure(values=[label for label in self.choices[key] if query in label.casefold()])

    def resolve(self, key):
        value = self.variables[key].get().strip()
        return self.choices[key].get(value, value if value in self.choices[key].values() else None)

    def select_country(self, *_):
        self.country_id = None
        self.ids = []
        self.render()
        self.save_button.configure(state='disabled')
        cid = self.resolve('country')
        if self.index is None or cid is None:
            return
        try:
            self.ids = culture_ids(read_country(self.index, cid))
        except (OSError, ValueError) as exc:
            self.status.set(str(exc)); return
        self.country_id = cid
        self.render()
        self.save_button.configure(state='normal')
        self.status.set('Add or remove cultures, then click Save Primary Cultures.')

    def render(self):
        self.listbox.delete(0, 'end')
        for cid in self.ids:
            self.listbox.insert('end', self.labels.get(cid, f'{cid} (pending)'))

    def add(self):
        cid = self.resolve('culture')
        if self.country_id is None or cid is None:
            self.status.set('Select a nation and a culture from this save first.'); return
        if cid not in self.ids:
            self.ids.append(cid)
        self.render()

    def remove(self):
        selected = set(self.listbox.curselection())
        remaining = [cid for i, cid in enumerate(self.ids) if i not in selected]
        if not remaining:
            self.status.set('Keep at least one primary culture.'); return
        self.ids = remaining
        self.render()

    def save(self):
        if self.index is None or self.country_id is None:
            return
        try:
            backup = save_primary_cultures(self.index, self.country_id, self.ids)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Save Primary Cultures', str(exc)); return
        self.editor.select_latest_save()
        messagebox.showinfo('Primary Cultures Saved', f'Reload the save in-game. No backup created')
