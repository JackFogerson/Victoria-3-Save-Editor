"""Refresh save offsets without discarding or silently reapplying state drafts."""
from pathlib import Path


def rebase_drafts(previous, fresh, state_ids):
    if Path(previous['path']).resolve() != Path(fresh['path']).resolve():
        raise ValueError('Drafts belong to a different save. Select the original save to continue.')
    old_pops, new_pops = {}, {}
    for snapshot, target in ((previous, old_pops), (fresh, new_pops)):
        for pop in snapshot['pops']:
            if pop[2] in state_ids: target.setdefault(pop[2], []).append(pop[2:])
    for sid in state_ids:
        if previous['states'].get(sid) != fresh['states'].get(sid) or old_pops.get(sid) != new_pops.get(sid):
            raise ValueError(f'State {sid} changed in the save. Drafts are still displayed; review them before explicitly discarding or transferring them.')
        for cid in previous['cultures']:
            # IDs must still denote the same culture. Goods changes are unrelated to drafts.
            if fresh['cultures'].get(cid, {}).get('key') != previous['cultures'][cid]['key']:
                raise ValueError('Culture identities changed. Drafts retained; automatic refresh stopped.')
        old_region, new_region = previous.get('regions', {}).get(previous['states'][sid]['region']), fresh.get('regions', {}).get(fresh['states'][sid]['region'])
        if (old_region[2] if old_region else None) != (new_region[2] if new_region else None):
            raise ValueError(f'Resources in State {sid} changed externally. Drafts retained; automatic refresh stopped.')
        # Protect pending migration and state land edits against concurrent changes.
        from mass_migration import field
        for key in ('mass_migration', 'land', 'arable_land'):
            def value(snapshot):
                text = snapshot['state_records'][sid][2]; span = field(text, key)
                return text[span[0]:span[1]] if span else None
            if value(previous) != value(fresh):
                raise ValueError(f'State {sid} {key} changed externally. Drafts retained; automatic refresh stopped.')
    return fresh
