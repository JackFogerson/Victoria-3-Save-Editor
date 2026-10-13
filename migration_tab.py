from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from autocomplete import LiveSuggestions
from mass_migration import index_save, create_migration


class MigrationTab(ttk.Frame):
    def __init__(self, notebook, editor, names):
        super().__init__(notebook, padding=10)
        notebook.add(self, text='Mass Migration')
        self.editor, self.names = editor, names
        self.index = None
        self.busy = False
        self.reload_requested = False
        self.results = queue.Queue()
        self.status = tk.StringVar(value='Select a save above. Migration choices load automatically.')
        self.days = tk.StringVar(value='1461')
        self.choices, self.variables, self.pickers, self.suggestions = {}, {}, {}, []
        ttk.Label(self, text='Create an active mass-migration event in the selected save. The game controls population movement.').pack(anchor='w', pady=5)
        ttk.Button(self, text='Load Migration Choices from Save', command=self.load).pack(anchor='w', pady=8)
        for key, label in [('culture', 'Migrating culture'), ('source', 'Source country'), ('destination', 'Destination state')]:
            row = ttk.Frame(self); row.pack(fill='x', pady=8)
            ttk.Label(row, text=label + ':', width=22).pack(side='left')
            variable = tk.StringVar(); self.variables[key] = variable; self.choices[key] = {}
            refresh = lambda k=key: self.search(k)
            picker = ttk.Combobox(row, textvariable=variable, width=65, postcommand=refresh)
            picker.pack(side='left', fill='x', expand=True)
            self.pickers[key] = picker
            self.suggestions.append(LiveSuggestions(picker, variable, refresh))
        row = ttk.Frame(self); row.pack(fill='x', pady=8)
        ttk.Label(row, text='Duration in days:', width=22).pack(side='left')
        ttk.Entry(row, textvariable=self.days, width=10).pack(side='left')
        ttk.Label(row, text='Starts on the save’s current game date. 1461 days is about four years.').pack(side='left', padx=8)
        ttk.Label(self, text='Experimental save event: reload the edited save and unpause to verify activation.\nExisting migrations are preserved; occupied destinations are rejected. No people are transferred instantly.\nUpdates the selected save without creating a backup.', wraplength=900).pack(anchor='w', pady=12)
        self.button = ttk.Button(self, text='Create Mass Migration in Save', command=self.create, state='disabled')
        self.button.pack(anchor='w', pady=8)
        ttk.Label(self, textvariable=self.status, wraplength=900).pack(anchor='w', pady=8)
        self.file_trace = editor.file_path.trace_add('write', self.save_changed)
        self.pending = self.after_idle(self.save_changed)
        self.bind('<Destroy>', self.cleanup, add='+')

    def cleanup(self, event):
        if event.widget == self:
            self.editor.file_path.trace_remove('write', self.file_trace)
            if self.pending is not None:
                self.after_cancel(self.pending)

    def cancel_pending(self):
        if self.pending is not None:
            self.after_cancel(self.pending)
            self.pending = None

    def save_changed(self, *_):
        if not self.busy:
            self.cancel_pending()
        self.index = None
        self.button.configure(state='disabled')
        for key in self.choices:
            self.choices[key] = {}
            self.variables[key].set('')
            self.search(key)
        if self.busy:
            self.reload_requested = True
        elif Path(self.editor.file_path.get()).is_file():
            self.load()

    def search(self, key):
        query = self.variables[key].get().strip().casefold()
        self.pickers[key].configure(values=[label for label in self.choices[key] if query in label.casefold()])

    def load(self):
        if self.busy: return
        path = self.editor.file_path.get()
        if not Path(path).is_file():
            messagebox.showerror('Select Save', 'Select a text save above first.'); return
        self.busy = True; self.button.configure(state='disabled')
        self.status.set('Reading countries, cultures, and states from the save…')
        def work():
            try: index, error = index_save(path), None
            except Exception as exc: index, error = None, str(exc)
            self.results.put((path, index, error))
        threading.Thread(target=work, daemon=True).start()
        self.pending = self.after(100, self.poll)

    def poll(self):
        self.pending = None
        try: path, index, error = self.results.get_nowait()
        except queue.Empty:
            self.pending = self.after(100, self.poll); return
        self.busy = False
        if self.reload_requested or path != self.editor.file_path.get():
            self.reload_requested = False
            self.save_changed()
            return
        if error:
            self.status.set('Could not load migration choices: ' + error); return
        self.populate(index)

    def populate(self, index):
        self.index = index
        self.choices['culture'] = {f'{cid} ({self.names.get(cid, item["name"].replace("_", " "))}) — {item["name"]}': cid for cid, item in index['cultures'].items()}
        self.choices['source'] = {f'{cid} ({item["name"]})': cid for cid, item in index['countries'].items()}
        self.choices['destination'] = {f'{sid} ({item["name"].removeprefix("STATE_").replace("_", " ").title()}) — {index["countries"].get(item["country"], {}).get("name", item["country"])}': sid for sid, item in index['states'].items()}
        for key in self.choices:
            self.search(key)
        current = self.editor.state_id.get().strip()
        for label, sid in self.choices['destination'].items():
            if sid == current and not self.variables['destination'].get():
                self.variables['destination'].set(label); break
        for suggestion in self.suggestions:
            suggestion.show()
        self.button.configure(state='normal')
        self.status.set(f'Loaded {Path(index["path"]).name}, dated {index["date"]}. Choose a culture, origin country, and destination.')

    def resolve(self, key):
        text = self.variables[key].get().strip()
        if text in self.choices[key]: return self.choices[key][text]
        if text in self.choices[key].values(): return text
        raise ValueError(f'Select a {key} search result or enter its numeric save ID.')

    def create(self):
        if self.index is None: return
        try:
            if str(Path(self.editor.file_path.get()).resolve()) != self.index['path']:
                raise ValueError('Selected save changed. Load its migration choices first.')
            culture, source, destination = (self.resolve(key) for key in ('culture', 'source', 'destination'))
            days = int(self.days.get())
            expiry = create_migration(self.index, culture, source, destination, days)
        except (OSError, ValueError, OverflowError) as exc:
            messagebox.showerror('Cannot Create Migration', str(exc)); return
        self.button.configure(state='disabled')
        self.editor.shortage_autofill.cache = None
        self.editor.state_culture_index.changed()
        self.editor.select_latest_save()
        messagebox.showinfo('Migration Created', f'Created migration to State {destination}, expiring {expiry}. No backup was created. Reload the save in-game to verify.')
