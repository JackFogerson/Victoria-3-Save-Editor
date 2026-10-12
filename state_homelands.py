"""Resolve save state IDs and update only homeland history commands."""
from pathlib import Path
import re
from culture_definitions import TOKEN, parse

DEFAULT_STATE_FILE = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game\common\history\states\00_states.txt')


def resolve_state(path, state_id):
    if not re.fullmatch(r'\d+', state_id):
        raise ValueError('Enter a numeric State ID.')
    active = False
    depth = 0
    selected = False
    with open(path, encoding='utf-8-sig') as handle:
        for line in handle:
            if not active:
                if not re.match(r'^states\s*=\s*\{', line):
                    continue
                active = True
            tokens = [m.group() for m in TOKEN.finditer(line) if not m.group().startswith('#')]
            for index, token in enumerate(tokens):
                if depth == 2 and token.isdecimal() and tokens[index + 1:index + 3] == ['=', '{']:
                    selected = int(token) == int(state_id)
                if selected and depth == 3 and token == 'region' and tokens[index + 1:index + 2] == ['=']:
                    region = tokens[index + 2].strip('"')
                    if not re.fullmatch(r'STATE_\w+', region):
                        raise ValueError('Unsupported state region reference.')
                    return region
                if token == '{':
                    depth += 1
                elif token == '}':
                    depth -= 1
                    if depth == 2:
                        selected = False
            if depth == 0:
                break
    raise ValueError(f'State ID {state_id} was not found in the selected text save, or has no region.')


def history_states(text):
    roots = [f for f in parse(text) if f.key.strip('"') == 'STATES']
    if len(roots) != 1:
        raise ValueError('Expected one STATES block in the history file.')
    return {f.key.strip('"').removeprefix('s:'): f for f in roots[0].children or [] if f.children is not None}


def homelands(block):
    return list(dict.fromkeys(f.value.strip('"').removeprefix('cu:') for f in block.children
                             if f.key == 'add_homeland'))


def replace_homelands(text, region, desired):
    if any(not re.fullmatch(r'\w+', name) for name in desired):
        raise ValueError('Homelands must use culture keys, such as north_german.')
    desired = list(dict.fromkeys(desired))
    block = history_states(text)[region]
    edits = []
    existing = homelands(block)
    for field in block.children:
        if field.key == 'add_homeland' and field.value.strip('"').removeprefix('cu:') not in desired:
            edits.append((field.start, field.end, ''))
    newline = '\r\n' if '\r\n' in text else '\n'
    additions = [name for name in desired if name not in existing]
    if additions:
        edits.append((block.end - 1, block.end - 1, newline + ''.join(
            '\t\tadd_homeland = cu:' + name + newline for name in additions) + '\t'))
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    history_states(text)
    return text
