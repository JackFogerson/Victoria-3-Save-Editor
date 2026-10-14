"""Debounced background estimation; all Tk access stays on the UI thread."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk
from shortage_estimator import DEFAULT_GAME, estimate


class ShortageAutofill:
    def __init__(self, editor, parent):
        self.editor, self.root = editor, editor.root
        self.enabled = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value='Select a save and enter a State ID to autofill estimated shortfalls.')
        self.cache = None
        self.busy = False
        self.timer = None
        self.results = queue.Queue()
        self.revision = 0
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=4)
        ttk.Checkbutton(row, text='Autofill estimated qualification shortfalls', variable=self.enabled, command=self.changed).pack(side='left')
        ttk.Button(row, text='Recalculate', command=self.recalculate).pack(side='right')
        ttk.Label(parent, textvariable=self.status, wraplength=730).pack(anchor='w', pady=(0, 5))
        editor.state_id.trace_add('write', self.changed)
        editor.file_path.trace_add('write', self.changed)
        for variable in editor.job_inputs.values():
            variable.trace_add('write', self.edited)

    def edited(self, *args):
        self.revision += 1

    def key(self):
        path = Path(self.editor.file_path.get()).resolve()
        stat = path.stat()
        if not path.is_file(): raise ValueError('Select a save file.')
        methods = DEFAULT_GAME / 'common/production_methods'
        if not methods.is_dir(): raise ValueError('Game production-method folder not found.')
        return (str(path), stat.st_mtime_ns, stat.st_size,
                tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(methods.glob('*.txt'))))

    def changed(self, *args):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if not self.enabled.get():
            self.status.set('Automatic estimates off. Workforce amounts remain editable.')
            return
        for variable in self.editor.job_inputs.values(): variable.set('0')
        self.status.set('Waiting for a valid save and State ID…')
        self.timer = self.root.after(500, self.start)

    def recalculate(self):
        self.cache = None
        self.changed()

    def start(self):
        self.timer = None
        if not self.enabled.get(): return
        sid = self.editor.state_id.get().strip()
        if not sid.isdecimal(): return
        sid = str(int(sid))
        try:
            key = self.key()
        except (OSError, ValueError) as exc:
            self.status.set(str(exc)); return
        if self.cache is not None and self.cache[0] == key:
            self.fill(self.cache[1], sid); return
        if self.busy:
            self.status.set('Calculating shortfalls… the latest State ID will be used.')
            return
        self.busy = True
        self.status.set('Calculating estimated shortfalls… you can keep using the editor.')
        revision = self.revision
        def work():
            try: result, error = estimate(key[0]), None
            except Exception as exc: result, error = None, str(exc)
            self.results.put((key, revision, result, error))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(100, self.poll)

    def poll(self):
        try: key, revision, result, error = self.results.get_nowait()
        except queue.Empty:
            self.root.after(100, self.poll); return
        self.busy = False
        if not self.enabled.get(): return
        try: current_key = self.key()
        except (OSError, ValueError): return
        if key != current_key:
            self.start(); return
        if error:
            self.status.set('Could not estimate shortfalls: ' + error); return
        self.cache = (key, result)
        if revision != self.revision:
            # A changed State ID clears inputs itself; manual changes stay intact.
            if any(v.get().strip() not in ('', '0') for v in self.editor.job_inputs.values()):
                self.status.set('Estimate ready. Kept your edited amounts; Recalculate to autofill.'); return
        sid = self.editor.state_id.get().strip()
        if sid.isdecimal(): self.fill(result, str(int(sid)))

    def fill(self, result, sid):
        if sid not in result['state_names']:
            self.status.set(f'State ID {sid} is not present in this save.'); return
        reasons = list(result['warnings'].get(sid, []))
        if sid in result['states_without_qualification_cache']:
            reasons.append('This state has no cached qualification totals.')
        unmapped = result.get('state_unmapped_professions', {}).get(sid, []) if 'state_unmapped_professions' in result else result['unmapped_professions']
        if unmapped:
            reasons.append('Could not verify profession IDs against the save’s cached workforce totals: '
                           + ', '.join(unmapped) + '. The mapping is ambiguous; automatic filling would be unreliable.')
        if reasons:
            self.status.set('Automatic fill skipped: ' + ' '.join(reasons)); return
        amounts = {row['profession']: row['estimated_shortage'] for row in result['rows'] if row['state_id'] == sid}
        skipped = {}
        if 'workforce_pop_jobs' in result:
            existing = set(result['workforce_pop_jobs'].get(sid, []))
            skipped = {job: amount for job, amount in amounts.items() if job not in existing}
            amounts = {job: amount for job, amount in amounts.items() if job in existing}
        for job, variable in self.editor.job_inputs.items():
            variable.set(str(amounts.get('soldiers' if job == 'servicemen' else job, 0)))
        region = result['state_names'][sid].removeprefix('STATE_').replace('_', ' ').title()
        total = sum(amounts.values())
        self.status.set(f'{region}: filled {total:,} estimated workers to add (vacancies minus available qualifications). Review before Apply.' if total else f'{region}: no estimated qualification shortfall. Workforce additions set to 0.')
        if skipped:
            self.status.set(f'{region}: filled {total:,} estimated workers. Skipped professions with no existing workforce populations: ' + ', '.join(f'{job} ({amount:,})' for job, amount in skipped.items()) + '.')
