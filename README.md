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

### Book Metadata (overrides chapter file metadata)
- `--title`: Override book title
- `--author`: Override author
- `--year`: Set release year
- `--genre`: Set genre
- `--comment`: Add comment/description

### Processing
- `-w, --workers`: Number of parallel workers (default: auto-detect)
- `--no-optimize`: Skip optimization step
- `--keep-temp`: Keep temporary files after completion
- `--temp-dir`: Directory for temporary files (default: <input_dir>/tmp/)
- `--max-retries`: Maximum retries for failed conversions (default: 3)

### Output Control
- `-q, --quiet`: Minimal output (errors only)
- `-v, --verbose`: Detailed output
- `--debug`: Show ffmpeg output (implies --verbose)
- `--no-color`: Disable colored output
- `--log-file`: Write output to log file

### Batch Processing
- `--batch`: Process all subdirectories as separate audiobooks
- `-r, --recursive`: Recursively search for MP3 files
- `--pattern`: File pattern to match (default: *.mp3)
- `--exclude`: Exclude files matching pattern

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
├── gui/                   # GUI components
│   ├── main_window.py     # Main GUI window
│   └── chapter_editor.py  # Chapter editor dialog
└── README.md              # This file
```

## Technical Details

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
