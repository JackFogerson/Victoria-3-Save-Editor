"""Homelands in a campaign are culture core_states lists."""
from pathlib import Path
from datetime import datetime
import os
import re
import shutil
import tempfile
from mass_migration import index_save, field, signature


def cores(text):
    span = field(text, 'core_states')
    if span is None:
        return []
    value = text[span[0]:span[1]]
    if not re.fullmatch(r'\{[\sA-Za-z0-9_"]*\}', value):
        raise ValueError('Unsupported core_states format.')
    return [token.strip('"') for token in value[1:-1].split()]


def load_homelands(path, state_id):
    index = index_save(path)
    if state_id not in index['states']:
        raise ValueError('State ID is not present in this save.')
    region = index['states'][state_id]['name']
    records, current = {}, []
    with Path(path).open('rb') as handle:
        for cid, item in index['cultures'].items():
            start, end = item['span']
            handle.seek(start)
            text = handle.read(end - start).decode('utf-8')
            name = item['name']
            if name in records:
                raise ValueError('Duplicate culture key in save: ' + name)
            records[name] = (start, end, text, cid)
            if region in cores(text): current.append(name)
    if signature(path) != index['signature']:
        raise ValueError('Save changed during loading. Reload homelands.')
    return {'index': index, 'region': region, 'records': records, 'current': current}


def save_homelands(loaded, desired):
    index, region, records = loaded['index'], loaded['region'], loaded['records']
    desired = set(desired)
    if desired - records.keys():
        raise ValueError('Culture not present in save: ' + ', '.join(sorted(desired - records.keys())))
    path = Path(index['path'])
    if signature(path) != index['signature']:
        raise ValueError('Save changed since loading. Reload homelands.')
    edits = []
    for name, (start, end, text, cid) in records.items():
        states = cores(text)
        if (region in states) == (name in desired): continue
        states = [s for s in states if s != region]
        if name in desired: states.append(region)
        encoded = '{ ' + ' '.join(states) + ' }'
        span = field(text, 'core_states')
        if span:
            text = text[:span[0]] + encoded + text[span[1]:]
        else:
            pos = text.rfind('}')
            nl = '\r\n' if '\r\n' in text else '\n'
            text = text[:pos] + '\tcore_states=' + encoded + nl + text[pos:]
        edits.append((start, end, text.encode('utf-8')))
    if not edits: return None
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
        if signature(path) != index['signature']:
            raise ValueError('Save changed while preparing edit; nothing applied.')
        backup = None
        os.replace(temporary, path)
        return backup
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
