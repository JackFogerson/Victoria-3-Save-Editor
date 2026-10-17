"""Retry transient Windows file locks without repeating an edit."""
import os
import shutil
import time
from mass_migration import signature


def commit_save(temporary, path, expected, backup=None):
    def retry(operation):
        for attempt in range(21):
            if signature(path) != expected:
                raise ValueError('Save changed while editing; reload it before applying changes.')
            try:
                return operation()
            except PermissionError:
                if attempt == 20:
                    raise PermissionError('Save is still locked or not writable. Wait for the game to finish saving, then try again.') from None
                time.sleep(0.25)
    # Backups are opt-in for explicit callers, never automatic UI saves.
    if backup is not None:
        retry(lambda: shutil.copy2(path, backup))
    retry(lambda: os.replace(temporary, path))
