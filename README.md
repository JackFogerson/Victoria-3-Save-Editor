# Victoria 3 Save Editor

Run `python v3_editor` with Python and Tkinter installed. Keep `cultures.json` beside the script.

The file picker starts in your user's `Documents/Paradox Interactive/Victoria 3/save games` folder when available.

In either culture field, type an ID or part of a name to immediately see matching `id (name)` results. Search is case-insensitive. Suggestions update while typing; click a result or use arrow keys and Enter. Escape dismisses suggestions without changing your input. You can also type an ID directly; unknown IDs display `id (pending)`. Scanned cultures use the same labels. Only IDs are written to the save.

Add or update entries in `cultures.json` to expand the name list, then restart the editor. The supplied mappings are user-provided.

The editor operates on text saves and replaces the selected file. Keep a backup before editing.

## Culture definitions

The Culture Definitions tab opens the installed game's `game/common/cultures/00_cultures.txt`. Use Browse for another installation or a writable copy. Search by culture ID or name and click Load Culture. Choose religion and language, then toggle goods in the obsession and taboo lists. Both lists offer the same goods; clearing all selections removes the culture's explicit list entries.

Save Culture Definition edits only the loaded culture's changed fields. It creates a dated `.bak` beside the file, preserves the other definitions, and refuses to overwrite a file modified since loading. This edits global game definitions, independently of the selected save and State ID. Windows may require write permission to the Steam game folder. Game updates may replace edited definitions.

The bundled catalog contains 317 vanilla culture keys, 15 religions, 196 languages, and 12 goods scanned from the installed file. IDs 0–316 were checked against the explicit culture database in a local save. Existing user-provided names and IDs outside that range were retained. Mods or other game versions may use different IDs. Reload refreshes choices from the selected definitions file; bundled choices remain available. Blank culture taboo lists do not remove taboos supplied by religion.

Run checks with `python -B -m unittest discover`.

## State homelands

Select a text save, enter its State ID in the top field, then open State Homelands and click Load Homelands for State ID. The editor reads that state's `region` from the save and finds the matching region in `game/common/history/states/00_states.txt`; it does not infer IDs from history-file order.

Search cultures by ID or name and click Add Homeland, or select existing homelands and click Remove Selected. A culture key such as `north_german` can also be entered directly, including modded keys. Unknown numeric IDs are rejected because history files require culture keys. Save State Homelands creates a dated backup and edits only that region's homeland entries. Changing the selected save or State ID requires reloading before saving.

These are initial game-history changes for new games, not edits to the current save. A region's homelands apply to all its split-state portions. Browse supports alternate installations or writable copies; Windows may require permission to write into the game folder.

## State resources

State Editor always uses the State ID entered at the top and resolves it through the selected save, just like State Homelands. Click Load State. The editor searches the region folder for the matching file and shows its name.

Change arable land directly. Add/remove arable building keys. Select a capped building, enter a level, and click Add / Update; the same controls add new capped buildings, and Remove deletes the selected entry. Search suggestions come from the selected folder, and manual building keys remain supported. Levels must be non-negative whole numbers. Click Save State Resources to write the loaded region's changed fields and create a dated backup. Other regions, provinces, traits, and discoverable-resource definitions are preserved. These edits affect game map definitions for new games, not the selected save.

## Experimental qualification shortage report

Run `python -B shortage_estimator.py "path/to/save.v3"`. It writes Markdown and JSON reports under `reports/` without changing the save. Use `--game "path/to/game"` for another installation.

The estimate compares each active non-subsistence building's production-method employment capacity with workers assigned to its workplace, then subtracts saved employable qualifications. Vacancies corresponds to the tooltip's “needed” number; estimated shortfall subtracts available qualifications. Profession indices are inferred from aggregate workforce and checked against pop counts. Unknown production methods and unsupported employment modifiers are reported. Country/state/building modifiers, mod load order, hiring restrictions, and rounding are not fully modeled. Check results in-game before using them to add population; the command-line report does not apply changes.

Subsistence vacancies are excluded based on the Alabama screenshot check. The revised estimate also preserves the Minsk, Baja Paraguay, North Sumatra, and Hudavendigar screenshot comparisons. This remains an inferred rule rather than a complete reproduction of the game engine.

## Automatic workforce estimates

With a save selected, entering the State ID automatically fills Modify Workforces with estimated shortfalls (vacancies minus available qualifications). The first scan runs in the background; subsequent states use a cache invalidated when the save or production-method files change. States with no shortfall get zeros. Turn off Autofill to enter amounts entirely manually, or edit filled amounts before Apply. Manual changes made during a calculation are preserved. Recalculate forces a fresh scan. Selecting another state clears previous additions while autofill is enabled.

Autofill only changes form fields. Apply Population Changes is still required to write the save. Additions are distributed exactly across existing workforce pops, including remainders. If a requested profession has no existing workforce pop, Apply reports an error instead of silently skipping it.

## Culture population percentages

In Change Culture, use Change culture population to select a culture by ID/name and enter a signed percentage: `-90` removes 90%, `+10` adds 10%, and `-100` sets workers and dependents to zero. Decimal percentages are supported. Each matching population group's workers and dependents are scaled separately and rounded to whole people (halves round up), so very small populations may not change by the exact aggregate percentage. The existing culture ID is preserved.

Apply Percentage changes only that culture in the selected State ID and creates a dated backup beside the save. It does not apply workforce autofill amounts, culture swaps, or religion swaps. A status message reports before/after totals. Missing matches or invalid percentages leave the save unchanged.
