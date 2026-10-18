"""One-pass campaign indexing and one-write independent state edits."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import os
import re
import shutil
import tempfile
from mass_migration import entries, field, signature, updated_records
from save_io import commit_save
from save_homelands import cores
from save_resources import put, get, resources_from_records, prepare_resource_edits


def scalar(text, key, default=''):
    match = re.search(r'^\s*' + re.escape(key) + r'=([^\s{}]+)', text, re.M)
    return match[1].strip('"') if match else default


def load_batch(path, include_settlements=False):
    path = Path(path).resolve()
    before = signature(path)
    states, cultures, pops = {}, {}, []
    state_records, regions, countries = {}, {}, {}
    buildings, seen = {}, set()
    for section, ident, start, end, raw in entries(path, ('states', 'cultures', 'pops', 'state_region_manager', 'country_manager', 'building_manager'), seen=seen):
        text = raw.decode('utf-8')
        if section == 'building_manager':
            sid, key = scalar(text, 'state'), scalar(text, 'building')
            levels = Decimal(scalar(text, 'levels', '0'))
            if levels.is_finite() and levels > 0 and scalar(text, 'active', 'yes') != 'no':
                counts = buildings.setdefault(sid, Counter()); counts[key] += levels
        elif section == 'state_region_manager':
            regions[get(text, 'template', '').strip(chr(34))] = (start, end, text)
        elif section == 'country_manager':
            countries[ident] = scalar(text, 'definition')
        elif section == 'states':
            state_records[ident] = (start, end, text)
            region = scalar(text, 'region')
            if region: states[ident] = {'region': region, 'cultures': Counter(), 'religions': Counter(), 'jobs': Counter(), 'homelands': [], 'country': scalar(text, 'country')}
        elif section == 'cultures':
            key = scalar(text, 'type')
            if key: cultures[ident] = {'key': key, 'span': (start, end), 'text': text, 'cores': cores(text)}
        else:
            sid = scalar(text, 'location')
            culture, religion, job = (scalar(text, key) for key in ('culture', 'religion', 'type'))
            wf = scalar(text, 'workforce', None)
            dependents = scalar(text, 'dependents', '0')
            if sid and culture:
                pops.append((start, end, sid, culture, religion, job, None if wf is None else int(wf), int(dependents)))
    for start, end, sid, cid, religion, job, workforce, dependents in pops:
        if sid not in states: continue
        state = states[sid]
        state['cultures'][cid] += (workforce or 0) + dependents
        state['religions'][religion] += (workforce or 0) + dependents
        if workforce is not None: state['jobs'][job] += 1
    for state in states.values():
        state['homelands'] = [cid for cid, culture in cultures.items() if state['region'] in culture['cores']]
    if signature(path) != before: raise ValueError('Save changed during loading. Reload the batch.')
    if not states or not cultures: raise ValueError('Select a supported text save with states and cultures.')
    game_date = None
    with path.open('rb') as handle:
        for line in handle:
            match = re.match(rb'^date=(\d+)\.(\d+)\.(\d+)', line)
            if match:
                game_date = '-'.join(x.decode().zfill(2) for x in match.groups()); break
            if handle.tell() > 1024 * 1024: break
    from settlement_checklist import load_catalog
    catalog = load_catalog() if include_settlements else None
    if signature(path) != before: raise ValueError('Save changed during loading. Reload it.')
    return {'settlement_catalog': catalog, 'buildings': buildings, 'building_data_present': 'building_manager' in seen, 'date': game_date, 'state_records': state_records, 'regions': regions, 'countries': countries, 'path': str(path), 'signature': before, 'states': states, 'cultures': cultures, 'pops': pops}


def apply_batch(snapshot, plans):
    """Validate everything first; percentages use original cultures, then swaps."""
    path = Path(snapshot['path'])
    if signature(path) != snapshot['signature']: raise ValueError('Save changed since loading. Reload the batch before applying.')
    if not plans: raise ValueError('Add at least one state to the batch.')
    regions, normalized, skipped = {}, {}, []
    valid_cultures = set(snapshot['cultures'])
    known_religions = {r for state in snapshot['states'].values() for r in state['religions']}
    for sid, plan in plans.items():
        if sid not in snapshot['states']: raise ValueError('Unknown State ID: ' + sid)
        state = snapshot['states'][sid]
        scales = {}
        for cid, value in plan.get('percentages', {}).items():
            percent = Decimal(str(value).strip().removesuffix('%'))
            if not percent.is_finite() or percent < -100: raise ValueError('Population percentage must be finite and at least -100.')
            if cid not in state['cultures']: raise ValueError(f'Culture {cid} is not present in State {sid}.')
            if percent: scales[cid] = 1 + percent / 100
        swaps = plan.get('cultures', {})
        for old, new in swaps.items():
            if old not in state['cultures'] or new not in valid_cultures: raise ValueError(f'Invalid culture conversion in State {sid}.')
        religions = plan.get('religions', {})
        for old, new in religions.items():
            if old not in state['religions'] or new not in known_religions: raise ValueError(f'Invalid religion conversion in State {sid}.')
        jobs = {}
        for job, amount in plan.get('workforce', {}).items():
            amount = int(amount)
            if not amount: continue
            count = state['jobs'].get(job, 0)
            if not count:
                skipped.append(f'State {sid}: {job} ({amount:+,})'); continue
            base, remainder = divmod(amount, count)
            jobs[job] = iter([base + 1] * remainder + [base] * (count - remainder))
        if 'homelands' in plan:
            desired = set(plan['homelands'])
            if desired - valid_cultures: raise ValueError('Unknown homeland culture.')
            region = state['region']
            if region in regions and regions[region] != desired:
                raise ValueError(f'{region} is shared by split states with conflicting homeland edits. Use the same homeland list.')
            regions[region] = desired
        normalized[sid] = (scales, swaps, religions, jobs)
    edits = []
    touched_pops = 0
    with path.open('rb') as handle:
        for start, end, sid, cid, religion, job, workforce, dependents in snapshot['pops']:
            if sid not in normalized: continue
            scales, swaps, religions, jobs = normalized[sid]
            factor = scales.get(cid, Decimal(1))
            new_wf = None if workforce is None else int((Decimal(workforce) * factor).to_integral_value(rounding=ROUND_HALF_UP))
            new_deps = int((Decimal(dependents) * factor).to_integral_value(rounding=ROUND_HALF_UP))
            if new_wf is not None and job in jobs: new_wf += next(jobs[job])
            if new_wf is not None and new_wf < 0: raise ValueError(f'State {sid}: workforce reduction would make a {job} population negative.')
            replacements = {}
            if new_wf != workforce: replacements['workforce'] = str(new_wf)
            if new_deps != dependents: replacements['dependents'] = str(new_deps)
            if cid in swaps and swaps[cid] != cid: replacements['culture'] = swaps[cid]
            if religion in religions and religions[religion] != religion: replacements['religion'] = religions[religion]
            if not replacements: continue
            handle.seek(start); text = handle.read(end - start).decode('utf-8')
            for key, value in replacements.items(): text = put(text, key, value)
            edits.append((start, end, text.encode('utf-8'))); touched_pops += 1
    for cid, culture in snapshot['cultures'].items():
        values = list(culture['cores'])
        for region, desired in regions.items():
            if region in values and cid not in desired: values.remove(region)
            elif region not in values and cid in desired: values.append(region)
        if values != culture['cores']:
            text = put(culture['text'], 'core_states', '{ ' + ' '.join(values) + ' }')
            edits.append((*culture['span'], text.encode('utf-8')))
    # Merge edits to the same culture/state (homelands, resources and migrations).
    merged = {(a, b): data for a, b, data in edits}
    resource_regions = {}
    for sid, plan in plans.items():
        if 'resources' not in plan: continue
        region = snapshot['states'][sid]['region']
        if region in resource_regions:
            if resource_regions[region] != plan['resources']: raise ValueError('Conflicting resource edits for split states in ' + region)
            continue
        resource_regions[region] = plan['resources']
        loaded = resources_from_records(path, snapshot['signature'], sid, snapshot['state_records'], snapshot['regions'])
        for a, b, data in prepare_resource_edits(loaded, plan['resources']): merged[a, b] = data
    for sid, plan in plans.items():
        if 'migration' not in plan: continue
        event = plan['migration']; cid, source = event['culture'], event['source']
        if cid not in valid_cultures or source not in snapshot['countries']: raise ValueError('Choose a valid migration culture and source country.')
        if source == snapshot['states'][sid]['country']: raise ValueError('Mass migration requires a destination in another country.')
        if not snapshot['date']: raise ValueError('Save date is missing.')
        a, b, state_text = snapshot['state_records'][sid]
        culture = snapshot['cultures'][cid]; c, d = culture['span']
        state_text = merged.get((a, b), state_text.encode()).decode('utf-8')
        culture_text = merged.get((c, d), culture['text'].encode()).decode('utf-8')
        state_text, culture_text, _ = updated_records(state_text, culture_text, cid, source, sid, snapshot['date'], int(event['days']))
        merged[a, b] = state_text.encode('utf-8'); merged[c, d] = culture_text.encode('utf-8')
    edits = [(a, b, data) for (a, b), data in merged.items()]
    result = {'populations': touched_pops, 'records': len(edits), 'skipped': skipped}
    if not edits: return result
    temporary = None
    try:
        with path.open('rb') as source, tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as target:
            temporary = target.name
            for start, end, data in sorted(edits):
                remaining = start - source.tell()
                if remaining < 0: raise ValueError('Overlapping batch edits.')
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk: raise ValueError('Save ended unexpectedly.')
                    target.write(chunk); remaining -= len(chunk)
                target.write(data); source.seek(end)
            shutil.copyfileobj(source, target)
        commit_save(temporary, path, snapshot['signature'])
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
    return result
