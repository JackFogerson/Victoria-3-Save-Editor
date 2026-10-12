import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from culture_definitions import save_changes
from state_homelands import DEFAULT_STATE_FILE, resolve_state, history_states, homelands, replace_homelands


class HomelandTab(ttk.Frame):
    def __init__(self, notebook, editor, names):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='State Homelands')
        self.editor = editor
        self.region = None
        self.original = None
        self.path = tk.StringVar(value=str(DEFAULT_STATE_FILE))
        self.query = tk.StringVar()
        self.status = tk.StringVar(value='Select a text save and enter its State ID above, then load homelands.')
        keys = json.loads(Path(__file__).with_name('culture_catalog.json').read_text(encoding='utf-8'))['cultures']
        self.labels = {f'{i} ({names.get(str(i), key.replace("_", " "))}) — {key}': key for i, key in enumerate(keys)}
        self.ids = dict(enumerate(keys))
        self.names = names
        ttk.Label(self, text='Edit homeland history in 00_states.txt. These changes apply to new games.').pack(anchor='w')
        row = ttk.Frame(self)
        row.pack(fill='x', pady=8)
        ttk.Entry(row, textvariable=self.path, state='readonly').pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse…', command=self.browse).pack(side='left', padx=5)
        ttk.Button(self, text='Load Homelands for State ID', command=self.load).pack(anchor='w')
        ttk.Label(self, textvariable=self.status, wraplength=730).pack(anchor='w', pady=8)
        list_frame = ttk.Frame(self)
        list_frame.pack(fill='both', expand=True)
        self.list = tk.Listbox(list_frame, selectmode='extended', exportselection=False, height=8)
        scrollbar = ttk.Scrollbar(list_frame, command=self.list.yview)
        self.list.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.list.pack(fill='both', expand=True)
        row = ttk.Frame(self)
        row.pack(fill='x', pady=8)
        self.picker = ttk.Combobox(row, textvariable=self.query, width=42, postcommand=self.search)
        self.picker.pack(side='left')
        self.picker.bind('<KeyRelease>', self.search)
        ttk.Button(row, text='Add Homeland', command=self.add).pack(side='left', padx=5)
        ttk.Button(row, text='Remove Selected', command=self.remove).pack(side='left')
        self.save_button = ttk.Button(self, text='Save State Homelands (creates backup)', command=self.save, state='disabled')
        self.save_button.pack(anchor='w')
        self.search()

    def search(self, event=None):
        query = self.query.get().strip().casefold()
        self.picker.configure(values=[label for label in self.labels if query in label.casefold()])

    def dirty(self):
        return self.region is not None and self.current != self.initial

    def discard(self):
        return not self.dirty() or messagebox.askyesno('Unsaved Homelands', 'Discard unsaved homeland changes?')

    def browse(self):
        if not self.discard():
            return
        path = filedialog.askopenfilename(initialdir=str(DEFAULT_STATE_FILE.parent), filetypes=[('State history', '*.txt')])
        if path:
            self.path.set(path)
            self.region = None
            self.list.delete(0, 'end')
            self.save_button.configure(state='disabled')
            self.status.set('Click Load Homelands for State ID to read this file.')

    def load(self):
        if not self.discard():
            return
        try:
            save = self.editor.file_path.get()
            state_id = self.editor.state_id.get().strip()
            region = resolve_state(save, state_id)
            path = Path(self.path.get())
            original = path.read_bytes()
            text = original.decode('utf-8-sig')
            states = history_states(text)
            if region not in states:
                raise ValueError(f'{region} is not present in this history file.')
            values = homelands(states[region])
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Load Homelands', str(exc))
            return
        self.region, self.loaded_path = region, path
        self.original, self.text = original, text
        self.context = (save, state_id)
        self.current, self.initial = values, list(values)
        self.refresh()
        self.save_button.configure(state='normal')

    def refresh(self):
        self.list.delete(0, 'end')
        reverse = {key: label for label, key in self.labels.items()}
        for name in self.current:
            self.list.insert('end', reverse.get(name, name + ' (pending)'))
        self.status.set(f'State ID {self.context[1]} → {self.region}: {len(self.current)} homelands. Saving edits this history region, including all split-state portions.')

    def add(self):
        if self.region is None:
            messagebox.showerror('Load a State', 'Load the state homelands first.')
            return
        value = self.query.get().strip()
        name = self.labels.get(value)
        if name is None and value.isdecimal():
            name = self.ids.get(int(value))
            if name is None:
                messagebox.showerror('Unknown Culture ID', 'No verified culture key is known for this ID. Enter the game culture key instead.')
                return
        if name is None:
            matches = [key for i, key in self.ids.items() if value.casefold() in (key.casefold(), self.names.get(str(i), '').casefold())]
            name = matches[0] if len(matches) == 1 else value
        import re
        if not re.fullmatch(r'[A-Za-z_]\w*', name):
            messagebox.showerror('Invalid Culture', 'Select a culture result or enter a game culture key such as north_german.')
            return
        if name not in self.current:
            self.current.append(name)
            self.refresh()

    def remove(self):
        if self.region is not None:
            for index in reversed(self.list.curselection()):
                del self.current[index]
            self.refresh()

    def save(self):
        if self.region is None or not self.dirty():
            return
        if self.context != (self.editor.file_path.get(), self.editor.state_id.get().strip()):
            messagebox.showerror('State Selection Changed', 'Reload homelands for the newly selected save or State ID before saving.')
            return
        try:
            updated = replace_homelands(self.text, self.region, self.current)
            encoded = updated.encode('utf-8')
            if self.original.startswith(b'\xef\xbb\xbf'):
                encoded = b'\xef\xbb\xbf' + encoded
            backup = save_changes(self.loaded_path, self.original, encoded)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Cannot Save Homelands', f'{exc}\nThe game folder may require write permission. You can edit a writable copy using Browse.')
            return
        self.original, self.text = encoded, updated
        self.initial = list(self.current)
        self.status.set(f'Saved {self.region}. Backup: {backup.name}')
