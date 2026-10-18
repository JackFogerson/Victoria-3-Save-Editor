"""Read-only settlement checklist using installed definitions and built save levels."""
from pathlib import Path
from decimal import Decimal, InvalidOperation
import json
import re
from culture_definitions import definitions

GAME = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game')
HUBS = ('city', 'farm', 'mine', 'wood', 'port')


def load_catalog(game=GAME, mods=None):
    warnings = []
    if mods is None:
        config = Path.home() / 'Documents/Paradox Interactive/Victoria 3/content_load.json'
        try: mods = [Path(m['path']) for m in json.loads(config.read_text(encoding='utf-8-sig')).get('enabledMods', [])] if config.exists() else []
        except (OSError, ValueError, KeyError) as exc: mods = []; warnings.append('Could not read enabled mods: ' + str(exc))
    roots = [Path(game), *map(Path, mods)]
    buildings, regions, names = {}, {}, {}
    # Same relative filenames from a later mod replace earlier files.
    def files(relative, pattern):
        effective = {}
        for root in roots:
            directory = root / relative
            for path in sorted(directory.rglob(pattern)):
                effective[path.relative_to(directory).as_posix()] = path
        return sorted(effective.values(), key=lambda p: (roots.index(next(r for r in reversed(roots) if p.is_relative_to(r))), str(p)))
    for relative, destination in [('common/buildings', buildings), ('map_data/state_regions', regions)]:
        for path in files(relative, '*.txt'):
            try:
                for raw_name, block in definitions(path.read_text(encoding='utf-8-sig')).items():
                    name = raw_name.removeprefix('REPLACE_OR_CREATE:').removeprefix('REPLACE:')
                    fields = {f.key: f.value.strip('"') for f in block.children if f.children is None}
                    if relative == 'common/buildings': destination[name] = fields.get('city_type', '')
                    else: destination[name] = {hub: fields[hub] for hub in HUBS if hub in fields}
            except (OSError, ValueError) as exc: warnings.append(path.name + ': ' + str(exc))
    for path in files('localization/english', '*.yml'):
        try:
            for key, value in re.findall(r'^\s*(HUB_NAME_STATE_\w+):\d*\s*"([^"\r\n]*)"', path.read_text(encoding='utf-8-sig'), re.M): names[key] = value
        except (OSError, UnicodeError) as exc: warnings.append(path.name + ': ' + str(exc))
    return {'buildings': buildings, 'regions': regions, 'names': names, 'warnings': warnings}


def checklist(snapshot, sid, catalog):
    region = snapshot['states'][sid]['region']
    hubs = catalog['regions'].get(region)
    counts = snapshot.get('buildings', {}).get(sid, {})
    unknown = [key for key, levels in counts.items() if levels > 0 and key not in catalog['buildings']]
    rows = []
    for hub in HUBS:
        name = catalog['names'].get(f'HUB_NAME_{region}_{hub}', '(name unavailable)')
        matching = [(key, levels) for key, levels in counts.items() if levels > 0 and catalog['buildings'].get(key) == hub]
        candidates = sorted(key for key, kind in catalog['buildings'].items() if kind == hub and not key.startswith('building_subsistence_'))
        # Prefer conventional examples over special or automatically managed buildings.
        preferred = {'city':'building_food_industry', 'farm':'building_wheat_farm', 'mine':'building_iron_mine', 'wood':'building_logging_camp', 'port':'building_port'}[hub]
        if preferred in candidates: candidates.remove(preferred); candidates.insert(0, preferred)
        if hubs is None: status, detail = 'Unknown', 'Map-region definition unavailable.'
        elif hub not in hubs: status, detail = 'Not available', 'This region has no defined ' + hub + ' hub.'
        elif matching:
            status = 'Building present'
            detail = ', '.join(f'{key.removeprefix("building_").replace("_", " ")} ({levels:g})' for key, levels in matching)
        elif not snapshot.get('building_data_present') or unknown or catalog['warnings']:
            status, detail = 'Unknown', 'Building data or definitions are incomplete; cannot confirm absence.'
        else:
            status = 'Missing building'
            detail = 'Build 1 level: ' + ' / '.join(k.removeprefix('building_').replace('_', ' ') for k in candidates[:3]) if candidates else 'No matching building definition found.'
        rows.append((hub.title(), name if hubs and hub in hubs else '—', status, detail))
    return rows
