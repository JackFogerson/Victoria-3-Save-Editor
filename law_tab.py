from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from autocomplete import LiveSuggestions
from culture_definitions import save_changes
from law_editor import DEFAULT_LAWS, scan_laws, law_values, validate_effect, replace_law, institution_base


class LawTab(ttk.Frame):
    def __init__(self, notebook, on_saved=None):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='Laws')
        self.loaded = None
        self.on_saved = on_saved
        self.folder = tk.StringVar(value=str(DEFAULT_LAWS))
        self.query = tk.StringVar()
        self.effect = tk.StringVar()
        self.value = tk.StringVar()
        self.status = tk.StringVar(value='Choose a law to edit its effects.')
        self.labels, self.options = {}, []
        ttk.Label(self, text='Edit law effects for every country using the law. Save creates a backup.').pack(anchor='w')
        row = ttk.Frame(self); row.pack(fill='x', pady=5)
        ttk.Entry(row, textvariable=self.folder, state='readonly').pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse Folder…', command=self.browse).pack(side='left')
        ttk.Button(row, text='Reload', command=self.load_folder).pack(side='left')
        row = ttk.Frame(self); row.pack(fill='x', pady=5)
        ttk.Label(row, text='Law:').pack(side='left')
        self.picker = ttk.Combobox(row, textvariable=self.query, width=65, postcommand=self.search_laws)
        self.picker.pack(side='left', padx=5)
        self.picker.bind('<<ComboboxSelected>>', self.select_law)
        self.picker.bind('<Return>', self.select_law)
        self.law_suggestions = LiveSuggestions(self.picker, self.query, self.search_laws)
        inner = ttk.Notebook(self); inner.pack(fill='both', expand=True)
        regular = ttk.Frame(inner, padding=5); inner.add(regular, text='Ongoing Effects')
        self.scope = tk.StringVar(value='Law effects')
        scope_picker = ttk.Combobox(regular, textvariable=self.scope, state='readonly', values=('Law effects', 'Institution effects per level'))
        scope_picker.pack(anchor='w', fill='x')
        scope_picker.bind('<<ComboboxSelected>>', self.change_scope)
        self.institution_info = tk.StringVar()
        ttk.Label(regular, textvariable=self.institution_info, wraplength=880).pack(anchor='w')
        frame = ttk.Frame(regular); frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=('value',), height=7, selectmode='browse')
        self.tree.heading('#0', text='Consequence / modifier'); self.tree.heading('value', text='Value')
        self.tree.column('#0', width=420); self.tree.column('value', width=100)
        scroll = ttk.Scrollbar(frame, command=self.tree.yview); scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scroll.set); self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.select_effect)
        row = ttk.Frame(regular); row.pack(fill='x', pady=5)
        self.effect_picker = ttk.Combobox(row, textvariable=self.effect, width=48, postcommand=self.search_effects)
        self.effect_picker.pack(side='left')
        self.effect_suggestions = LiveSuggestions(self.effect_picker, self.effect, self.search_effects)
        ttk.Entry(row, textvariable=self.value, width=10).pack(side='left', padx=4)
        ttk.Button(row, text='Add / Update', command=self.add).pack(side='left')
        ttk.Button(row, text='Remove Selected', command=self.remove).pack(side='left', padx=4)
        ttk.Label(regular, text='Choose an effect, enter its value, then Add / Update. Numbers or yes/no; percentage modifiers use 0.1 for 10%.').pack(anchor='w')
        self.scripts = {}
        for key, title in [('on_activate', 'On Enactment (script)'), ('on_deactivate', 'On Removal (script)')]:
            frame = ttk.Frame(inner, padding=5); inner.add(frame, text=title)
            ttk.Label(frame, text='Advanced: edit the game effect script. Enactment/removal effects are not replayed just by saving this file.').pack(anchor='w')
            text = tk.Text(frame, height=10, wrap='none', undo=True)
            scroll = ttk.Scrollbar(frame, command=text.yview); scroll.pack(side='right', fill='y')
            text.configure(yscrollcommand=scroll.set); text.pack(fill='both', expand=True)
            self.scripts[key] = text
        ttk.Label(self, textvariable=self.status, wraplength=900).pack(anchor='w', pady=4)
        ttk.Label(self, text='After saving game definitions, fully exit and restart Victoria 3, then load your save.\nQualifications modifiers change qualification gain; they do not instantly create qualified workers.', wraplength=900).pack(anchor='w')
        self.save_button = ttk.Button(self, text='Save Law Effects (creates backup)', command=self.save, state='disabled')
        self.save_button.pack(anchor='w')
        if DEFAULT_LAWS.is_dir(): self.load_folder()

    def values(self):
        return {'modifier': dict(self.modifiers), 'institution_modifier': dict(self.institution_modifiers), **{key: box.get('1.0', 'end-1c') for key, box in self.scripts.items()}}

    def active_modifiers(self):
        return self.modifiers if self.scope.get() == 'Law effects' else self.institution_modifiers

    def change_scope(self, event=None):
        self.effect.set(''); self.value.set(''); self.refresh()

    def discard(self):
        return self.loaded is None or self.values() == self.initial or messagebox.askyesno('Unsaved Law Changes', 'Discard unsaved changes to this law?')

    def browse(self):
        if not self.discard(): return
        folder = filedialog.askdirectory(initialdir=self.folder.get())
        if folder:
            self.folder.set(folder); self.load_folder(checked=True)

    def load_folder(self, checked=False):
        if not checked and not self.discard(): return
        try: laws, options = scan_laws(self.folder.get())
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Load Laws', str(exc)); return
        self.laws, self.options = laws, options
        self.labels = {name.removeprefix('law_').replace('_', ' ').title() + ' (' + name + ')': name for name in sorted(laws)}
        self.loaded = None; self.query.set(''); self.search_laws()
        self.modifiers = {}; self.institution_modifiers = {}; self.refresh()
        self.institution_info.set('')
        for box in self.scripts.values(): box.delete('1.0', 'end')
        self.save_button.configure(state='disabled')
        self.status.set(f'{len(laws)} laws loaded. Select one to view its consequences.')

    def search_laws(self):
        query = self.query.get().casefold()
        self.picker.configure(values=[label for label in self.labels if query in label.casefold()])

    def search_effects(self):
        query = self.effect.get().casefold()
        self.effect_picker.configure(values=[name for name in self.options if query in name.casefold()])

    def select_law(self, event=None):
        query = self.query.get()
        name = self.labels.get(query, query if query in getattr(self, 'laws', {}) else None)
        if name is None: return
        if not self.discard():
            self.query.set(next(label for label, key in self.labels.items() if key == self.loaded)); return
        try:
            path = self.laws[name]; original = path.read_bytes(); text = original.decode('utf-8-sig')
            values = law_values(text, name)
            institution, base = institution_base(self.folder.get(), text, name)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Load Law', str(exc)); return
        self.loaded, self.path, self.original, self.text = name, path, original, text
        self.modifiers = values['modifier']
        self.institution_modifiers = values['institution_modifier']
        self.scope.set('Institution effects per level' if institution else 'Law effects')
        self.institution_info.set((institution + ': base per level: ' + (', '.join(f'{k} = {v}' for k, v in base.items()) or 'none') + '\nEntries below add to the base for this law only (e.g. base 0.2 plus 0.1 = 0.3 per level).') if institution else 'This law does not enable an institution. Use Law effects for ongoing modifiers.')
        for key, box in self.scripts.items():
            box.delete('1.0', 'end'); box.insert('1.0', values[key])
        self.initial = self.values(); self.effect.set(''); self.value.set(''); self.refresh()
        self.save_button.configure(state='normal'); self.status.set(f'Editing {name} — {path.name}')

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for key, value in self.active_modifiers().items(): self.tree.insert('', 'end', iid=key, text=key, values=(value,))

    def select_effect(self, event=None):
        if self.tree.selection():
            key = self.tree.selection()[0]; self.effect.set(key); self.value.set(self.active_modifiers()[key])

    def add(self):
        if self.loaded is None: return
        key, value = self.effect.get().strip(), self.value.get().strip()
        try: value = validate_effect(key, value)
        except ValueError as exc:
            messagebox.showerror('Invalid Effect', str(exc)); return
        if self.scope.get() != 'Law effects' and not institution_base(self.folder.get(), self.text, self.loaded)[0]:
            messagebox.showerror('No Institution', 'This law does not enable an institution. Choose Law effects.'); return
        self.active_modifiers()[key] = value; self.refresh()

    def remove(self):
        if self.loaded and self.tree.selection():
            del self.active_modifiers()[self.tree.selection()[0]]; self.refresh()

    def save(self):
        if self.loaded is None: return
        try:
            values = self.values()
            if values == self.initial: self.status.set('No changes to save.'); return
            text = replace_law(self.text, self.loaded, values)
            data = (b'\xef\xbb\xbf' if self.original.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')
            backup = save_changes(self.path, self.original, data)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Save Law', str(exc)); return
        self.text, self.original = text, data
        saved = law_values(text, self.loaded)
        self.modifiers = saved['modifier']
        self.institution_modifiers = saved['institution_modifier']
        self.initial = self.values()
        self.refresh()
        self.status.set(f'Saved {self.loaded}. Restart Victoria 3 and load your save. Backup: {backup.name}')
        if self.on_saved: self.on_saved()
