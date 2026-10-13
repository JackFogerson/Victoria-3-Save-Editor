"""Culture definition editing UI, separate from population save editing."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from autocomplete import LiveSuggestions
from culture_save import apply_culture_goods

from culture_definitions import (DEFAULT_CULTURE_FILE, attributes, catalog,
                                 definitions, replace_attributes, save_changes)


class CultureDefinitionTab(ttk.Frame):
    def __init__(self, notebook, names, on_saved=None, save_path=None):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='Culture Definitions')
        self.names = names
        self.on_saved = on_saved
        self.save_path = save_path
        self.original = None
        self.loaded_culture = None
        self.loaded_path = None
        self.path = tk.StringVar(value=str(DEFAULT_CULTURE_FILE))
        self.selection = tk.StringVar()
        self.status = tk.StringVar(value='Load a culture definitions file to begin.')
        self.fields = {key: tk.StringVar() for key in ('religion', 'language')}
        self.bundled = json.loads(Path(__file__).with_name('culture_catalog.json').read_text(encoding='utf-8'))
        self.ids = {name: str(i) for i, name in enumerate(self.bundled['cultures'])}
        ttk.Label(self, text='Edits game culture definitions globally; State ID does not apply.').pack(anchor='w')
        file_row = ttk.Frame(self)
        file_row.pack(fill='x', pady=6)
        ttk.Entry(file_row, textvariable=self.path, state='readonly').pack(side='left', fill='x', expand=True)
        ttk.Button(file_row, text='Browse…', command=self.browse).pack(side='left', padx=4)
        ttk.Button(file_row, text='Reload', command=self.load_file).pack(side='left')
        choose = ttk.Frame(self)
        choose.pack(fill='x', pady=5)
        ttk.Label(choose, text='Culture:').pack(side='left')
        self.picker = ttk.Combobox(choose, textvariable=self.selection, width=38, postcommand=self.filter_cultures)
        self.picker.pack(side='left', padx=5)
        self.picker.bind('<KeyRelease>', self.filter_cultures)
        self.suggestions = LiveSuggestions(self.picker, self.selection, self.filter_cultures)
        ttk.Button(choose, text='Load Culture', command=self.load_culture).pack(side='left')
        self.combos = {}
        for key in ('religion', 'language'):
            row = ttk.Frame(self)
            row.pack(fill='x', pady=3)
            ttk.Label(row, text=key.title() + ':', width=12).pack(side='left')
            combo = ttk.Combobox(row, textvariable=self.fields[key], state='readonly', width=42)
            combo.pack(side='left')
            self.combos[key] = combo
        ttk.Label(self, text='Select any number of goods. No selection clears that list.').pack(anchor='w', pady=(8, 2))
        goods_frame = ttk.Frame(self)
        goods_frame.pack(fill='both', expand=True)
        self.goods_lists = {}
        for key in ('obsessions', 'taboos'):
            frame = ttk.LabelFrame(goods_frame, text=key.title(), padding=5)
            frame.pack(side='left', fill='both', expand=True, padx=3)
            box = tk.Listbox(frame, selectmode='multiple', exportselection=False, height=7)
            scroll = ttk.Scrollbar(frame, orient='vertical', command=box.yview)
            box.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right', fill='y')
            box.pack(fill='both', expand=True)
            self.goods_lists[key] = box
        ttk.Label(self, textvariable=self.status, wraplength=720).pack(anchor='w', pady=5)
        self.save_button = ttk.Button(self, text='Save Culture Definition (creates backup)', command=self.save, state='disabled')
        self.save_button.pack(anchor='w')
        if save_path is not None:
            ttk.Button(self, text='Apply Obsessions/Taboos to Selected Save (creates backup)', command=self.apply_to_save).pack(anchor='w')
        ttk.Label(self, text='Existing campaigns store their own obsessions and taboos. Apply to the save, then reload it in-game.', wraplength=900).pack(anchor='w')
        if DEFAULT_CULTURE_FILE.is_file():
            self.load_file()

    def dirty(self):
        return self.loaded_culture is not None and self.current_values() != self.loaded_values

    def apply_to_save(self):
        if self.loaded_culture is None:
            return
        try:
            backup = apply_culture_goods(self.save_path(), {self.loaded_culture: self.current_values()})
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Update Save', str(exc)); return
        self.status.set(f'Updated {self.loaded_culture} obsessions/taboos in {backup.name.split(".v3")[0]}. Reload the save in-game. Backup created.')
        if self.on_saved: self.on_saved()

    def allow_discard(self):
        return not self.dirty() or messagebox.askyesno('Unsaved Culture Changes', 'Discard the unsaved culture definition changes?')

    def browse(self):
        if not self.allow_discard():
            return
        path = filedialog.askopenfilename(initialdir=str(DEFAULT_CULTURE_FILE.parent), filetypes=[('Culture definitions', '*.txt')])
        if path:
            self.path.set(path)
            self.load_file(discard_checked=True)

    def load_file(self, discard_checked=False):
        if not discard_checked and not self.allow_discard():
            return
        try:
            path = Path(self.path.get())
            original = path.read_bytes()
            text = original.decode('utf-8-sig')
            blocks = definitions(text)
            if not blocks or not any(attributes(block)['language'] for block in blocks.values()):
                raise ValueError('This does not appear to be a culture definitions file.')
            options = catalog(text)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Load Definitions', str(exc))
            if self.loaded_path:
                self.path.set(str(self.loaded_path))
            return
        self.original, self.text, self.blocks = original, text, blocks
        self.loaded_path = path
        self.options = options
        self.loaded_culture = None
        self.labels = {}
        for name in blocks:
            cid = self.ids.get(name)
            display = f'{cid} ({self.names.get(cid, name.replace("_", " "))}) — {name}' if cid is not None else name
            self.labels[display] = name
        self.selection.set('')
        self.filter_cultures()
        for variable in self.fields.values():
            variable.set('')
        for box in self.goods_lists.values():
            box.delete(0, 'end')
        self.save_button.configure(state='disabled')
        self.status.set(f'Loaded {len(blocks)} cultures. Search by ID or name, then click Load Culture.')

    def filter_cultures(self, event=None):
        query = self.selection.get().casefold().strip()
        self.picker.configure(values=[label for label in getattr(self, 'labels', {}) if query in label.casefold()])

    def load_culture(self):
        if self.original is None:
            return
        query = self.selection.get().strip()
        name = self.labels.get(query)
        if name is None:
            matches = [name for label, name in self.labels.items()
                       if query.casefold() in (name.casefold(), self.ids.get(name),
                                              self.names.get(self.ids.get(name), '').casefold())]
            if len(matches) == 1:
                name = matches[0]
        if name is None:
            messagebox.showerror('Choose Culture', 'Select a search result or enter an exact culture ID or name.')
            return
        if not self.allow_discard():
            return
        self.loaded_culture = name
        values = attributes(self.blocks[name])
        self.loaded_values = values
        for key, variable in self.fields.items():
            options = set(self.options[key + 's']) | set(self.bundled[key + 's'])
            options.add(values[key])
            self.combos[key].configure(values=sorted(options - {''}))
            variable.set(values[key])
        goods = sorted(set(self.options['goods']) | set(self.bundled['goods']) | set(values['obsessions']) | set(values['taboos']))
        for key, box in self.goods_lists.items():
            box.delete(0, 'end')
            for index, good in enumerate(goods):
                box.insert('end', good)
                if good in values[key]:
                    box.selection_set(index)
        # Compare list values in UI order, regardless of original file order.
        self.loaded_values = self.current_values()
        self.status.set(f'Editing: {name}. Save writes only this culture to {self.loaded_path.name}.')
        self.save_button.configure(state='normal')

    def current_values(self):
        values = {key: variable.get() for key, variable in self.fields.items()}
        values.update({key: [box.get(i) for i in box.curselection()] for key, box in self.goods_lists.items()})
        return values

    def save(self):
        if self.loaded_culture is None:
            return
        values = self.current_values()
        changes = {key: value for key, value in values.items() if value != self.loaded_values[key]}
        if not changes:
            self.status.set('No changes to save.')
            return
        try:
            updated = replace_attributes(self.text, self.loaded_culture, changes)
            encoded = updated.encode('utf-8')
            if self.original.startswith(b'\xef\xbb\xbf'):
                encoded = b'\xef\xbb\xbf' + encoded
            backup = save_changes(self.loaded_path, self.original, encoded)
        except PermissionError:
            messagebox.showerror('Write Access Required', 'Windows denied access to this file. Run the editor with permission to write to the game folder, or edit a writable copy. The culture file was not replaced.')
            return
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Save Definition', str(exc))
            return
        self.original, self.text = encoded, updated
        self.blocks = definitions(updated)
        self.options = catalog(updated)
        self.loaded_values = values
        self.status.set(f'Saved {self.loaded_culture}. Backup: {backup.name}')
        if self.on_saved: self.on_saved()

