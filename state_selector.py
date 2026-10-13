"""Save-state suggestions keep display labels separate from numeric IDs."""
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk
from autocomplete import LiveSuggestions
from shortage_estimator import database_blocks


def state_labels(path):
    labels = {}
    for text in database_blocks(path, 'states'):
        sid = text.split('=')[0].strip()
        region = re.search(r'^\s*region="?(STATE_\w+)"?\s*$', text, re.M)
        if region:
            name = region[1].removeprefix('STATE_').replace('_', ' ').title()
            labels[sid] = f'{sid} ({name})'
    return labels


def newest_save(folder):
    files = [path for path in Path(folder).glob('*.v3') if path.is_file()]
    return max(files, key=lambda path: (path.stat().st_mtime_ns, path.name)) if files else None


class StateSelector(ttk.Combobox):
    def __init__(self, parent, editor):
        self.editor = editor
        self.display = tk.StringVar()
        self.labels = {}
        self.lock = False
        self.timer = None
        self.busy = False
        self.results = queue.Queue()
        super().__init__(parent, textvariable=self.display, width=30, postcommand=self.refresh)
        self.suggestions = LiveSuggestions(self, self.display, self.refresh)
        self.display.trace_add('write', self.display_changed)
        editor.state_id.trace_add('write', self.id_changed)
        editor.file_path.trace_add('write', self.file_changed)

    def display_changed(self, *args):
        if self.lock: return
        match = re.fullmatch(r'\s*(\d+)(?:\s*\([^\n]*\))?\s*', self.display.get())
        self.lock = True
        try: self.editor.state_id.set(str(int(match[1])) if match else '')
        finally: self.lock = False

    def id_changed(self, *args):
        if self.lock: return
        self.lock = True
        try:
            sid = self.editor.state_id.get()
            self.display.set(self.labels.get(sid, sid))
        finally: self.lock = False

    def refresh(self):
        query = self.display.get().casefold().strip()
        self.configure(values=[label for label in self.labels.values() if query in label.casefold()])

    def key(self):
        path = Path(self.editor.file_path.get()).resolve(); stat = path.stat()
        if not path.is_file(): raise ValueError('Select a save.')
        return str(path), stat.st_size, stat.st_mtime_ns

    def file_changed(self, *args):
        self.labels = {}; self.suggestions.hide(); self.refresh()
        self.id_changed()
        if self.timer is not None: self.after_cancel(self.timer)
        self.timer = self.after(400, self.load)

    def load(self):
        self.timer = None
        if self.busy: return
        try: key = self.key()
        except (OSError, ValueError): return
        self.busy = True
        def work():
            try: labels = state_labels(key[0])
            except (OSError, ValueError): labels = {}
            self.results.put((key, labels))
        threading.Thread(target=work, daemon=True).start()
        self.after(100, self.poll)

    def poll(self):
        try: key, labels = self.results.get_nowait()
        except queue.Empty:
            self.after(100, self.poll); return
        self.busy = False
        try: current = self.key()
        except (OSError, ValueError): return
        if current != key: self.load(); return
        self.labels = labels; self.refresh()
        # Do not interrupt a name search that the user is typing.
        if self.editor.state_id.get(): self.id_changed()
