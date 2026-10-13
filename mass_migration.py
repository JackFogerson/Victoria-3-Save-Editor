"""Create linked mass-migration save records, without moving population."""
from pathlib import Path
from datetime import date, timedelta
import os
import re
import shutil
import tempfile
from culture_definitions import TOKEN


def signature(path):
    stat = Path(path).stat()
    return stat.st_size, stat.st_mtime_ns


def entries(path):
    section = None
    depth = 0
    raw = None
    with Path(path).open('rb') as handle:
        while True:
            offset = handle.tell()
            line = handle.readline()
            if not line: break
            if section is None:
                match = re.match(rb'^(country_manager|states|cultures)=\{', line)
                if match:
                    section = match[1].decode(); depth = 1
                continue
            if depth == 2:
                match = re.match(rb'^\s*(\d+)=\{', line)
                if match:
                    entry_id, start, raw = match[1].decode(), offset, []
            if raw is not None: raw.append(line)
            clean = re.sub(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*', b'', line)
            depth += clean.count(b'{') - clean.count(b'}')
            if raw is not None and depth == 2:
                yield section, entry_id, start, handle.tell(), b''.join(raw)
                raw = None
            if depth == 0: section = None
        if section is not None: raise ValueError('Incomplete save database section.')


def field(text, key):
    """Return a direct entry field's value span; tolerate anonymous arrays."""
    tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith('#')]
    depth, found = 0, []
    for i, token in enumerate(tokens):
        if depth == 1 and token.group() == key and i + 2 < len(tokens) and tokens[i + 1].group() == '=':
            value = tokens[i + 2]
            end = value.end()
            if value.group() == '{':
                nested = 1
                for following in tokens[i + 3:]:
                    if following.group() == '{': nested += 1
                    elif following.group() == '}': nested -= 1
                    if nested == 0:
                        end = following.end(); break
                else: raise ValueError('Incomplete migration record.')
            found.append((value.start(), end))
        if token.group() == '{': depth += 1
        elif token.group() == '}': depth -= 1
    if depth != 0: raise ValueError('Unbalanced save entry.')
    if len(found) > 1: raise ValueError(f'Duplicate {key} fields; refusing to overwrite.')
    return found[0] if found else None


def index_save(path):
    path = Path(path)
    before = signature(path)
    result = {'path': str(path.resolve()), 'signature': before, 'countries': {}, 'states': {}, 'cultures': {}}
    with path.open('rb') as handle:
        for line in handle:
            match = re.match(rb'^date=(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?\s*$', line)
            if match:
                result['date'] = date(*map(int, match.groups()[:3])).isoformat()
                break
    if 'date' not in result: raise ValueError('A text save with a valid game date is required.')
    for section, ident, start, end, raw in entries(path):
        text = raw.decode('utf-8')
        def scalar(key):
            match = re.search(r'^\t' + key + r'=([^\r\n]+)', text, re.M)
            return match[1].strip().strip('"') if match else ''
        item = {'span': (start, end)}
        if section == 'country_manager':
            item['name'] = scalar('definition')
            if item['name']: result['countries'][ident] = item
        elif section == 'states':
            item.update(name=scalar('region'), country=scalar('country'), occupied=bool(re.search(r'^\tmass_migration=', text, re.M)))
            if item['name']: result['states'][ident] = item
        else:
            item['name'] = scalar('type')
            if item['name']: result['cultures'][ident] = item
    if any(not result[key] for key in ('countries', 'states', 'cultures')):
        raise ValueError('Save is missing countries, states, or cultures.')
    result['countries'] = {key: item for key, item in result['countries'].items() if any(s['country'] == key for s in result['states'].values())}
    if signature(path) != before: raise ValueError('Save changed during loading; reload it.')
    return result


def updated_records(state_text, culture_text, culture_id, country_id, state_id, start_date, days):
    if not all(re.fullmatch(r'\d+', value) for value in (culture_id, country_id, state_id)):
        raise ValueError('Invalid save identifiers.')
    if not isinstance(days, int) or not 1 <= days <= 36500:
        raise ValueError('Duration must be 1–36,500 days.')
    start = date.fromisoformat(start_date)
    expiry = start + timedelta(days=days)
    def game_date(value): return f'{value.year}.{value.month}.{value.day}'
    if field(state_text, 'mass_migration') is not None:
        raise ValueError('Destination already has a mass-migration record. Choose another state.')
    span = field(culture_text, 'migration')
    if span:
        existing = culture_text[span[0]:span[1]]
        if re.search(r'\bstate\s*=\s*' + re.escape(state_id) + r'(?!\d)', existing):
            raise ValueError('This culture already has a migration record for that destination.')
    newline = '\r\n' if '\r\n' in state_text else '\n'
    destination = newline.join(['', '\tmass_migration={', f'\t\tculture={culture_id}', f'\t\tcountry={country_id}', '\t}', ''])
    close = state_text.rfind('}')
    state_text = state_text[:close] + destination + state_text[close:]
    newline = '\r\n' if '\r\n' in culture_text else '\n'
    record = newline.join(['{', f'\t\t\tstate={state_id}', f'\t\t\torigin={country_id}', f'\t\t\tdate={game_date(start)}', f'\t\t\texpiry_date={game_date(expiry)}', '\t\t\tactive=yes', '\t\t}'])
    if span:
        insert = span[1] - 1
        culture_text = culture_text[:insert] + ' ' + record + ' ' + culture_text[insert:]
    else:
        insert = culture_text.rfind('}')
        culture_text = culture_text[:insert] + newline + '\tmigration={ ' + record + ' }' + newline + culture_text[insert:]
    field(state_text, 'mass_migration'); field(culture_text, 'migration')
    return state_text, culture_text, game_date(expiry)


def create_migration(index, culture_id, source_id, destination_id, days):
    path = Path(index['path'])
    if signature(path) != index['signature']: raise ValueError('Save changed since loading. Reload migration choices.')
    if culture_id not in index['cultures'] or source_id not in index['countries'] or destination_id not in index['states']:
        raise ValueError('Select a culture, source country, and destination from the loaded save.')
    if index['states'][destination_id]['country'] == source_id:
        raise ValueError('Mass migration requires a destination in another country.')
    state_span = index['states'][destination_id]['span']; culture_span = index['cultures'][culture_id]['span']
    with path.open('rb') as handle:
        def read_span(span):
            handle.seek(span[0]); return handle.read(span[1] - span[0]).decode('utf-8')
        state_text, culture_text = read_span(state_span), read_span(culture_span)
    state_text, culture_text, expiry = updated_records(state_text, culture_text, culture_id, source_id, destination_id, index['date'], days)
    edits = sorted([(state_span, state_text.encode('utf-8')), (culture_span, culture_text.encode('utf-8'))])
    temporary = None
    try:
        with path.open('rb') as source, tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as target:
            temporary = target.name
            for (start, end), data in edits:
                remaining = start - source.tell()
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk: raise ValueError('Save ended unexpectedly.')
                    target.write(chunk); remaining -= len(chunk)
                source.seek(end); target.write(data)
            shutil.copyfileobj(source, target)
        if signature(path) != index['signature']: raise ValueError('Save changed while preparing migration; nothing applied.')
        os.replace(temporary, path)
        return expiry
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
