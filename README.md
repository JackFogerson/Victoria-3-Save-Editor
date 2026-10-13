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

Culture source selectors (swap Target ID and percentage Culture) suggest only cultures with workers or dependents in the selected save/state. This list loads in the background when the save or State ID changes, independently of workforce autofill. Unknown names show `(pending)`. Replacement New ID remains unrestricted; manual ID entry remains supported.

## Laws

The Laws tab scans the installed `common/laws` folder (Browse Folder supports other installations). Search the dropdown and select a law to load it automatically. Under Ongoing Effects, select a consequence, edit its value and click Add / Update; use the searchable effect list to add a consequence, or Remove Selected to delete one. Suggestions include effects found across the loaded laws; custom modifier keys are allowed. Values are numbers or yes/no. Percentage modifiers use fractional values, such as 0.1 for 10%.

Advanced On Enactment and On Removal tabs edit effect scripts. Script structure is checked before saving, but engine semantics are not validated. Saving definitions does not replay enactment/removal events. Save Law Effects changes only the selected law, preserves unrelated content, creates a dated backup, and refuses to overwrite externally changed files. Changes apply globally to countries using that law; game-folder write permission may be needed.

## Institution law effects

When using the default game laws folder, the editor also scans enabled mods listed in `content_load.json` and selects their replacement law definitions, including `REPLACE_OR_CREATE:` entries. The selected law's full source path appears in the status line. Saving a mod law edits that mod file with a backup; Workshop updates may overwrite those edits.

The Laws tab separates **Law effects** from **Institution effects per level**. Welfare and other institution laws open on their institution effects. The table includes inherited institution effects and shows editable totals per level. Entering 0.3 for welfare payments means 30% per level; the editor calculates the law-specific adjustment automatically. Removing an inherited effect sets its total to zero for that law. This edits the chosen law, not the shared institution definition. Suggestions also include installed modifier type definitions.

After saving law definitions, fully exit and restart Victoria 3 before loading the save. Reloading a save alone should not be relied on to reload game definitions. `state_pop_qualifications_mult = 0.25` is a +25% qualification-gain modifier, not an instant grant of qualified workers.

## Primary cultures

Existing campaigns store culture obsessions and taboos in the save. In Culture Definitions, load a culture, select its goods, and click **Apply Obsessions/Taboos to Selected Save** to update those lists in the campaign. It creates a backup and preserves other culture data; reload the edited save in-game. The separate Save Culture Definition button continues to edit game definitions.

The Primary Cultures tab edits a nation's primary cultures in the selected text save. Choices load automatically. Search the nation by save ID or country tag, then search cultures by ID or name. Add Culture and Remove Selected stage changes; Save Primary Cultures writes that nation's list. At least one primary culture is required. A dated `.bak` backup is created and excluded from newest-save selection. Reload the edited save in-game. This changes national primary-culture status, not population culture identities.

## Mass migration events (experimental)

Select a text save and open Mass Migration. Choices load automatically when the selected save changes, including after applying an edit. All three fields suggest matches as you type: culture ID/name, source country ID/tag, and destination state ID/name. Click a suggestion or use the arrow keys and Enter; numeric IDs can also be entered directly. Load Migration Choices from Save remains available for a manual refresh. Choices use IDs from that save, including modded culture keys. The top State ID is used as the initial destination when available. The start date comes from the save; 1461 days defaults to roughly four years.

Create Mass Migration writes the destination state's `mass_migration` record and a linked entry in the culture's `migration` list. Existing culture migrations are preserved. No backup is created for migration edits; the completed edit replaces the selected save, leaving other bytes unchanged. Occupied destinations, same-country origins, duplicates, and stale save data are rejected. Source country is used because the game effect does not identify one origin state.

Reload the edited save and unpause to test activation. This mirrors a migration observed in a local save, but has not been validated by running a newly inserted event in-game. Eligibility, movement rates, and outcome are controlled by the game; no population is moved instantly. Reload choices before creating another event.

## Latest save and state search

The editor selects the most recently modified `.v3` file in your Victoria 3 save-games folder at startup and checks again after successful Apply/Save actions. Backups and temporary files are excluded. Browse remains available for manual selection. “Most recent” uses filesystem modification time, including edits made by this editor.

The top State ID field suggests `ID (State Name)` while typing an ID or name. Names come from the selected save and load in the background. Selecting a result keeps the numeric ID internally for every tab. Culture percentage changes affect each matching population group individually, across all professions and religions, including both workers and dependents within the selected state.

## Undiscovered resources

State Editor also scans `resource` blocks with `undiscovered_amount`. The installed files contain three types: oil rigs (150 entries, 4,757 levels), rubber plantations (108 entries, 1,779 levels), and gold fields (46 entries, 360 levels). These building keys are included in capped-resource suggestions, even in regions without an undiscovered entry.

Loading a state displays its undiscovered amounts. Selecting a matching capped-resource key suggests existing capped levels plus all undiscovered levels of that type. Level is the final capped total and remains editable. Add / Update stages conversion; Save State Resources removes matching undiscovered resource blocks and writes the capped value with a backup. Other resource types stay unchanged. Removing a staged capped entry cancels its pending conversion. A gold-field conversion uses `building_gold_field`, not `building_gold_mine`; the converted resource block, including any depletion metadata, is removed.
