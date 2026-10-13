"""Read and replace a country's primary culture IDs in a text save."""
from datetime import datetime
from pathlib import Path
import os
import re
import shutil
import tempfile
from mass_migration import field, signature


def culture_ids(text):
    span = field(text, 'cultures')
    if span is None:
        raise ValueError('This country has no primary-culture list.')
    value = text[span[0]:span[1]]
    if not re.fullmatch(r'\{[\s\d]*\}', value):
        raise ValueError('Unrecognized primary-culture list; no changes made.')
    return value[1:-1].split()


def read_country(index, country_id):
    path = Path(index['path'])
    if signature(path) != index['signature']:
        raise ValueError('Save changed. Reload choices before editing.')
    start, end = index['countries'][country_id]['span']
    with path.open('rb') as handle:
        handle.seek(start)
        text = handle.read(end - start).decode('utf-8')
    return text


def save_primary_cultures(index, country_id, ids):
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise ValueError('Keep at least one primary culture.')
    if any(cid not in index['cultures'] for cid in ids):
        raise ValueError('Choose cultures from the selected save.')
    text = read_country(index, country_id)
    culture_ids(text)  # Validate before replacing only the direct field.
    a, b = field(text, 'cultures')
    replacement = (text[:a] + '{ ' + ' '.join(ids) + ' }' + text[b:]).encode('utf-8')
    path = Path(index['path'])
    start, end = index['countries'][country_id]['span']
    temporary = None
    try:
        with path.open('rb') as source, tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as target:
            temporary = target.name
            remaining = start
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError('Save ended unexpectedly.')
                target.write(chunk)
                remaining -= len(chunk)
            target.write(replacement)
            source.seek(end)
            shutil.copyfileobj(source, target)
        if signature(path) != index['signature']:
            raise ValueError('Save changed while preparing edit; nothing applied.')
        backup = path.with_name(path.name + '.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        shutil.copy2(path, backup)
        os.replace(temporary, path)
        return backup
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
