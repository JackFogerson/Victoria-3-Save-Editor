"""Simultaneous per-state editing backed by one cached save scan."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from autocomplete import LiveSuggestions
from batch_states import load_batch, apply_batch
from mass_migration import signature


class StateCard(ttk.LabelFrame):
    def __init__(self, parent, owner, sid):
        self.owner, self.sid = owner, sid
        self.data = owner.snapshot['states'][sid]
        super().__init__(parent, text=f'{sid} — {self.data["region"].removeprefix("STATE_").replace("_", " ").title()}', padding=8)
        self.pack(fill='x', padx=6, pady=6)
        self.current_homelands = list(self.data['homelands'])
        self.percentages, self.conversions, self.religions, self.workforce = {}, {}, {}, {}
        self.suggestions = []
        ttk.Button(self, text='Remove state from batch', command=lambda: owner.remove(sid)).pack(anchor='e')
        homeland = ttk.Frame(self); homeland.pack(fill='x', pady=4)
        ttk.Label(homeland, text='Homelands', width=14).pack(side='left')
        self.homelands = tk.Listbox(homeland, height=3, selectmode='extended', exportselection=False, width=35)
        self.homelands.pack(side='left')
        self.homeland_query = tk.StringVar()
        self.combo(homeland, self.homeland_query, list(owner.culture_labels), width=26).pack(side='left', padx=4)
        ttk.Button(homeland, text='Add', command=self.add_homeland).pack(side='left')
        ttk.Button(homeland, text='Remove', command=self.remove_homeland).pack(side='left', padx=4)
        self.refresh_homelands()
        frame = ttk.LabelFrame(self, text='Culture populations — blank conversion keeps the culture', padding=4)
        frame.pack(fill='x', pady=4)
        for col, title in enumerate(('Current culture', 'Population', 'Change %', 'Convert to')):
            ttk.Label(frame, text=title).grid(row=0, column=col, sticky='w', padx=5)
        for row, (cid, count) in enumerate(self.data['cultures'].items(), 1):
            ttk.Label(frame, text=owner.culture_label(cid)).grid(row=row, column=0, sticky='w', padx=5)
            ttk.Label(frame, text=f'{count:,}').grid(row=row, column=1, sticky='w', padx=5)
            percent = tk.StringVar(value='0'); self.percentages[cid] = percent
            ttk.Entry(frame, textvariable=percent, width=8).grid(row=row, column=2, padx=5)
            target = tk.StringVar(); self.conversions[cid] = target
            self.combo(frame, target, list(owner.culture_labels), width=28).grid(row=row, column=3, sticky='ew', padx=5)
        frame.columnconfigure(3, weight=1)
        frame = ttk.LabelFrame(self, text='Religion conversions — blank keeps the religion', padding=4); frame.pack(fill='x', pady=4)
        for row, (religion, count) in enumerate(self.data['religions'].items()):
            ttk.Label(frame, text=f'{religion} ({count:,})', width=35).grid(row=row, column=0, sticky='w')
            target = tk.StringVar(); self.religions[religion] = target
            self.combo(frame, target, owner.religion_options, width=30).grid(row=row, column=1, sticky='ew')
        frame.columnconfigure(1, weight=1)
        frame = ttk.LabelFrame(self, text='Workforce additions — total workers per profession', padding=4); frame.pack(fill='x', pady=4)
        all_jobs = {'laborers', 'machinists', 'engineers', 'farmers', 'clergymen', 'clerks', 'officers', 'bureaucrats', 'aristocrats', 'capitalists', 'shopkeepers', 'academics', 'soldiers', 'peasants', 'slaves'}
        all_jobs.update(job for state in owner.snapshot['states'].values() for job in state['jobs'])
        for i, job in enumerate(sorted(all_jobs)):
            variable = tk.StringVar(value='0'); self.workforce[job] = variable
            ttk.Label(frame, text=job + (' *' if job not in self.data['jobs'] else '')).grid(row=i // 4, column=(i % 4) * 2, sticky='w', padx=3)
            ttk.Entry(frame, textvariable=variable, width=8).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=3)
        ttk.Label(frame, text='* No existing workforce population in this state; additions are skipped for that profession.').grid(row=(len(all_jobs)+3)//4, column=0, columnspan=8, sticky='w', pady=4)

    def combo(self, parent, variable, choices, **kwargs):
        widget = ttk.Combobox(parent, textvariable=variable, **kwargs)
        def refresh(): widget.configure(values=[v for v in choices if variable.get().casefold().strip() in v.casefold()])
        widget.configure(postcommand=refresh)
        self.suggestions.append(LiveSuggestions(widget, variable, refresh))
        refresh()
        return widget

    def refresh_homelands(self):
        self.homelands.delete(0, 'end')
        for cid in self.current_homelands: self.homelands.insert('end', self.owner.culture_label(cid))

    def add_homeland(self):
        if self.owner.busy: return
        try: cid = self.owner.resolve_culture(self.homeland_query.get())
        except ValueError as exc: messagebox.showerror('Choose Culture', str(exc)); return
        if cid not in self.current_homelands: self.current_homelands.append(cid)
        self.refresh_homelands()

    def remove_homeland(self):
        if self.owner.busy: return
        for i in reversed(self.homelands.curselection()): del self.current_homelands[i]
        self.refresh_homelands()

    def plan(self):
        result = {'percentages': {cid: var.get().strip() or '0' for cid, var in self.percentages.items()},
                  'cultures': {cid: self.owner.resolve_culture(var.get()) for cid, var in self.conversions.items() if var.get().strip()},
                  'religions': {r: var.get().strip() for r, var in self.religions.items() if var.get().strip()},
                  'workforce': {job: var.get().strip() or '0' for job, var in self.workforce.items()}}
        if set(self.current_homelands) != set(self.data['homelands']): result['homelands'] = list(self.current_homelands)
        return result


class BatchTab(ttk.Frame):
    def __init__(self, notebook, editor):
        super().__init__(notebook, padding=8)
        notebook.add(self, text='Batch States'); notebook.insert(0, self)
        self.editor, self.snapshot = editor, None
        self.cards, self.state_labels, self.culture_labels = {}, {}, {}
        self.busy = False; self.results = queue.Queue(); self.pending = None
        self.query = tk.StringVar()
        self.status = tk.StringVar(value='Load the selected save once, then add several states below. Automatic backups are off.')
        ttk.Label(self, text='Edit each state independently. All queued changes apply together in one save write.').pack(anchor='w')
        ttk.Label(self, text='Order: culture percentage (workers + dependents), workforce additions, then culture/religion conversions.\nHomelands are shared across split-state portions; conflicting lists are rejected.', wraplength=950).pack(anchor='w')
        row = ttk.Frame(self); row.pack(fill='x', pady=6)
        self.load_button = ttk.Button(row, text='Start Fresh / Load Save', command=self.load); self.load_button.pack(side='left')
        self.picker = ttk.Combobox(row, textvariable=self.query, width=35, postcommand=self.search); self.picker.pack(side='left', padx=6)
        self.suggestions = LiveSuggestions(self.picker, self.query, self.search)
        self.add_button = ttk.Button(row, text='Add State', command=self.add); self.add_button.pack(side='left')
        self.apply_button = ttk.Button(row, text='Apply All State Changes', command=self.apply); self.apply_button.pack(side='right')
        ttk.Label(self, textvariable=self.status, wraplength=950).pack(anchor='w', pady=4)
        area = ttk.Frame(self); area.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(area, highlightthickness=0)
        scrollbar = ttk.Scrollbar(area, orient='vertical', command=self.canvas.yview)
        scrollbar.pack(side='right', fill='y'); self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.trace = editor.file_path.trace_add('write', self.file_changed)
        self.bind('<Destroy>', self.cleanup, add='+')

    def cleanup(self, event):
        if event.widget == self:
            self.editor.file_path.trace_remove('write', self.trace)
            if self.pending is not None: self.after_cancel(self.pending)

    def file_changed(self, *_):
        if self.snapshot is not None:
            self.status.set('Selected save changed or refreshed. Start Fresh / Load Save before applying this batch.')
            self.apply_button.configure(state='disabled')

    def culture_label(self, cid):
        item = self.snapshot['cultures'].get(cid)
        return f'{cid} ({item["key"].replace("_", " ") if item else "pending"})'

    def resolve_culture(self, text):
        text = text.strip()
        if text in self.culture_labels: return self.culture_labels[text]
        if text in self.snapshot['cultures']: return text
        matches = [cid for cid, item in self.snapshot['cultures'].items() if item['key'].casefold() == text.casefold()]
        if len(matches) == 1: return matches[0]
        raise ValueError('Choose a culture result or enter its numeric save ID.')

    def search(self):
        query = self.query.get().strip().casefold()
        self.picker.configure(values=[label for label in self.state_labels if query in label.casefold()])

    def clear_cards(self):
        for card in self.cards.values(): card.destroy()
        self.cards.clear()

    def load(self):
        if self.busy: return
        if self.cards and not messagebox.askyesno('Start Fresh', 'Discard the queued state edits and reload the selected save?'): return
        path = self.editor.file_path.get()
        if not Path(path).is_file(): messagebox.showerror('Select Save', 'Select a text save above.'); return
        self.run('load', path, lambda: load_batch(path))

    def set_busy(self, busy):
        self.busy = busy
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Entry, ttk.Combobox, tk.Listbox)):
                    child.configure(state='disabled' if busy else 'normal')
                walk(child)
        walk(self)

    def run(self, action, path, function):
        self.set_busy(True)
        self.status.set('Scanning the save once for all states…' if action == 'load' else 'Applying all queued state edits in one write…')
        def worker():
            try: result, error = function(), None
            except Exception as exc: result, error = None, str(exc)
            self.results.put((action, path, result, error))
        threading.Thread(target=worker, daemon=True).start()
        self.pending = self.after(100, self.poll)

    def poll(self):
        self.pending = None
        try: action, path, result, error = self.results.get_nowait()
        except queue.Empty: self.pending = self.after(100, self.poll); return
        self.set_busy(False)
        if error:
            self.status.set('Batch not applied: ' + error); return
        if action == 'load':
            if Path(path).resolve() != Path(self.editor.file_path.get()).resolve():
                self.status.set('Save selection changed during loading. Load again.'); return
            self.clear_cards(); self.snapshot = result
            self.state_labels = {f'{sid} ({s["region"].removeprefix("STATE_").replace("_", " ").title()})': sid for sid, s in result['states'].items()}
            self.culture_labels = {self.culture_label(cid): cid for cid in result['cultures']}
            self.religion_options = sorted({r for state in result['states'].values() for r in state['religions']})
            self.query.set(''); self.search()
            self.status.set(f'Loaded {Path(path).name}. Add states by ID or name; each gets its own editable panel.')
        else:
            summary = f'Applied {result["records"]} record changes, including {result["populations"]} populations. No backup created.'
            if result['skipped']: summary += ' Skipped: ' + ', '.join(result['skipped'])
            if result['records']:
                self.clear_cards(); self.snapshot = None
                self.editor.shortage_autofill.cache = None
                self.editor.state_culture_index.changed()
                self.editor.select_latest_save()
                summary += ' Reload the save in-game. Start Fresh to prepare another batch.'
            self.status.set(summary)

    def add(self):
        if self.busy or self.snapshot is None: return
        value = self.query.get().strip()
        sid = self.state_labels.get(value, value)
        if sid not in self.snapshot['states']:
            messagebox.showerror('Choose State', 'Choose a result or enter its numeric save State ID.'); return
        if sid not in self.cards: self.cards[sid] = StateCard(self.body, self, sid)
        self.query.set('')

    def remove(self, sid):
        if not self.busy: self.cards.pop(sid).destroy()

    def apply(self):
        if self.busy or self.snapshot is None: return
        try:
            if Path(self.editor.file_path.get()).resolve() != Path(self.snapshot['path']):
                raise ValueError('Selected save changed. Reload the batch.')
            if signature(self.snapshot['path']) != self.snapshot['signature']:
                raise ValueError('Save changed since loading. Reload the batch.')
            plans = {sid: card.plan() for sid, card in self.cards.items()}
        except (OSError, ValueError) as exc: messagebox.showerror('Cannot Apply Batch', str(exc)); return
        snapshot = self.snapshot
        self.run('apply', snapshot['path'], lambda: apply_batch(snapshot, plans))
