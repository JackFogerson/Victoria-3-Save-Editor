"""Read map-region resources and preserve unrelated definition text."""
from pathlib import Path
import re
from culture_definitions import definitions

DEFAULT_REGION_FOLDER = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game\map_data\state_regions')


def resource_values(block):
    fields = {f.key: f for f in block.children}
    return {
        'arable_land': fields['arable_land'].value if 'arable_land' in fields else '0',
        'arable_resources': [f.value.strip('"') for f in fields['arable_resources'].children] if 'arable_resources' in fields else [],
        'capped_resources': {f.key: f.value for f in fields['capped_resources'].children} if 'capped_resources' in fields else {},
    }


def scan_regions(folder):
    regions, arable, capped = {}, set(), set()
    for path in sorted(Path(folder).glob('*.txt')):
        for name, block in definitions(path.read_bytes().decode('utf-8-sig')).items():
            if not name.startswith('STATE_'):
                continue
            if name in regions:
                raise ValueError(f'Duplicate region {name} in folder.')
            fields = {f.key: f for f in block.children}
            regions[name] = (path, fields['id'].value)
            values = resource_values(block)
            arable.update(values['arable_resources'])
            capped.update(values['capped_resources'])
    if not regions:
        raise ValueError('No state region definitions found in this folder.')
    return regions, sorted(arable), sorted(capped)


def nonnegative(value):
    if not re.fullmatch(r'\d+', str(value)):
        raise ValueError('Arable land and resource levels must be non-negative whole numbers.')
    return str(int(value))


def replace_resources(text, region, changes):
    block = definitions(text)[region]
    fields = {f.key: f for f in block.children}
    newline = '\r\n' if '\r\n' in text else '\n'
    edits, additions = [], []
    for key, value in changes.items():
        if key == 'arable_land':
            encoded = nonnegative(value)
        elif key in ('arable_resources', 'capped_resources'):
            if any(not re.fullmatch(r'building_\w+', name) for name in value):
                raise ValueError('Use building keys such as building_iron_mine.')
            if key == 'arable_resources':
                encoded = '{ ' + ' '.join('"' + name + '"' for name in dict.fromkeys(value)) + ' }'
            else:
                encoded = '{' + newline + ''.join('        ' + name + ' = ' + nonnegative(level) + newline for name, level in value.items()) + '    }'
        else:
            raise ValueError('Unsupported state resource field.')
        if key in fields:
            field = fields[key]
            edits.append((field.value_start, field.end, encoded))
        else:
            additions.append('    ' + key + ' = ' + encoded + newline)
    if additions:
        edits.append((block.end - 1, block.end - 1, newline + ''.join(additions)))
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    definitions(text)
    return text
