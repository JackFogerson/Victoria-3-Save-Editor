"""Edit campaign region resource pools and split-state arable land."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import os
import re
import shutil
import tempfile
from mass_migration import entries, field, signature
from state_resources import nonnegative
from save_io import commit_save


def get(text, key, default=None):
    span = field(text, key)
    return text[span[0]:span[1]] if span else default


def put(text, key, value):
    span = field(text, key)
    if span: return text[:span[0]] + value + text[span[1]:]
    pos = text.rfind('}')
    nl = '\r\n' if '\r\n' in text else '\n'
    return text[:pos] + '\t' + key + '=' + value + nl + text[pos:]


def resource_records(text):
    persistent = get(text, 'persistent_resources')
    if persistent is None: raise ValueError('Save region has no persistent resource data.')
    resources = get('x=' + persistent, 'resources')
    if resources is None: raise ValueError('Save region has no resource list.')
    # Records contain scalar properties; reject unfamiliar nested structures.
    body = resources[1:-1]
    matches = list(re.finditer(r'\{[^{}]*\}', body))
    if re.sub(r'\{[^{}]*\}', '', body).strip():
        raise ValueError('Unsupported saved resource structure.')
    records = {}
    for match in matches:
        raw = 'x=' + match.group()
        name = get(raw, 'type', '').strip('"')
        if not re.fullmatch(r'building_\w+', name) or name in records:
            raise ValueError('Invalid or duplicate saved resource type.')
        records[name] = raw
    return records


def load_resources(path, sid):
    before = signature(path)
    states, regions = {}, {}
    for section, ident, start, end, raw in entries(path, ('states', 'state_region_manager')):
        text = raw.decode('utf-8')
        record = (start, end, text)
        if section == 'states': states[ident] = record
        else: regions[get(text, 'template', '').strip('"')] = record
    if signature(path) != before: raise ValueError('Save changed while loading; reload it.')
    return resources_from_records(path, before, sid, states, regions)

def resources_from_records(path, before, sid, states, regions):
    if sid not in states: raise ValueError('State ID is not present in save.')
    region = get(states[sid][2], 'region', '').strip('"')
    if region not in regions: raise ValueError('State region resource record is missing from save.')
    record = regions[region]
    resources = resource_records(record[2])
    values = {'arable_land': nonnegative(get(record[2], 'arable_land', '0')), 'arable_resources': [], 'capped_resources': {}}
    undiscovered = {}
    for name, raw in resources.items():
        amount = get(raw, 'amount')
        hidden = get(raw, 'undiscovered_amount')
        if hidden is not None: undiscovered[name] = int(nonnegative(hidden))
        if amount is not None: values['capped_resources'][name] = nonnegative(amount)
        elif hidden is None: values['arable_resources'].append(name)
    return {'path': str(Path(path).resolve()), 'signature': before, 'region': region,
            'record': record, 'resources': resources, 'values': values, 'undiscovered': undiscovered,
            'states': {i: r for i, r in states.items() if get(r[2], 'region', '').strip('"') == region}}


def save_resources(loaded, values):
    path = Path(loaded['path'])
    if signature(path) != loaded['signature']: raise ValueError('Save changed since loading. Reload the state.')
    edits = prepare_resource_edits(loaded, values)
    temporary = None
    try:
        with path.open('rb') as source, tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as target:
            temporary = target.name
            for a, b, data in sorted(edits):
                remaining = a - source.tell()
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk: raise ValueError('Save ended unexpectedly.')
                    target.write(chunk); remaining -= len(chunk)
                source.seek(b); target.write(data)
            shutil.copyfileobj(source, target)
        if signature(path) != loaded['signature']: raise ValueError('Save changed while preparing edit; nothing applied.')
        backup = None
        commit_save(temporary, path, loaded['signature'], backup)
        return backup
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)


def prepare_resource_edits(loaded, values):
    land = nonnegative(values['arable_land'])
    arable, capped = values['arable_resources'], values['capped_resources']
    if set(arable) & set(capped): raise ValueError('A building cannot be both arable and capped.')
    if any(not re.fullmatch(r'building_\w+', n) for n in list(arable) + list(capped)):
        raise ValueError('Invalid building identifier.')
    converted = set(values.get('discover_resources', []))
    if not converted <= set(capped): raise ValueError('Converted resources need a capped amount.')
    records = []
    for name in dict.fromkeys(list(loaded['resources']) + list(arable) + list(capped)):
        raw = loaded['resources'].get(name, 'x={ type="' + name + '" }')
        hidden = name in loaded['undiscovered'] and name not in converted
        if name not in arable and name not in capped and not hidden: continue
        for key in ('amount', 'undiscovered_amount'):
            span = field(raw, key)
            if span:
                # Remove the entire scalar assignment, retaining other metadata.
                pattern = re.compile(r'\b' + key + r'\s*=\s*' + re.escape(raw[span[0]:span[1]]))
                raw = pattern.sub('', raw, count=1)
        if name in capped: raw = put(raw, 'amount', nonnegative(capped[name]))
        if hidden: raw = put(raw, 'undiscovered_amount', str(loaded['undiscovered'][name]))
        records.append(raw[2:])
    start, end, original = loaded['record']
    persistent = 'x=' + get(original, 'persistent_resources')
    persistent = put(persistent, 'resources', '{ ' + ' '.join(records) + ' }')
    changed = put(put(original, 'persistent_resources', persistent[2:]), 'arable_land', land)
    edits = [(start, end, changed.encode('utf-8'))]
    if land != loaded['values']['arable_land']:
        for a, b, text in loaded['states'].values():
            share = Decimal(get(text, 'land', '1' if len(loaded['states']) == 1 else '-1'))
            if not 0 <= share <= 1: raise ValueError('State land share is missing or invalid.')
            amount = str((Decimal(land) * share).to_integral_value(rounding=ROUND_HALF_UP))
            edits.append((a, b, put(text, 'arable_land', amount).encode('utf-8')))
    return edits
