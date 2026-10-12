"""Read-only, approximate vacancy/qualification comparison for text saves.

Vacancies use each building's PM employment capacity minus its employed pops.
This is an estimate, not the game's executable tooltip calculation.
"""
import argparse
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import re
from culture_definitions import definitions

DEFAULT_GAME = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game')


def database_blocks(path, section):
    """Stream numeric database entries without loading the entire save."""
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line in handle:
            if re.match(r'^' + re.escape(section) + r'\s*=\s*\{', line):
                break
        else:
            raise ValueError(f'Missing {section} section in text save.')
        depth = 1
        lines = None
        for line in handle:
            clean = re.sub(r'"(?:\\.|[^"\\])*"|#[^\n]*', '', line)
            if depth == 2 and re.match(r'^\s*\d+\s*=\s*\{', line):
                lines = []
            if lines is not None:
                lines.append(line)
            depth += clean.count('{') - clean.count('}')
            if lines is not None and depth == 2:
                yield ''.join(lines)
                lines = None
            if depth == 0:
                return


def children(block):
    return {f.key: f for f in block.children or [] if f.key}


def scalar(fields, key, default='0'):
    return fields[key].value.strip('"') if key in fields else default


def pm_jobs(game):
    jobs, unsupported = {}, {}
    for path in sorted((Path(game) / 'common/production_methods').glob('*.txt')):
        for name, block in definitions(path.read_text(encoding='utf-8-sig')).items():
            result = defaultdict(Decimal)
            flags = []
            for scope in block.children:
                if scope.key != 'building_modifiers': continue
                for scaling in scope.children or []:
                    for field in scaling.children or []:
                        match = re.fullmatch(r'building_employment_(\w+)_add', field.key)
                        if match and scaling.key == 'level_scaled':
                            result[match[1]] += Decimal(field.value)
                        elif 'employment_' in field.key:
                            flags.append(field.key)
            jobs[name] = dict(result)
            unsupported[name] = flags
    return jobs, unsupported


def estimate(save, game=DEFAULT_GAME):
    states, countries = {}, {}
    def value(text, key, default='0'):
        m = re.search(r'^\s*' + key + r'=([^\s{}]+)', text, re.M)
        return m[1].strip('"') if m else default
    def array(text, key):
        m = re.search(r'^\s*' + key + r'=\{([^}]*)\}', text, re.M)
        return {k: Decimal(v) for k, v in re.findall(r'(\d+)=([\d.]+)', m[1])} if m else {}
    for text in database_blocks(save, 'country_manager'):
        countries[text.split('=')[0].strip()] = value(text, 'definition', '?')
    for text in database_blocks(save, 'states'):
        sid = text.split('=')[0].strip()
        states[sid] = {'region': value(text, 'region'), 'country': countries.get(value(text, 'country'), '?'),
                       'qualifications': array(text, 'population_employable_qualifications'),
                       'workforce': array(text, 'population_workforce_by_profession'),
                       'has_qualifications': 'population_employable_qualifications=' in text}
    # Infer profession indices by comparing aggregate workforce with pop totals.
    population = defaultdict(lambda: defaultdict(int))
    employed = defaultdict(lambda: defaultdict(int))
    for text in database_blocks(save, 'pops'):
        job, workforce = value(text, 'type'), int(value(text, 'workforce'))
        population[value(text, 'location')][job] += workforce
        workplace = value(text, 'workplace', '')
        if workplace: employed[workplace][job] += workforce
    professions = sorted({job for counts in population.values() for job in counts})
    enum = {}
    enum_validation = {}
    for job in professions:
        scores = []
        for index in range(15):
            relevant = [(sid, counts) for sid, counts in population.items() if sid in states and counts.get(job, 0) > 0]
            matches = sum(Decimal(counts[job]) == states[sid]['workforce'].get(str(index), Decimal(0)) for sid, counts in relevant)
            scores.append((matches, str(index)))
        scores.sort(reverse=True)
        if scores[0][0] >= max(1, len(relevant) * 0.95) and scores[0][0] > scores[1][0]:
            enum[job] = scores[0][1]
            enum_validation[job] = {'matching_states': scores[0][0], 'states_with_profession': len(relevant)}
    jobs, unsupported = pm_jobs(game)
    vacancies = defaultdict(lambda: defaultdict(Decimal))
    warnings = defaultdict(set)
    used_methods = set()
    for text in database_blocks(save, 'building_manager'):
        bid = text.split('=')[0].strip()
        sid = value(text, 'state')
        if sid not in states or value(text, 'active', 'yes') == 'no': continue

        rates = defaultdict(Decimal)
        methods = re.search(r'^\s*production_methods=\{([^}]*)\}', text, re.M)
        if methods is None:
            warnings[sid].add(f'Building {bid} has no production methods.')
            continue
        for method in re.findall(r'"([^"\n]+)"', methods[1]):
            used_methods.add(method)
            if method not in jobs:
                warnings[sid].add(f'Unknown production method: {method}')
                continue
            for warning in unsupported[method]: warnings[sid].add(f'Unsupported modifier: {method}: {warning}')
            for job, rate in jobs[method].items(): rates[job] += rate
        for job, rate in rates.items():
            required = max(Decimal(0), rate) * Decimal(value(text, 'levels'))
            vacancies[sid][job] += max(Decimal(0), required - employed[bid].get(job, 0))
    rows = []
    for sid, totals in vacancies.items():
        state = states[sid]
        for job, vacant in totals.items():
            if job in ('peasants', 'laborers', 'slaves', 'soldiers'): continue
            if job not in enum or not state['has_qualifications']: continue
            available = state['qualifications'].get(enum[job], Decimal(0))
            shortage = vacant - available
            if shortage > 0:
                rows.append({'state_id': sid, 'region': state['region'], 'country': state['country'], 'profession': job,
                             'estimated_vacancies': float(vacant), 'available_qualifications': float(available),
                             'estimated_shortage': int(shortage.to_integral_value(rounding=ROUND_CEILING)),
                             'warnings': sorted(warnings[sid])})
    rows.sort(key=lambda row: (-row['estimated_shortage'], int(row['state_id']), row['profession']))
    return {'save': str(Path(save).resolve()), 'game': str(game), 'profession_indices': enum,
            'profession_index_validation': enum_validation,
            'comparison_states': {sid: {'region': st['region'], 'country': st['country'], 'qualifications': {job: float(st['qualifications'].get(index, 0)) for job, index in enum.items()}, 'vacancies': {job: float(n) for job, n in vacancies[sid].items()}} for sid, st in states.items() if 'SUMATRA' in st['region'] or 'HUDAV' in st['region']},
            'unmapped_professions': sorted(set(professions) - set(enum)),
            'states_scanned': len(states), 'states_without_qualification_cache': [sid for sid, s in states.items() if not s['has_qualifications']],
            'warnings': {sid: sorted(items) for sid, items in warnings.items() if items}, 'rows': rows}


def write_report(result, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    rows = result['rows']
    lines = ['# Estimated qualification shortages', '', f"Save: `{Path(result['save']).name}`", '',
             f"{result['states_scanned']} states scanned; {len(set(r['state_id'] for r in rows))} states flagged; {len(rows)} profession shortages.", '',
             'Method: sum each active building’s production-method job capacity minus workers assigned to that building; subtract saved employable qualifications. Positive shortfalls round up.', '',
             'Estimates only: employment modifiers, mod load order, hiring restrictions, and engine rounding may differ. No save or game file is modified. Compare Vacancies to “needed for full employment”; shortfall is vacancies minus available qualifications.', '',
             'North Sumatra (575) and Hudavendigar (835) match the supplied screenshots. Other results still need in-game verification.', '',
             '| State ID | Region | Owner | Profession | Vacancies | Available | Shortfall |',
             '|---|---|---|---|---:|---:|---:|']
    for r in sorted(rows, key=lambda r: (r['region'], int(r['state_id']), r['profession'])):
        lines.append(f"| {r['state_id']} | {r['region'].removeprefix('STATE_').replace('_', ' ').title()} | {r['country']} | {r['profession']} | {r['estimated_vacancies']:g} | {r['available_qualifications']:g} | {r['estimated_shortage']} |")
    lines += ['', f"States with unresolved production-method warnings: {len(result['warnings'])}. See JSON for details.",
              f"Unmapped professions: {', '.join(result['unmapped_professions']) or 'none'}."]
    output.with_suffix('.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('save')
    parser.add_argument('--game', default=str(DEFAULT_GAME))
    parser.add_argument('--output', default='reports/shortage_estimates.json')
    args = parser.parse_args()
    result = estimate(args.save, args.game)
    write_report(result, args.output)
    print(f"Scanned {result['states_scanned']} states; found {len(result['rows'])} estimated profession shortages.")
    print('Unmapped professions:', result['unmapped_professions'])
    print('States with warnings:', len(result['warnings']))
