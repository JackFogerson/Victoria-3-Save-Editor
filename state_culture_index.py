"""Background index of cultures actually present in a save's states."""
from collections import defaultdict
from pathlib import Path
import queue
import re
import threading
from shortage_estimator import database_blocks


def read_state_cultures(path):
    result = defaultdict(set)
    for text in database_blocks(path, 'pops'):
        state = re.search(r'^\s*location=(\d+)\s*$', text, re.M)
        culture = re.search(r'^\s*culture=(\w+)\s*$', text, re.M)
        sizes = re.findall(r'^\s*(?:workforce|dependents)=(\d+)\s*$', text, re.M)
        if state and culture and any(int(size) > 0 for size in sizes):
            result[str(int(state[1]))].add(culture[1])
    return dict(result)


class StateCultureIndex:
    def __init__(self, editor):
        self.editor = editor
        self.cache = None
        self.busy = False
        self.timer = None
        self.results = queue.Queue()
        editor.file_path.trace_add('write', self.changed)
        editor.state_id.trace_add('write', self.changed)

    def key(self):
        path = Path(self.editor.file_path.get()).resolve()
        stat = path.stat()
        if not path.is_file(): raise ValueError('Select a save.')
        return str(path), stat.st_mtime_ns, stat.st_size

    def changed(self, *args):
        self.editor.set_state_cultures(set())
        if self.timer is not None: self.editor.root.after_cancel(self.timer)
        self.timer = self.editor.root.after(400, self.load)

    def load(self):
        self.timer = None
        sid = self.editor.state_id.get().strip()
        if not sid.isdecimal(): return
        try: key = self.key()
        except (OSError, ValueError): return
        if self.cache and self.cache[0] == key:
            self.editor.set_state_cultures(self.cache[1].get(str(int(sid)), set()))
            return
        if self.busy: return
        self.busy = True
        def work():
            try: result = read_state_cultures(key[0])
            except (OSError, ValueError): result = None
            self.results.put((key, result))
        threading.Thread(target=work, daemon=True).start()
        self.editor.root.after(100, self.poll)

    def poll(self):
        try: key, result = self.results.get_nowait()
        except queue.Empty:
            self.editor.root.after(100, self.poll); return
        self.busy = False
        try: current = self.key()
        except (OSError, ValueError): return
        if current != key: self.load(); return
        if result is not None:
            self.cache = key, result
            self.load()
