"""Update persisted culture goods lists without changing other save data."""
from pathlib import Path
from datetime import datetime
import os
import re
import shutil
import tempfile
from mass_migration import entries, field, signature


def update_goods(text, values):
    for key in ('obsessions', 'taboos'):
        goods = values[key]
        if any(not re.fullmatch(r'[A-Za-z0-9_]+', good) for good in goods):
            raise ValueError('Invalid goods identifier.')
        encoded = '{ ' + ' '.join(dict.fromkeys(goods)) + ' }'
        span = field(text, key)
        if span:
            text = text[:span[0]] + encoded + text[span[1]:]
        else:
            end = text.rfind('}')
            newline = '\r\n' if '\r\n' in text else '\n'
            text = text[:end] + '\t' + key + '=' + encoded + newline + text[end:]
    return text


def apply_culture_goods(path, changes):
    path = Path(path)
    before = signature(path)
    edits, found = [], set()
    for section, ident, start, end, raw in entries(path):
        if section != 'cultures':
            continue
        text = raw.decode('utf-8')
        span = field(text, 'type')
        name = text[span[0]:span[1]].strip('"') if span else ''
        if name in changes:
            found.add(name)
            edits.append((start, end, update_goods(text, changes[name]).encode('utf-8')))
    if found != set(changes):
        raise ValueError('Cultures missing from save: ' + ', '.join(set(changes) - found))
    temporary = None
    try:
        with path.open('rb') as source, tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as target:
            temporary = target.name
            for start, end, data in sorted(edits):
                remaining = start - source.tell()
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk: raise ValueError('Save ended unexpectedly.')
                    target.write(chunk); remaining -= len(chunk)
                source.seek(end); target.write(data)
            shutil.copyfileobj(source, target)
        if signature(path) != before:
            raise ValueError('Save changed while preparing edit; nothing applied.')
        backup = path.with_name(path.name + '.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        shutil.copy2(path, backup)
        os.replace(temporary, path)
        return backup
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
