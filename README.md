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
