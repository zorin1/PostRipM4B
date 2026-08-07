# Batch Processing Requirements for PostRipM4B

## Overview

This document specifies the required behavior of the **Batch** processing feature in
PostRipM4B. The feature exists in the GUI (the "🔄 Batch" tab) and as a CLI flag
(`--batch`), but today it is **not actually functional**:

- In the GUI, the `Batch` button and the widgets exist, but `Convert` ignores batch mode
  and only ever runs a single conversion against the Input-tab source folder.
- In the CLI, `--batch` is stored into `config.batch` but that field is **never read**
  anywhere in `AudioBookConverter.run()` — so `--batch` silently has no effect.

The goal is to make batch mode run a full, independent conversion for **each** selected
subdirectory (GUI) or each subdirectory (CLI), treating each folder as its own
audiobook, applying the Audio/Advanced settings and batch-specific metadata rules.

Reference files for implementers:

- `gui/main_window.py` — GUI, Batch tab, `WorkerThread`, `start_conversion`,
  `create_config_from_gui`, `scan_batch_directories`, `toggle_batch_mode`,
  `validate_inputs`.
- `PostRipM4B.py` — `Config` dataclass, `AudioBookConverter` and its `run()`,
  `_load_metadata()`, `_get_output_filename()`, `_find_cover_image()`,
  `_find_mp3_files()`; `main()` and `parse_args()`.
- `chapter_parser.py` — `Metadata` / `Chapter` classes, `load_chapters()`,
  `detect_chapter_format()`.

---

## 1. Batch Tab UI ("Scan Subdirectories" flow)

Existing widgets in `create_batch_tab` (see `gui/main_window.py`):

- `batch_check` — checkbox labeled "Process all subdirectories" (the batch-mode master).
- `batch_list` — `QListWidget`, the "Found directories:" box.
- `scan_batch_btn` — "Scan Subdirectories".
- `select_all_btn` — "Select All".
- `deselect_all_btn` — "Deselect All".
- `pattern_edit_batch` — "Output Filename Pattern" (default `{title}`).

### 1.1 "Scan Subdirectories"
1. Read the source location from the Input tab **"MP3 Files Location"** field
   (`source_edit`). If it is empty or does not exist, show a warning and do nothing.
2. Clear `batch_list`.
3. Populate it with **one entry per immediate subdirectory** of the source location
   that contains at least one MP3 file (matching the Input-tab `pattern`, default
   `*.mp3`).
4. Each item shows `FolderName (N MP3 files)` and stores the **absolute folder path**
   in item user data.

### 1.2 "Select All" / "Deselect All"
- **Select All** marks **every** entry in the list as selected.
- **Deselect All** unmarks **every** entry.
- These buttons and "Convert" must all read/write the **same** selected-state.

### 1.3 Selection semantics MUST be reconciled (bug today)
Today there are **two independent selection mechanisms** on the same widget:
- `scan_batch_directories` sets `item.setCheckState(Qt.Checked)` (line ~952), and
- "Select All"/"Deselect All" call `batch_list.selectAll()` / `clearSelection()`
  (lines ~661–663), which drive `QListWidget.MultiSelection` row-selection.

These disagree (a list item can be check-state "checked" while not row-selected, and
vice-versa), so the user cannot tell what "Convert" will process. **Fix solution:
choose one canonical mechanism and use it everywhere.** Recommended: keep the
`QListWidget` row **selection** (or item `setData(CheckStateRole, ...)`) as the single
source of truth, have scan mark items selected/checked by default, and make Select
All / Deselect All / Convert all read it from the same place.

---

## 2. "Convert" button behavior — the per-folder batch loop

Today `start_conversion` (`gui/main_window.py:1335`) builds one `Config` from `source_edit`
and runs a single conversion; it never references batch mode or `batch_list`.

### Required behavior in batch mode
1. When `batch_check` is enabled, **iterate over every selected folder** in
   `batch_list` (order as displayed).
2. For each selected folder, run a **full independent audiobook conversion** — a new
   `Config` + `AudioBookConverter.run()` per folder — so no metadata/file state leaks
   between books.
3. Run one folder at a time, streaming progress/logs through the existing
   `WorkerThread` so the GUI stays responsive.
4. A failure in one folder must **not** abort the remaining folders (unless the user
   cancels). Log clear per-folder success/failure.
5. Overall status bar and the final completion dialog must summarize the whole batch,
   e.g. "3 of 5 books completed successfully".

### Batch-loop contract (add a GUI-level orchestrator method)
Add a method such as `start_batch_conversion()` that, for each selected folder:
1. Builds a fresh `Config` (see §3) with `config.input_dir = <folder abs path>` and
   `config.output_dir` set per §4.3.
2. Resolves per-folder metadata (see §3.2/§3.5) and writes it into the `Config`.
3. Sets the output base name from `pattern_edit_batch` (§3.4) → `config.output_name`.
4. Launches the `WorkerThread`, waits for it, records the result, moves on.
5. Does **not** reuse a single `Config` across folders (metadata/track/media/album
   would leak).

---

## 3. Settings used for each book

Per-folder `Config` construction. Reuse/extend `create_config_from_gui` so it can be
called once per folder (parameterize the `input_dir`; return a fresh `Config`).

### 3.1 Audio tab — use ALL Audio settings
- Bitrate: assume auto unless `bitrate_auto` unchecked; otherwise `bitrate_combo`.
- Sample rate, channels, and the `optimize_check` / `keep_temp_check` /
  `force_reencode_check` toggles — all from the Audio tab.

### 3.2 Metadata — do NOT use Metadata tab field values
In batch mode the Metadata tab's typed fields (`title_edit`, `author_edit`,
`album_edit`, `sort_name_edit`, `year_spin`, `genre_edit`, `comment_edit`,
`track_spin`, `media_type_spin`) must be **ignored**. Per folder:

- **Auto-detect** a metadata/chapter file inside the folder, using the file
  **extension** to determine the format (reuse `chapter_parser.detect_chapter_format()` /
  `load_chapters()` and the same priority as the "Auto-detect (from file extension)"
  format). Standard locations: `{folder}/metadata/metadata.json` (Libby),
  `{folder}/metadata.txt` (ffmetadata), `{folder}/chapters.txt`,
  plus any format `detect_chapter_format()` handles.
- If **no** file is found, generate metadata (see §3.5).
- **Cover art:** always auto-detect a cover per folder via `_find_cover_image()`
  (`{folder}/cover.jpg|png`, `{folder}/metadata/*.{jpg,png,...}`), unless the
  "No cover" option is set.

### 3.3 Advanced tab — use all Advanced settings
`ffmpeg_path`, `ffprobe_path`, `temp_dir`, `max_retries`, workers (Input tab
`workers_spin`), verbosity toggles, `overwrite_check`, and `pattern_edit` (MP3 file
pattern). The Input-tab **"Output Directory" field is ignored** in batch mode —
output is always the per-folder `<folder>/m4b` (see §5.3).

### 3.4 Batch tab — Output Filename Pattern
- `pattern_edit_batch` must be honored for **every** book's output file name.
- Placeholders (as the existing label says): `{title}`, `{author}`, `{year}`.
  Replace placeholders using each folder's resolved metadata; append `.m4b`.
- **Implementation requirement:** today `_get_output_filename()`
  (`PostRipM4B.py:1249`) only reads `config.output_name` — it knows nothing about this
  pattern. Add a `Config` field (e.g. `output_pattern`) and have
  `_get_output_filename()` expand `{title}/{author}/{year}` from metadata when present,
  falling back to the title if a placeholder has no value. Do this in the core
  converter so both GUI and CLI benefit.
- **CLI support:** add a `--output-pattern` flag (default
  `{title}`, matching the GUI default). In batch mode it is used for every
  book's filename, exactly as the GUI `pattern_batch` is. In single-book mode, if
  supplied, it also drives the output filename. This flag populates the same
  `Config.output_pattern` field used by `_get_output_filename()`.
- Note on `{title}`: when no metadata file exists (or it provides no title), `{title}`
  resolves to the **folder name** (see §3.5). So with the default `{title}` pattern a
  folder `book1` without metadata produces `book1.m4b`.

### 3.5 Generated Metadata fallback
Even when a metadata file **is** found, for any missing field apply folder-name
defaults: **Title / Album / Sort Name = folder name**, **Track Number = 1**,
**Media Type = 2**. When a metadata file exists, its values win for the fields it
provides; the folder-name defaults fill only what is missing.

---

## 4. CLI `--batch` must be made real (currently dead code)

`config.batch` (PostRipM4B.py:179) is set in both `from_args()` methods and by the GUI
(1482) but is **never read** — `AudioBookConverter.run()` has no batch branch, and
`main()` calls `converter.run()` exactly once. This must be fixed:

1. In CLI mode, when `--batch` is set, `main()` must expand the input directory into its
   subdirectories (each containing matching MP3s) and run a **separate conversion per
   subdirectory**, exactly mirroring the GUI loop in §2.
2. The per-folder `output_dir` in CLI mode must follow the rules in §5.3 (each book →
   `<folder>/m4b`; any `--output-dir` is ignored in batch mode).
3. `config.batch` may be used as the trigger, but the orchestration loop (not
   `run()`) is responsible for iterating folders.
4. Keep `--batch` backward-compatible with existing flags; flags that apply to all
   books (bitrate, ffprobe paths/Ffmpeg, workers, audio settings) still do; the
   singular-metadata flags (`--title`, `--album`, `--author`, `--track-num`,
   `--media-type`) must **not** be applied in batch mode — each folder derives its own
   metadata per §3.2/§3.5.
5. Add `--output-pattern` (see §3.4) as the CLI counterpart to the Batch-tab pattern.

---

## 5. Output location and naming

### 5.1 Extension
Always `.m4b`.

### 5.2 Filename
Output name = the expanded `pattern_batch` (batch) or the title/config rule
(single-book), sanitized of characters illegal in filenames (`_get_output_filename`
already sanitizes).

### 5.3 Per-folder output directory — per-folder `<folder>/m4b`
Each selected book folder writes its `.m4b` into **its own `m4b` subdirectory**:

```
/Harry Potter/
    book1/  →  /Harry Potter/book1/m4b/book1.m4b
    book2/  →  /Harry Potter/book2/m4b/book2.m4b
```

This mirrors the existing single-book behavior where the output defaults to
`<source>/m4b` (see `update_output_dir` in `gui/main_window.py:315`). Implementation:
- For each selected folder `F`, set `config.input_dir = F` and
  `config.output_dir = F / "m4b"`.
- **The Input-tab "Output Directory" field is IGNORED (meaningless) in batch mode.**
  In batch mode it should be disabled/hidden in the GUI and must not influence output.
  Single-book mode still uses it as today.
- CLI `--batch`: the Output Directory is likewise ignored; each book writes to
  `<folder>/m4b` regardless of any `--output-dir` argument. This keeps GUI and CLI
  identical and avoids mixing books or filename collisions.

---

## 6. Validation

- Batch mode must require **at least one selected folder**; otherwise show a clear
  warning ("No directories selected") and abort.
- `validate_inputs()` today only validates the top-level `source_edit` and ignores batch
  mode. Update it so batch mode validates the selected folders and the shared output
  directory, not the Input-tab source.

---

## 7. Implementation / architecture notes

- Do **not** regress single-book (non-batch) conversion; single-book behavior must stay
  identical to today.
- Add batch orchestration **at the GUI level** (a runner that loops the selected list).
  For the CLI, add an equivalent loop in `main()`.
- Reuse `AudioBookConverter` and `WorkerThread` as-is; do not duplicate conversion
  logic.
- The `WorkerThread` already replaces `progress.*` with signals (gui/main_window.py:86–96);
  batch logging should prepend the current folder, e.g. `[Bookname 2/5]`.
- Ensure no stale `current_metadata`, `edited_metadata`, or chapter-file temp state
  carries from one folder to the next.

---

## 8. Acceptance checks

- [ ] Batch tab: Scan lists subdirs with MP3 count.
- [ ] Select All / Deselect All work and match what Convert will process (single
      source of truth).
- [ ] Convert processes each selected folder as its own audiobook and does not stop on
      a single failure.
- [ ] Audio + Advanced settings are applied to every book.
- [ ] Metadata tab values are ignored; folder-name fallback applied; Track = 1,
      Media = 2.
- [ ] Cover auto-detected per folder.
- [ ] Output Filename Pattern is applied to every output.
- [ ] CLI `--batch <dir>` loops subdirs and behaves like the GUI.
- [ ] Per-folder output directory is deterministic: each book → `<folder>/m4b`; the
      Input-tab/CLI Output Directory is ignored in batch mode.
- [ ] Single-book conversion is unchanged.