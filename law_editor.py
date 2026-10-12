"""Lossless-span edits for law modifiers and activation/deactivation effects."""
from pathlib import Path
from decimal import Decimal, InvalidOperation
import re
from culture_definitions import definitions, parse

DEFAULT_LAWS = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game\common\laws')


def scan_laws(folder):
    laws, effects = {}, set()
    for path in sorted(Path(folder).glob('*.txt')):
        text = path.read_bytes().decode('utf-8-sig')
        for name, block in definitions(text).items():
            if not name.startswith('law_'): continue
            if name in laws: raise ValueError(f'Duplicate law definition: {name}')
            laws[name] = path
            for field in block.children:
                if field.key == 'modifier': effects.update(f.key for f in field.children or [] if f.key)
    if not laws: raise ValueError('No laws found in this folder.')
    return laws, sorted(effects)


def law_values(text, name):
    fields = {f.key: f for f in definitions(text)[name].children}
    modifiers = fields.get('modifier')
    if modifiers and any(f.children is not None for f in modifiers.children):
        raise ValueError('Nested law modifiers are not supported by this editor.')
    values = {'modifier': {f.key: f.value for f in modifiers.children or []} if modifiers else {}}
    for key in ('on_activate', 'on_deactivate'):
        field = fields.get(key)
        values[key] = text[field.value_start + 1:field.end - 1] if field else ''
    return values


def validate_effect(key, value):
    if not re.fullmatch(r'[A-Za-z_]\w*', key): raise ValueError('Enter a modifier key from the list or a valid custom key.')
    if value not in ('yes', 'no'):
        try: number = Decimal(value)
        except InvalidOperation: raise ValueError('Effect values must be a number, yes, or no.')
        if not number.is_finite(): raise ValueError('Effect values must be finite.')
    return value


def replace_law(text, name, values):
    block = definitions(text)[name]
    fields = {f.key: f for f in block.children}
    original = law_values(text, name)
    newline = '\r\n' if '\r\n' in text else '\n'
    edits, additions = [], []
    for key in ('modifier', 'on_activate', 'on_deactivate'):
        if values[key] == original[key]: continue
        if key == 'modifier':
            # Modify only changed entries, retaining comments and other values.
            existing = {f.key: f for f in fields[key].children} if key in fields else {}
            added = []
            for effect, value in values[key].items():
                validate_effect(effect, value)
                if effect in existing:
                    field = existing[effect]
                    if field.value != value: edits.append((field.value_start, field.end, value))
                else: added.append('\t\t' + effect + ' = ' + value + newline)
            for effect, field in existing.items():
                if effect not in values[key]: edits.append((field.start, field.end, ''))
            if added:
                if key in fields:
                    edits.append((fields[key].end - 1, fields[key].end - 1, newline + ''.join(added) + '\t'))
                else: additions.append('\tmodifier = {' + newline + ''.join(added) + '\t}' + newline)
        else:
            body = values[key].replace('\r\n', '\n').replace('\n', newline)
            # Validate balanced script and prevent escape into another law.
            wrapper = parse('check = {' + body + '\n}')
            if len(wrapper) != 1 or wrapper[0].key != 'check': raise ValueError('Script must remain inside its effect block.')
            encoded = '{' + body + '}'
            if key in fields: edits.append((fields[key].value_start, fields[key].end, encoded))
            elif body.strip(): additions.append('\t' + key + ' = ' + encoded + newline)
    if additions: edits.append((block.end - 1, block.end - 1, newline + ''.join(additions)))
    for start, end, value in sorted(edits, reverse=True): text = text[:start] + value + text[end:]
    definitions(text)
    return text
