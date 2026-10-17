"""Small, lossless-span reader/editor for Clausewitz culture definitions."""
import re
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import os
from datetime import datetime


DEFAULT_CULTURE_FILE = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game\common\cultures\00_cultures.txt')
TOKEN = re.compile(r'#[^\r\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#"]+')


@dataclass
class Field:
    key: str
    start: int
    value_start: int
    end: int
    children: object = None
    value: str = ''


def parse(text):
    tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith('#')]

    def fields(index, nested=False):
        result = []
        while index < len(tokens):
            token = tokens[index]
            if token.group() == '}':
                if not nested:
                    raise ValueError('Unexpected closing brace')
                return result, index + 1
            if index + 1 < len(tokens) and tokens[index + 1].group() == '=':
                key = token.group()
                start = index
                index += 2
                if index == len(tokens):
                    raise ValueError('Missing value')
                value_start = tokens[index].start()
                # Tagged blocks such as color = rgb { ... }.
                if index + 1 < len(tokens) and tokens[index + 1].group() == '{':
                    index += 1
                if tokens[index].group() == '{':
                    children, index = fields(index + 1, True)
                    result.append(Field(key, tokens[start].start(), value_start,
                                        tokens[index - 1].end(), children))
                else:
                    result.append(Field(key, token.start(), value_start,
                                        tokens[index].end(), value=tokens[index].group()))
                    index += 1
            elif token.group() == '{':
                raise ValueError('Unexpected opening brace')
            else:
                result.append(Field('', token.start(), token.start(), token.end(), value=token.group()))
                index += 1
        if nested:
            raise ValueError('Unclosed block')
        return result, index

    return fields(0)[0]


def definitions(text):
    return {f.key: f for f in parse(text) if f.key and f.children is not None}


def attributes(block):
    values = {'religion': '', 'language': '', 'obsessions': [], 'taboos': []}
    for field in block.children:
        if field.key in ('religion', 'language'):
            values[field.key] = field.value.strip('"')
        elif field.key in ('obsessions', 'taboos'):
            values[field.key] = [f.value.strip('"') for f in field.children or [] if not f.key]
    return values


def catalog(text):
    blocks = definitions(text)
    religions, languages, goods = set(), set(), set()
    for block in blocks.values():
        data = attributes(block)
        religions.add(data['religion'])
        languages.add(data['language'])
        goods.update(data['obsessions'] + data['taboos'])
    return {'cultures': list(blocks), 'religions': sorted(religions - {''}),
            'languages': sorted(languages - {''}), 'goods': sorted(goods)}


def replace_attributes(text, culture, changes):
    block = definitions(text)[culture]
    existing = {f.key: f for f in block.children}
    edits, additions = [], []
    newline = '\r\n' if '\r\n' in text else '\n'
    for key, value in changes.items():
        if key not in ('religion', 'language', 'obsessions', 'taboos'):
            raise ValueError('Unsupported culture field')
        items = value if isinstance(value, list) else [value]
        if any(not re.fullmatch(r'[A-Za-z0-9_]+', item) for item in items):
            raise ValueError('Values must be game identifiers')
        encoded = '{ ' + ' '.join(items) + ' }' if isinstance(value, list) else value
        if key in existing:
            field = existing[key]
            edits.append((field.value_start, field.end, encoded))
        else:
            additions.append('\t' + key + ' = ' + encoded + newline)
    if additions:
        edits.append((block.end - 1, block.end - 1, newline + ''.join(additions)))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    definitions(text)  # Refuse malformed output before writing.
    return text


def save_changes(path, original, updated):
    path = Path(path)
    if path.read_bytes() != original:
        raise ValueError('The file changed since loading. Reload it before saving.')
    backup = None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
            temporary = handle.name
            handle.write(updated)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return backup
