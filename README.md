# PostRipM4B - MP3 to M4B Audiobook Converter

PostRipM4B is a comprehensive audiobook converter designed specifically for processing output from **[LibbyRip](https://github.com/PsychedelicPalimpsest/LibbyRip)**. It converts MP3 files with embedded metadata into properly formatted M4B audiobook files with chapters, cover art, and accurate metadata.

## Features

- **Dual Interface**: Both command-line (CLI) and graphical (GUI) interfaces
- **Chapter Support**: Multiple chapter formats (Libby, ffmetadata, m4b-tool, Audacity)
- **Smart Processing**: Auto-detects optimal parallel workers and audio settings
- **Cover Art**: Automatic cover image detection and embedding
- **Metadata Preservation**: Maintains author, title, narrator, and other book information
- **Chapter Editor**: Built-in GUI editor for fine-tuning chapter timings and titles
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **iTunes Sort Name**: Writes the Sort Name tag for M4B files
- **"When done" actions**: Optionally quit, sleep, or shut down the computer after conversions finish (Batch tab or `--when-done`)

## Workflow

1. **Rip audiobook** using [LibbyRip](https://github.com/PsychedelicPalimpsest/LibbyRip)
2. **Extract the ZIP file** that LibbyRip produces
3. **Run PostRipM4B** on the extracted folder:
   - GUI Mode: `python PostRipM4b.py --gui <path-to-extracted-folder>`
   - CLI Mode: `python PostRipM4b.py <path-to-extracted-folder>`

## Quick Start

### Prerequisites
- Python 3.8 or higher
- FFmpeg installed and in your system PATH
- mutagen (for writing iTunes Sort Name)

### Installation

1. Clone the repository:
`
git clone https://github.com/yourusername/PostRipM4B.git
cd PostRipM4B
`

2. Install required packages:
`
pip install -r requirements.txt
`

3. Ensure FFmpeg is installed:
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or use your package manager
## Virtual Environment Setup

PostRipM4B requires Python 3.8+ and PyQt5. We recommend using a virtual environment to manage dependencies.

### Creating and Activating the Virtual Environment

1. **Create the virtual environment:**
`
python3 -m venv .venv
`

2. **Activate the virtual environment:**

   - **Linux/macOS:**
   `
   source .venv/bin/activate
   `

   - **Windows (Command Prompt):**
   `
   .venv\Scripts\activate
   `

   - **Windows (PowerShell):**
   `
   .venv\Scripts\Activate.ps1
   `

3. **Install required packages:**
`
pip install -r requirements.txt
`

4. **Verify installation:**
`
python PostRipM4b.py --help
`

   You should see the help message with all available options.

### Using the Convenience Script (Linux/macOS)

For easier execution on Linux/macOS, a convenience script is provided:

1. **Make the script executable:**
`
chmod +x PostRipM4B.sh
`

2. **Run the converter:**
`
./PostRipM4B.sh --gui
`

   Or with command-line arguments:
`
./PostRipM4B.sh /path/to/audiobook --bitrate 128k --title "My Book"
`

The script automatically:
- Checks for the virtual environment
- Activates it if found
- Runs the converter with proper Python environment

### Important Notes

- **Always activate the virtual environment** before running `pip install` or the converter directly
- **Your shell prompt will show `(.venv)`** when the environment is active
- **To deactivate the environment** when done, simply run:
`
deactivate
`

- **Or close the terminal** - the environment is only active in that session

### Troubleshooting Virtual Environment Issues

If you encounter "ModuleNotFoundError" for PyQt5:

1. **Ensure the virtual environment is activated** (you should see `(.venv)` in your prompt)
2. **Reinstall requirements:**
`
pip install --upgrade -r requirements.txt
`

3. **Check Python version in venv:**
`
python --version
`

4. **Verify PyQt5 is installed:**
`
pip list | grep PyQt5
`
## Usage

### GUI Mode (Recommended)
`
python PostRipM4b.py --gui /path/to/extracted/audiobook
`

The GUI provides:
- Visual configuration of all settings
- Chapter preview and editing
- Real-time progress tracking
- One-click conversion

### Command-Line Mode
`
python PostRipM4b.py /path/to/extracted/audiobook 
`

## Command-Line Options

### Input/Output
- `input_dir`: Directory containing MP3 files (default: current directory)
- `-o, --output-dir`: Output directory for M4B file (default: <input_dir>/m4b/)
- `-n, --output-name`: Output filename (without extension, defaults to book title)
- `--overwrite`: Overwrite existing output file

### Audio Quality
- `-b, --bitrate`: Audio bitrate (e.g., 64k, 128k, 256k, defaults to auto-detect)
- `--sample-rate`: Sample rate in Hz (e.g., 44100, 48000, defaults to source)
- `--channels`: Audio channels (1=mono, 2=stereo, defaults to source)

### Chapter Metadata
- `--metadata`: Path to metadata file (backward compatibility, assumes Libby format)
- `--libby-chapters`: Path to Libby metadata.json file
- `--ffmetadata-chapters`: Path to ffmetadata.txt file
- `--m4btool-chapters`: Path to m4b-tool/tone chapters.txt file
- `--audacity-chapters`: Path to Audacity label file

### Cover Art
- `--cover`: Path to cover image (default: auto-detect)
- `--no-cover`: Don't embed cover image even if available

### Book Metadata (fills in missing metadata from chapter file)

Values from the metadata/chapter file take precedence. Command-line values (and GUI entries) are used only when the metadata file does not provide a value for that field.
- `--title`: Book title (falls back to the input directory name when neither the metadata file nor `--title` provides one)
- `--author`: Author
- `--narrator`: Narrator (written to the M4B when present)
- `--year`: Set release year (empty/omitted when not provided, from metadata file, or entered in the GUI)
- `--genre`: Set genre
- `--comment`: Add comment/description
- `--track-num`: Track number (default: 1)
- `--sort-name`: iTunes sort name (default: value of `--title` if provided, otherwise from metadata file)
- `--media-type`: iTunes media type (default: 2)
- `--album`: Album tag (default: value of `--title` if provided, otherwise from metadata file)

**Title-based defaults:** The title is resolved in this order: metadata file → `--title` → input directory name. When a title is resolved and `--album`/`sort_name` are not provided by the metadata file, both `album` and `sort_name` are automatically populated with the title value. Explicit values from the metadata file take precedence. This same behavior applies in GUI mode — loading metadata will populate Sort Name and Album from the title if those fields are not already set in the source metadata.

### Processing
- `-w, --workers`: Number of parallel workers (default: auto-detect)
- `--no-optimize`: Skip optimization step
- `--keep-temp`: Keep temporary files after completion
- `--temp-dir`: Directory for temporary files (default: tracks the input dir as <input_dir>/tmp/)
- `--max-retries`: Maximum retries for failed conversions (default: 3)

### Output Control
- `-q, --quiet`: Minimal output (errors only)
- `-v, --verbose`: Detailed output
- `--debug`: Show ffmpeg output (implies --verbose)
- `--no-color`: Disable colored output
- `--log-file`: Write output to log file

### Batch Processing
- `--batch`: Process all subdirectories as separate audiobooks
- `--output-pattern`: Output filename pattern with `{title}`, `{author}`, `{year}` placeholders (default: `{title}`). Used for every book in batch mode and for the output filename in single-book mode.)
- `-r, --recursive`: Recursively search for MP3 files
- `--pattern`: File pattern to match (default: *.mp3)
- `--exclude`: Exclude files matching pattern
- `--when-done {nothing,quit,sleep,shutdown}`: Action after conversion finishes (default: none — the application just exits). Works for both single-book and batch conversions. In GUI mode this overrides the Batch tab's "When done" setting **for that session only** (it is not saved). Sleep and shutdown are skipped with a warning if the platform doesn't support them (e.g. no logind on Linux).

### Advanced
- `--ffmpeg-path`: Custom path to ffmpeg binary
- `--ffprobe-path`: Custom path to ffprobe binary
- `--force-reencode`: Force re-encoding even if source is already in target format

### GUI & Misc
- `--gui`: Launch graphical user interface
- `--version`: Show version information

### Chapter Formats Supported

1. **Libby Format** (`metadata.json`): Default format from LibbyRip
2. **FFmetadata** (`metadata.txt`): FFmpeg metadata format
3. **m4b-tool** (`chapters.txt`): Format used by m4b-tool and tone
4. **Audacity Labels**: Label files from Audacity

The converter auto-detects the format, or you can specify it with:
`
python PostRipM4b.py /path/to/audiobook --libby-chapters metadata.json
`

## Project Structure

```
PostRipM4B/
├── PostRipM4b.py          # Main converter script
├── chapter_parser.py      # Chapter format parsing module
├── requirements.txt       # Python dependencies
├── test_all_options.py    # Test the CLI command line options 
├── test_concat_file.py    # Unit tests for concat-list escaping
├── gui/                   # GUI components
│   ├── main_window.py     # Main GUI window
│   └── chapter_editor.py  # Chapter editor dialog
└── README.md              # This file
```

## Technical Details

### Key Components

1. **AudioBookConverter Class**: Main conversion engine with parallel processing
2. **chapter_parser Module**: Unified parser for multiple chapter formats
3. **Config Dataclass**: Centralized configuration management
4. **ProgressTracker Class**: Verbosity-controlled output with color support
5. **GUI Framework**: PyQt5-based interface with real-time feedback

### Conversion Process

1. **Analysis**: Scan MP3 files and detect audio properties
2. **Metadata Loading**: Parse chapter information from supported formats
3. **Parallel Conversion**: Convert MP3 to M4B using multiple workers
4. **Chapter Timing**: Calculate accurate chapter positions based on actual audio duration
5. **Assembly**: Concatenate files with metadata and cover art
6. **Optimization**: Finalize M4B file for compatibility

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
`
git clone https://github.com/zorin1/PostRipM4B.git
cd PostRipM4B
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
### Code Style
- Follow PEP 8 guidelines
- Use type hints for function signatures
- Include docstrings for public methods
- Keep the dual interface (CLI + GUI) in sync

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **[LibbyRip](https://github.com/PsychedelicPalimpsest/LibbyRip)** for the initial audiobook extraction
- **FFmpeg** team for the incredible multimedia framework
- **PyQt5** developers for the GUI framework
- **ChatGPT/OpenAI** and **Deepseek** for assistance in writing and debugging code (This project was developed with significant AI assistance)

## Troubleshooting

### Common Issues

1. **"ffmpeg not found"**
   - Ensure FFmpeg is installed and in your system PATH
   - Or specify path with `--ffmpeg-path` option

2. **"No MP3 files found"**
   - Check your input directory contains MP3 files
   - Use `--pattern` to match different file patterns

3. **"Chapter timing inaccurate"**
   - Use the GUI's chapter editor to adjust timings
   - Or manually edit chapter files before conversion

4. **Memory issues with large audiobooks**
   - Reduce worker count with `--workers` option
   - Ensure sufficient disk space for temporary files

### Getting Help
- Check the verbose output with `--verbose` or `--debug` flags
- Enable temporary file retention with `--keep-temp` for inspection
- Submit issues on GitHub with detailed error messages

## Support

For issues, questions, or feature requests:
1. Check the [GitHub Issues](https://github.com/zorin1/PostRipM4B/issues)
2. Review the troubleshooting guide above
3. Submit a detailed issue report

---

*Happy listening! If you enjoy this tool, please consider starring the repository.*

## Version 1.4.3

This release fixes conversions failing for books whose folder or file names contain an apostrophe (e.g. `G. Z. Zzz - The Snoozing Dragon's Tail`).

- **Fixed: apostrophe in paths broke concatenation**: the ffmpeg concat list wrapped each file path in single quotes without escaping, so an apostrophe in the input folder or file name terminated the quoted path early — ffmpeg then failed with "Impossible to open '...The Snoozing Dragon'". Paths are now escaped using the concat demuxer's `'\''` quoting rule, so any book or author name containing an apostrophe converts correctly.
- **Improved info glyph**: the CLI and GUI log prefix `ℹ` (which many terminals render as a bare lowercase "i") was replaced with `ⓘ`.
- **New unit test suite** (`test_concat_file.py`): verifies concat-list escaping round-trips through ffmpeg's quoting rules for paths with apostrophes (including multiple files), plus an end-to-end test that runs real ffmpeg against an apostrophe-containing path (skipped when ffmpeg is absent). Run with `./.venv/bin/python3 test_concat_file.py`.

## Version 1.4.2

This release adds a "When done" feature (inspired by HandBrake) that lets the computer take an action automatically after conversions finish — handy for overnight, unattended batch rips.

- **New Batch tab option: "After Batch Completion → When done"**: choose *Do Nothing* (default), *Quit*, *Sleep*, or *Shutdown*. The selection resets to *Do Nothing* on each launch (nothing is written to a config file). Sleep and Shutdown are greyed out automatically on systems that don't support them.
- **Cancellable countdown before any action fires**: when the batch finishes with Quit/Sleep/Shutdown selected, a 60-second countdown dialog appears so you can cancel; otherwise the action runs.
- **Confirmation before starting**: selecting Sleep or Shutdown asks for confirmation when you start a batch ("The computer will shut down when the batch finishes"). Cancelling a conversion manually never triggers an action.
- **New `--when-done` CLI flag**: `{nothing,quit,sleep,shutdown}`, default none (the application simply exits as before). Works in both CLI and GUI modes:
  - CLI: `python PostRipM4B.py --batch /path/to/books --when-done shutdown` shuts the computer down after the last book converts.
  - GUI: overrides the Batch tab's "When done" setting **for that session only**.
- **Cross-platform power actions** (`gui/power_actions.py`), mirroring HandBrake's approach per OS:
  - **Windows**: `SetSuspendState` API (sleep) and `shutdown.exe` (power off)
  - **macOS**: AppleScript via System Events
  - **Linux**: logind over D-Bus (with `CanSuspend`/`CanPowerOff` capability checks; falls back from `busctl` to `dbus-send`)

## Version 1.4.1

This release makes the temporary-file directory smarter so temporary files stay next to the audiobook being processed.

- **Temp directory defaults to the input folder**: when `--temp-dir` is not given, temporary files now live in `<input_dir>/tmp` (the folder of the audiobook being converted) instead of a global default. This keeps temp files with the book and avoids cross-book collisions.
- **Explicit `--temp-dir` is honored as a fixed override**: any value you pass is used as-is and is no longer overridden. In single-book and batch mode alike, each book derives its own `<folder>/tmp` unless you specify one manually.
- **GUI temp-directory field only used as an override**: the GUI now treats the "Temp Directory" field strictly as a manual override (cleared field = derive per-book from the input dir). Batch mode no longer forces/ignores it separately.

## Version 1.4

This release fixes batch processing and subdirectory scanning for audiobooks that span multiple folders or discs.

- **One-level subdirectory scanning**: "Search subdirectories for MP3 files" (GUI Input tab / CLI `--recursive`) scans the book folder plus its immediate subdirectories — exactly the layout of a multi-CD book like `multiple/CD01`, `multiple/CD02`. Deeper nesting is intentionally not searched. Single-book validation uses the same scan, so a book whose MP3s live in subdirectories is no longer rejected with "No MP3 files found".
- **Batch finds books at any depth**: batch scanning (GUI *Scan Subdirectories* and CLI `--batch --recursive`) walks the whole source tree and lists every audiobook it finds — for example, pointing it at `~/Music` lists `Harry Potter/Book1`, `Harry Potter/Book2`, `Harry Potter/Book3`, even though the books sit below a series folder. A folder whose audio lives in its immediate subdirectories (e.g. `Book2/CD01`, `Book2/CD02`) is treated as ONE book. Container folders (like `Harry Potter` itself) are not listed as books. The disc subdirectories of a multi-CD book are still shown in the GUI, unchecked, so you can convert a single disc on its own. When subdirectory search is off, only the source's immediate subfolders that directly contain audio are listed.

## Version 1.3.2

This release stops writing a bogus year tag and adds full narrator support.

- **Year is no longer forced to the current year**: previously the release year defaulted to today's date and was always written as a `date` tag — even when the year was unknown, and it silently overwrote a year present in the metadata file. Now the year is only written to the M4B when it's explicitly provided: via `--year`, in a metadata file, or entered in the GUI. When it's missing, no `date` tag is written at all. The GUI's year field now defaults to "Not specified" instead of today's year.
- **Narrator support added**: the narrator (e.g. from a Libby `metadata.json` `creator` entry with role `narrator`) is now written to the M4B instead of being silently discarded. Added a new `--narrator` CLI flag and a Narrator field in the GUI's Metadata tab. When no narrator is present, no narrator tag is written. Uses existing tags (`----:com.apple.iTunes:narrator` and `----:com.apple.iTunes:LYRICIST`) via mutagen.
- **Metadata precedence now matches batch mode**: values from the metadata/chapter file take precedence over command-line values, which are used only to fill in fields the file doesn't provide. This keeps batch processing correct (each book uses its own file's metadata) and fixes CLI/GUI overrides being silently discarded in the GUI.
- **GUI no longer carries stale metadata between books**: switching the source directory to a book with no metadata file now clears the previous book's values and shows the CLI/GUI defaults (e.g. `--narrator`) instead of the previous book's narrator/title/author.
- **Chapter Information updates when switching books**: switching to a book with no metadata now clears the Chapter Information section and disables the Edit Chapters button instead of leaving the previous book's chapters on screen. Late MP3-analysis results from a previously selected book are ignored so they can't repopulate the display.
- **Edit Chapters always available**: the Edit Chapters button is now always enabled, including for books with no metadata file — opening it builds chapters from the current fields so you can create and edit chapters from scratch. The editor no longer requires an author, so chapters can be used even when the author is unknown.
- **Title falls back to the book's directory name**: the title is now resolved in the order metadata file → `--title` → the name of the directory containing the MP3 files (previously, chapter-only files like `chapters.txt` produced the file's name, e.g. "chapters", as the title). Album and Sort Name are still populated from the resolved title when not set, and the GUI now shows this folder-name fallback in the Title/Album/Sort Name fields instead of leaving them blank.
- **Batch processing is always available**: the "Process all subdirectories" checkbox was removed — the Batch tab's *Scan Subdirectories* button and list are always enabled, and batch mode activates simply by checking folders in the list. CLI `--batch` now auto-populates the batch list when a source directory is set.

## Version 1.3.1

This release fixes output filename handling and improves recursive file discovery for books that span multiple folders.

- **Blank placeholders in output patterns**: `{author}` and `{year}` now expand to blank when the value is missing (e.g. `{title}-{year}` with no year gives `title-.m4b` instead of `title-title.m4b`). `{title}` still falls back to the folder name.
- **Recursive batch scanning**: the Batch tab's *Scan Subdirectories* (and CLI `--batch`) now search subdirectories recursively, so nested book folders like `Album1/Album2` are detected even when the audio lives one or more levels deep. (In 1.4 the search is refined to find books at any depth and group multi-CD folders into a single book.)
- **Correct file ordering for multi-directory books**: when *Search subdirectories for MP3 files* is enabled, files are now sorted by full path rather than filename alone, so books laid out as `CD1`, `CD2`, `CD3` are assembled in the right order instead of being interleaved.

## Version 1.3

This release makes **batch processing fully functional** in both the GUI and the CLI.

- **GUI batch mode is now working**: the "🔄 Batch" tab's *Scan Subdirectories*, *Select All*, and *Deselect All* now drive the actual conversion. Each selected folder is converted as its own independent audiobook, one at a time, with progress logs prefixed per book (e.g. `[bookname 2/5]`).
- **CLI `--batch` is now real**: previously the `--batch` flag was stored but never used. It now expands the input directory into its subdirectories and runs a separate conversion per folder.
- **Per-folder output**: each book writes to its own `<folder>/m4b` directory. The Output Directory setting (GUI Input tab / `--output-dir`) is ignored in batch mode, so books never collide.
- **Batch-specific metadata**: metadata-tab values are ignored in batch mode. Each folder auto-detects its own metadata/chapter file (`metadata/metadata.json`, `metadata.txt`, `chapters.txt`, etc.). When none is found — or fields are missing — the folder name is used as the Title/Album/Sort Name fallback, with Track = 1 and Media Type = 2. A cover image is auto-detected per folder.
- **New `--output-pattern` flag** (`{title}`, `{author}`, `{year}`): controls the output filename for every book (GUI and CLI), mirroring the Batch tab's Output Filename Pattern field.
- **Batch does not stop on failure**: if one book fails, the remaining books still convert, and a summary ("N of Y books completed successfully") is reported at the end.
- Single-book conversion behavior is unchanged.

## Version 1.2.1

- Fixed CLI metadata overrides (`--track-num`, `--album`, `--sort-name`, `--media-type`) being dropped when chapter timing adjustments were applied during conversion
- Fixed GUI not populating `--track-num`, `--sort-name`, `--album`, and `--media-type` values from CLI args in the Metadata tab
- Fixed GUI `--title` not automatically defaulting Album and Sort Name fields when `--album` and `--sort-name` are not explicitly passed

## Version 1.2.0 - Latest Updates

This release includes several improvements and refinements to enhance your audiobook conversion experience:

- Improved chapter parsing accuracy across all supported formats
- Enhanced GUI responsiveness and usability
- Optimized parallel processing for faster conversions
- Better error handling and logging for troubleshooting
- Updated dependencies for improved stability and compatibility
- Minor bug fixes and performance enhancements

Thank you for using PostRipM4B! Please continue to provide feedback and report issues on GitHub.
