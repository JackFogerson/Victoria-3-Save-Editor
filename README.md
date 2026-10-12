# Victoria 3 Save Editor

Run `python v3_editor` with Python and Tkinter installed. Keep `cultures.json` beside the script.

The file picker starts in your user's `Documents/Paradox Interactive/Victoria 3/save games` folder when available.

In either culture field, type an ID or part of a name, then open the dropdown to see matching `id (name)` results. Search is case-insensitive. You can also type an ID directly; unknown IDs display `id (pending)`. Scanned cultures use the same labels. Only IDs are written to the save.

Add or update entries in `cultures.json` to expand the name list, then restart the editor. The supplied mappings are user-provided.

The editor operates on text saves and replaces the selected file. Keep a backup before editing.

Run checks with `python -B -m unittest test_cultures.py`.
