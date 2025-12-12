#!/usr/bin/env ./.venv/bin/python3
"""
PostRipM4B.py - MP3 to M4B Audiobook Converter with GUI

Converts MP3 files to M4B audiobooks with comprehensive options.
Includes both command-line and graphical interfaces.

Features:
- Parallel conversion with auto-detected optimal worker count
- Accurate chapter timing based on actual file durations
- Support for multiple chapter formats (Libby, ffmetadata, m4b-tool, Audacity)
- Cover art embedding with case-insensitive detection
- Multiple output verbosity levels (quiet, verbose, debug)
- Clean temp file management with rollback on failure
- PyQt5 GUI for easy configuration

Usage:
  CLI mode:          python PostRipM4B.py /path/to/audiobook
  GUI mode:          python PostRipM4B.py --gui
  GUI with pre-fill: python PostRipM4B.py --gui /path/to/audiobook --title "My Book"
"""

import os
import sys
import json
import glob
import subprocess
import tempfile
import concurrent.futures
import argparse
from dataclasses import dataclass, field
from datetime import timedelta
import re
from typing import Any, List, Tuple, Optional, Dict
import shutil
import time
import math
from enum import Enum
from pathlib import Path
import ctypes
import platform

# Import the new chapter parser module
import chapter_parser

# -----------------------------
# Platform-specific imports
# -----------------------------
try:
    # PyQt5 imports will be handled conditionally
    pass
except ImportError:
    pass

# -----------------------------
# Enums and Constants
# -----------------------------

class Verbosity(Enum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3

class OutputStyle(Enum):
    PLAIN = "plain"
    COLOR = "color"

# -----------------------------
# Platform-specific functions
# -----------------------------

def get_default_music_dir() -> Path:
    """Get platform-specific music directory"""
    system = platform.system()

    if system == 'Windows':
        # Windows
        try:
            # Use SHGetFolderPath for Windows
            CSIDL_MYMUSIC = 13  # My Music folder

            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_MYMUSIC, None, 0, buf)
            music_dir = Path(buf.value)
            if music_dir.exists():
                return music_dir
        except:
            pass
        # Fallback
        return Path.home() / 'Music'

    elif system == 'Darwin':
        # macOS
        music_dir = Path.home() / 'Music'
        if music_dir.exists():
            return music_dir
        return Path.home()

    else:
        # Linux and others
        # Try XDG music directory first
        xdg_music = os.getenv('XDG_MUSIC_DIR')
        if xdg_music:
            music_dir = Path(xdg_music)
            if music_dir.exists():
                return music_dir

        # Fallback to user's Music directory
        music_dir = Path.home() / 'Music'
        if music_dir.exists():
            return music_dir

        # Ultimate fallback
        return Path.home()

# -----------------------------
# Configuration Class
# -----------------------------

@dataclass
class Config:
    """Configuration for the audiobook converter"""
    # Input/Output
    input_dir: str = field(default_factory=lambda: os.getcwd())
    output_dir: str = field(default_factory=lambda: "")  # Will be set by parse_args
    output_name: Optional[str] = None
    overwrite: bool = False

    # Audio Settings
    bitrate: Optional[str] = None  # Auto-detect if None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None

    # Chapter Metadata
    chapter_format: Optional[str] = None  # 'libby', 'ffmetadata', 'm4btool', 'audacity'
    chapter_file: Optional[str] = None    # Path to chapter file

    # Keep for backward compatibility
    metadata_file: Optional[str] = None   # Deprecated, use chapter_file instead

    # Cover art
    cover_file: Optional[str] = None     # Auto-detect if None
    no_cover: bool = False

    # Book metadata (can override chapter file metadata)
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    comment: Optional[str] = None

    # Processing
    workers: Optional[int] = None  # Auto-detect if None
    no_optimize: bool = False
    keep_temp: bool = False
    temp_dir: str = field(default_factory=lambda: "")  # Will be set by parse_args
    max_retries: int = 3

    # Output Control
    verbosity: Verbosity = Verbosity.NORMAL
    style: OutputStyle = OutputStyle.COLOR
    log_file: Optional[str] = None

    # Batch Processing
    batch: bool = False
    recursive: bool = False
    pattern: str = "*.mp3"
    exclude: Optional[str] = None

    # Advanced
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None
    force_reencode: bool = False

    # NEW: For edited chapters from GUI
    edited_metadata: Optional[chapter_parser.Metadata] = None
    temp_chapter_dir: Optional[str] = None  # For cleanup

    @classmethod
    def from_args(cls, args):
        """Create Config from command-line arguments"""
        config = cls()

        # Input/Output
        if hasattr(args, 'input_dir') and args.input_dir:
            config.input_dir = os.path.abspath(args.input_dir)

        if hasattr(args, 'output_dir') and args.output_dir:
            config.output_dir = os.path.abspath(args.output_dir)

        if hasattr(args, 'output_name'):
            config.output_name = args.output_name

        if hasattr(args, 'overwrite'):
            config.overwrite = args.overwrite

        # Audio Settings
        if hasattr(args, 'bitrate'):
            config.bitrate = args.bitrate

        if hasattr(args, 'sample_rate'):
            config.sample_rate = args.sample_rate

        if hasattr(args, 'channels'):
            config.channels = args.channels

        # Chapter Metadata
        chapter_file = None
        chapter_format = None

        # Check for specific chapter format flags (new)
        if hasattr(args, 'libby_chapters') and args.libby_chapters:
            chapter_file = os.path.abspath(args.libby_chapters)
            chapter_format = 'libby'
        elif hasattr(args, 'ffmetadata_chapters') and args.ffmetadata_chapters:
            chapter_file = os.path.abspath(args.ffmetadata_chapters)
            chapter_format = 'ffmetadata'
        elif hasattr(args, 'm4btool_chapters') and args.m4btool_chapters:
            chapter_file = os.path.abspath(args.m4btool_chapters)
            chapter_format = 'm4btool'
        elif hasattr(args, 'audacity_chapters') and args.audacity_chapters:
            chapter_file = os.path.abspath(args.audacity_chapters)
            chapter_format = 'audacity'
        # Fallback to old --metadata flag for backward compatibility
        elif hasattr(args, 'metadata') and args.metadata:
            chapter_file = os.path.abspath(args.metadata)
            chapter_format = 'libby'  # Assume Libby format for backward compatibility

        config.chapter_file = chapter_file
        config.chapter_format = chapter_format

        # Keep old metadata_file for backward compatibility
        if hasattr(args, 'metadata') and args.metadata:
            config.metadata_file = os.path.abspath(args.metadata)

        # Cover image - FIXED: Check if args.cover is not None
        if hasattr(args, 'cover') and args.cover:
            config.cover_file = os.path.abspath(args.cover)
        # else: config.cover_file is already None by default

        if hasattr(args, 'no_cover'):
            config.no_cover = args.no_cover

        # Book metadata (overrides)
        if hasattr(args, 'title'):
            config.title = args.title

        if hasattr(args, 'author'):
            config.author = args.author

        if hasattr(args, 'year'):
            config.year = args.year

        if hasattr(args, 'genre'):
            config.genre = args.genre

        if hasattr(args, 'comment'):
            config.comment = args.comment

        # Processing
        if hasattr(args, 'workers'):
            config.workers = args.workers

        if hasattr(args, 'no_optimize'):
            config.no_optimize = args.no_optimize

        if hasattr(args, 'keep_temp'):
            config.keep_temp = args.keep_temp

        if hasattr(args, 'temp_dir') and args.temp_dir:
            config.temp_dir = args.temp_dir

        if hasattr(args, 'max_retries'):
            config.max_retries = args.max_retries

        # Output Control
        if hasattr(args, 'quiet') and args.quiet:
            config.verbosity = Verbosity.QUIET
        elif hasattr(args, 'debug') and args.debug:
            config.verbosity = Verbosity.DEBUG
        elif hasattr(args, 'verbose') and args.verbose:
            config.verbosity = Verbosity.VERBOSE

        if hasattr(args, 'no_color'):
            config.style = OutputStyle.PLAIN

        if hasattr(args, 'log_file') and args.log_file:
            config.log_file = args.log_file

        # Batch Processing
        if hasattr(args, 'batch'):
            config.batch = args.batch

        if hasattr(args, 'recursive'):
            config.recursive = args.recursive

        if hasattr(args, 'pattern'):
            config.pattern = args.pattern

        if hasattr(args, 'exclude') and args.exclude:
            config.exclude = args.exclude

        # Advanced
        if hasattr(args, 'ffmpeg_path') and args.ffmpeg_path:
            config.ffmpeg_path = args.ffmpeg_path

        if hasattr(args, 'ffprobe_path') and args.ffprobe_path:
            config.ffprobe_path = args.ffprobe_path

        if hasattr(args, 'force_reencode'):
            config.force_reencode = args.force_reencode

        return config

# -----------------------------
# Progress Tracker
# -----------------------------

class ProgressTracker:
    """Handles output at different verbosity levels"""

    def __init__(self, config: Config):
        self.config = config
        self.log_file = None
        self.start_time = time.time()
        self.step_start_time = None
        self.step_message = ""

        # Color codes (only used if color enabled)
        self.colors = {
            'reset': '\033[0m',
            'bold': '\033[1m',
            'dim': '\033[2m',
            'green': '\033[32m',
            'yellow': '\033[33m',
            'blue': '\033[34m',
            'magenta': '\033[35m',
            'cyan': '\033[36m',
            'success': '\033[92m',
            'warning': '\033[93m',
            'error': '\033[91m',
            'info': '\033[94m',
        }

        # Open log file if specified
        if config.log_file:
            try:
                self.log_file = open(config.log_file, 'a', encoding='utf-8')
                self._log(f"=== Conversion started at {time.ctime()} ===", to_console=False)
            except Exception as e:
                self.error(f"Could not open log file: {e}")

    def _log(self, message: str, end: str = '\n', flush: bool = False, to_console: bool = True):
        """Internal method to log messages"""
        if self.log_file:
            self.log_file.write(message + end)
            self.log_file.flush()

        # Check if we should print to console
        # Don't print if running in GUI mode (QApplication exists)
        if to_console:
            try:
                from PyQt5.QtWidgets import QApplication
                # If QApplication exists, we're likely in GUI mode
                # Skip console output to avoid interfering with GUI
                app = QApplication.instance()
                if app is not None:
                    # GUI mode detected, skip console output
                    return
            except ImportError:
                # PyQt5 not installed, not in GUI mode
                pass
            except:
                # Any other error, assume not in GUI mode
                pass

            # Not in GUI mode, print to console
            print(message, end=end, flush=flush)

    def _format(self, message: str, style: str = '') -> str:
        """Format message with color/style if enabled"""
        if self.config.style == OutputStyle.COLOR and style in self.colors:
            return f"{self.colors[style]}{message}{self.colors['reset']}"
        return message

    def header(self, message: str):
        """Display header message"""
        if self.config.verbosity.value >= Verbosity.NORMAL.value:
            self._log(f"\n{self._format('═' * 60, 'dim')}")
            self._log(self._format(f"  {message}", 'bold'))
            self._log(self._format('═' * 60, 'dim'))

    def info(self, message: str):
        """Display informational message"""
        if self.config.verbosity.value >= Verbosity.NORMAL.value:
            self._log(f"{self._format('ℹ', 'info')}  {message}")

    def success(self, message: str):
        """Display success message"""
        if self.config.verbosity.value >= Verbosity.NORMAL.value:
            self._log(f"{self._format('✓', 'success')}  {message}")

    def warning(self, message: str):
        """Display warning message"""
        if self.config.verbosity.value >= Verbosity.QUIET.value:
            self._log(f"{self._format('⚠', 'warning')}  {message}")

    def error(self, message: str):
        """Display error message"""
        if self.config.verbosity.value >= Verbosity.QUIET.value:
            self._log(f"{self._format('✗', 'error')}  {message}")

    def step_start(self, message: str):
        """Start a processing step"""
        self.step_start_time = time.time()
        self.step_message = message

        if self.config.verbosity == Verbosity.NORMAL:
            self._log(f"{self._format('▶', 'cyan')}  {message}...", end='', flush=True)
        elif self.config.verbosity.value >= Verbosity.VERBOSE.value:
            self._log(f"{self._format('▶', 'cyan')}  {message}...")

    def step_end(self, success: bool = True, extra: str = ""):
        """End a processing step"""
        if self.step_start_time:
            elapsed = time.time() - self.step_start_time

            if self.config.verbosity == Verbosity.NORMAL:
                status = self._format("✓", "success") if success else self._format("✗", "error")
                elapsed_str = f" ({elapsed:.1f}s)" if elapsed > 1 else ""
                self._log(f" {status}{elapsed_str} {extra}")
            elif self.config.verbosity.value >= Verbosity.VERBOSE.value:
                status = self._format("done", "success") if success else self._format("failed", "error")
                elapsed_str = f" in {elapsed:.1f}s" if elapsed > 1 else ""
                self._log(f"  ↳ {status}{elapsed_str} {extra}")

            self.step_start_time = None
            self.step_message = ""

    def progress(self, current: int, total: int, message: str = ""):
        """Display progress bar or percentage"""
        if self.config.verbosity == Verbosity.NORMAL:
            percent = (current / total) * 100
            bar_length = 30
            filled = int(bar_length * current // total)
            bar = '█' * filled + '░' * (bar_length - filled)
            self._log(f"\r{self._format('▏', 'cyan')} [{bar}] {percent:.1f}% ({current}/{total}) {message}",
                    end='', flush=True)
            if current == total:
                self._log("")  # New line

    def debug(self, message: str):
        """Display debug message"""
        if self.config.verbosity.value >= Verbosity.DEBUG.value:
            self._log(f"{self._format('🔧', 'dim')}  {message}")

    def ffmpeg_output(self, output: str):
        """Display ffmpeg output (only in debug mode)"""
        if self.config.verbosity == Verbosity.DEBUG:
            for line in output.strip().split('\n'):
                if line.strip():
                    self._log(f"{self._format('  ', 'dim')}{line}")

    def summary(self, stats: Dict):
        """Display conversion summary"""
        if self.config.verbosity.value >= Verbosity.NORMAL.value:
            total_time = time.time() - self.start_time

            self.header("Conversion Complete")

            self.info(f"{self._format('📁', 'cyan')}  Input: {stats.get('input_dir', 'N/A')}")
            self.info(f"{self._format('📚', 'cyan')}  Title: {stats.get('title', 'N/A')}")
            if stats.get('author'):
                self.info(f"{self._format('👤', 'cyan')}  Author: {stats['author']}")

            self.info(f"{self._format('📊', 'cyan')}  Files processed: {stats.get('file_count', 0)}")
            self.info(f"{self._format('⚙️', 'cyan')}  Settings: AAC @ {stats.get('bitrate', 'N/A')}, "
                f"{stats.get('workers', 0)} workers")

            if stats.get('output_file'):
                output_file = stats['output_file']
                output_size = stats.get('output_size_mb', 0)
                input_size = stats.get('input_size_mb', 0)

                self.success(f"{self._format('✅', 'success')}  Output: {os.path.basename(output_file)}")
                # Use info instead of _log for consistency
                size_msg = f"{self._format('💾', 'cyan')}  Size: {output_size:.2f} MB"
                if input_size > 0:
                    reduction = ((input_size - output_size) / input_size) * 100
                    size_msg += f" (from {input_size:.2f} MB MP3s, {reduction:.1f}% reduction)"
                self.info(size_msg)

            self.info(f"{self._format('⏱️', 'cyan')}  Total time: {timedelta(seconds=int(total_time))}")

            if stats.get('audio_duration') and total_time > 0:
                speed = stats['audio_duration'] / total_time
                self.info(f"{self._format('🚀', 'cyan')}  Speed: {speed:.1f}x real-time")

            self.success(f"{self._format('✨', 'success')}  Successfully completed!")

    def close(self):
        """Close log file if open"""
        if self.log_file:
            self._log(f"=== Conversion ended at {time.ctime()} ===", to_console=False)
            self.log_file.close()

# -----------------------------
# Main Converter Class
# -----------------------------

class AudioBookConverter:
    """Main converter class"""

    def __init__(self, config: Config):
        self.config = config
        self.progress = ProgressTracker(config)
        self.temp_files = []
        self.intermediate_files = []
        self.output_file = None

        # Find ffmpeg and ffprobe
        self.ffmpeg = config.ffmpeg_path or shutil.which("ffmpeg")
        self.ffprobe = config.ffprobe_path or shutil.which("ffprobe")

        if not self.ffmpeg:
            self.progress.error("ffmpeg not found. Please install ffmpeg.")
            sys.exit(1)

        if not self.ffprobe:
            self.progress.warning("ffprobe not found. Chapter timing may be less accurate.")

    def _get_ffmpeg_verbosity(self) -> str:
        """Get ffmpeg verbosity level based on config"""
        if self.config.verbosity == Verbosity.DEBUG:
            return "info"
        elif self.config.verbosity == Verbosity.VERBOSE:
            return "warning"
        else:
            return "error"

    def run(self):
        """Main conversion workflow"""
        try:
            # Setup
            self._setup_directories()

            # Load metadata - NEW: Handle edited metadata from GUI
            metadata = self._load_metadata()

            # Find files
            mp3_files = self._find_mp3_files()

            # Detect bitrate if not specified
            if not self.config.bitrate and mp3_files:
                self.config.bitrate = self._detect_bitrate(mp3_files[0])

            # Determine workers if not specified
            if not self.config.workers:
                self.config.workers = self._get_optimal_worker_count()

            # Show configuration
            self._show_config(metadata, mp3_files)

            # Convert MP3 to M4B
            self.intermediate_files = self._convert_mp3s_to_m4b(mp3_files)

            if not self.intermediate_files:
                raise RuntimeError("No files were successfully converted")

            # Get durations
            accumulated_durations = self._get_m4b_durations()

            # Create metadata.txt (ffmetadata format)
            metadata_txt = self._create_metadata_file(metadata, accumulated_durations)
            self.temp_files.append(metadata_txt)

            # Find cover image
            cover_file = self._find_cover_image()

            # Create concat file
            concat_file = self._create_concat_file()
            self.temp_files.append(concat_file)

            # Create output filename
            self.output_file = self._get_output_filename(metadata)

            # Validate temp files exist
            self.progress.step_start("Validating temporary files")
            for i, m4b_file in enumerate(self.intermediate_files):
                if not os.path.exists(m4b_file):
                    self.progress.step_end(False)
                    raise RuntimeError(f"Temp file not found: {m4b_file}")
                elif os.path.getsize(m4b_file) == 0:
                    self.progress.step_end(False)
                    raise RuntimeError(f"Temp file is empty: {m4b_file}")

            if not os.path.exists(concat_file):
                self.progress.step_end(False)
                raise RuntimeError(f"Concat file not found: {concat_file}")

            if not os.path.exists(metadata_txt):
                self.progress.step_end(False)
                raise RuntimeError(f"Metadata file not found: {metadata_txt}")

            self.progress.step_end(True, f"All {len(self.intermediate_files)} files validated")

            # Concatenate files
            intermediate_file = self.output_file.replace(".m4b", "_intermediate.m4b")
            self._concatenate_files(concat_file, metadata_txt, cover_file, intermediate_file)

            # Optimize if requested
            if not self.config.no_optimize:
                self._optimize_file(intermediate_file, self.output_file)
                self.temp_files.append(intermediate_file)
            else:
                os.rename(intermediate_file, self.output_file)

            # Cleanup - NEW: Clean up temp chapter directory
            if not self.config.keep_temp:
                self._cleanup_temp_files()

            # Show summary
            self._show_summary(metadata, mp3_files, self.output_file, accumulated_durations)

            return True

        except Exception as e:
            self.progress.error(f"Conversion failed: {str(e)}")
            if self.config.verbosity == Verbosity.DEBUG:
                import traceback
                self.progress.debug(traceback.format_exc())
            self._cleanup_temp_files()
            return False
        finally:
            self.progress.close()

    def _setup_directories(self):
        """Create necessary directories"""
        # Ensure output_dir is set
        if not self.config.output_dir:
            # Use default music directory if output_dir not specified
            self.config.output_dir = str(get_default_music_dir())

        # Ensure temp_dir is set
        if not self.config.temp_dir:
            if self.config.input_dir:
                self.config.temp_dir = os.path.join(self.config.input_dir, "tmp")
            else:
                # Fallback to output_dir/tmp
                self.config.temp_dir = os.path.join(self.config.output_dir, "tmp")

        os.makedirs(self.config.output_dir, exist_ok=True)
        os.makedirs(self.config.temp_dir, exist_ok=True)

    def _load_metadata(self) -> chapter_parser.Metadata:
        """Load metadata from file, config, or edited metadata"""
        self.progress.step_start("Loading metadata")

        # NEW: Check for edited metadata from GUI
        if self.config.edited_metadata:
            metadata = self.config.edited_metadata
            self.progress.step_end(True, f"Using edited metadata: '{metadata.title}' by {metadata.author or 'Unknown'}")
            return metadata

        # First check if we have a chapter file specified
        if self.config.chapter_file and os.path.exists(self.config.chapter_file):
            try:
                metadata = chapter_parser.load_chapters(
                    self.config.chapter_file,
                    format=self.config.chapter_format
                )

                # Override with command-line values if specified
                if self.config.title:
                    metadata = chapter_parser.Metadata(
                        title=self.config.title,
                        author=self.config.author or metadata.author,
                        narrator=metadata.narrator,
                        total_duration=metadata.total_duration,
                        chapters=metadata.chapters,
                        year=self.config.year or metadata.year,
                        genre=self.config.genre or metadata.genre,
                        comment=self.config.comment or metadata.comment
                    )

                self.progress.step_end(True, f"'{metadata.title}' by {metadata.author or 'Unknown'}")
                return metadata

            except Exception as e:
                self.progress.step_end(False)
                raise RuntimeError(f"Failed to load chapter file: {str(e)}")

        # Fallback to old auto-detection for backward compatibility
        metadata_file = self.config.metadata_file
        if not metadata_file:
            # Auto-detect metadata file
            metadata_json = os.path.join(self.config.input_dir, "metadata", "metadata.json")
            if os.path.exists(metadata_json):
                metadata_file = metadata_json
                self.config.chapter_format = 'libby'
            else:
                # Look for metadata.txt in input directory
                metadata_txt = os.path.join(self.config.input_dir, "metadata.txt")
                if os.path.exists(metadata_txt):
                    metadata_file = metadata_txt
                    self.config.chapter_format = 'ffmetadata'

        if metadata_file and os.path.exists(metadata_file):
            try:
                # Use the new parser with detected format
                metadata = chapter_parser.load_chapters(
                    metadata_file,
                    format=self.config.chapter_format
                )

                # Override with command-line values if specified
                if self.config.title:
                    metadata = chapter_parser.Metadata(
                        title=self.config.title,
                        author=self.config.author or metadata.author,
                        narrator=metadata.narrator,
                        total_duration=metadata.total_duration,
                        chapters=metadata.chapters,
                        year=self.config.year or metadata.year,
                        genre=self.config.genre or metadata.genre,
                        comment=self.config.comment or metadata.comment
                    )

                self.progress.step_end(True, f"'{metadata.title}' by {metadata.author or 'Unknown'}")
                return metadata

            except Exception as e:
                self.progress.step_end(False)
                raise RuntimeError(f"Failed to load metadata file: {str(e)}")

        # If no metadata file found, generate from config/directory name
        title = self.config.title
        if not title:
            # Use the last part of the input directory as title
            title = os.path.basename(os.path.normpath(self.config.input_dir))
            if not title or title == ".":
                title = "Unknown Title"

        self.progress.step_end(True, f"Using generated metadata: '{title}'")

        # Create minimal metadata with empty chapters
        return chapter_parser.Metadata(
            title=title,
            author=self.config.author,
            narrator=None,
            total_duration=timedelta(seconds=0),  # Will be updated later
            chapters=[],
            year=self.config.year,
            genre=self.config.genre,
            comment=self.config.comment
        )

    def _find_mp3_files(self) -> List[str]:
        """Find MP3 files in input directory"""
        self.progress.step_start("Finding MP3 files")

        import fnmatch

        mp3_files = []

        if self.config.recursive:
            for root, dirs, files in os.walk(self.config.input_dir):
                for file in files:
                    if fnmatch.fnmatch(file, self.config.pattern):
                        mp3_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(self.config.input_dir):
                if fnmatch.fnmatch(file, self.config.pattern):
                    mp3_files.append(os.path.join(self.config.input_dir, file))

        # Sort files naturally
        mp3_files.sort(key=lambda x: [int(t) if t.isdigit() else t.lower()
                                     for t in re.split(r'(\d+)', os.path.basename(x))])

        if not mp3_files:
            self.progress.step_end(False)
            raise FileNotFoundError(f"No MP3 files found in {self.config.input_dir}")

        self.progress.step_end(True, f"{len(mp3_files)} files found")
        return mp3_files

    def _detect_bitrate(self, mp3_file: str) -> str:
        """Detect bitrate from MP3 file"""
        # If bitrate was specified via command line, ensure it has 'k' suffix
        if self.config.bitrate:
            bitrate = self.config.bitrate
            if not bitrate.endswith('k'):
                bitrate = f"{bitrate}k"
            return bitrate

        # Otherwise auto-detect
        try:
            ffprobe_cmd = [self.ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=bit_rate", "-of", "default=noprint_wrappers=1:nokey=1", mp3_file]
            result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, check=True)
            bitrate = result.stdout.strip()

            if bitrate and bitrate.isdigit():
                detected_k = int(int(bitrate) / 1000)
                # Round to nearest standard bitrate
                standard_bitrates = [32, 48, 64, 96, 128, 160, 192, 256, 320]
                closest = min(standard_bitrates, key=lambda x: abs(x - detected_k))
                return f"{closest}k"
        except:
            pass

        return "64k"  # Default fallback

    def _get_optimal_worker_count(self) -> int:
        """Determine optimal number of workers"""
        try:
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            workers = max(1, cpu_count // 2)
            workers = min(workers, 8)  # Cap at 8
            return workers
        except:
            return 4  # Default fallback

    def _show_config(self, metadata: chapter_parser.Metadata, mp3_files: List[str]):
        """Show configuration summary"""
        if self.config.verbosity.value >= Verbosity.NORMAL.value:
            self.progress.header("Configuration")

            # Use progress methods instead of direct print()
            self.progress.info(f"{self.progress._format('📁', 'cyan')}  Input: {self.config.input_dir}")
            self.progress.info(f"{self.progress._format('📚', 'cyan')}  Title: {metadata.title}")
            if metadata.author:
                self.progress.info(f"{self.progress._format('👤', 'cyan')}  Author: {metadata.author}")

            self.progress.info(f"{self.progress._format('📊', 'cyan')}  Files: {len(mp3_files)} MP3 files")

            # Fix: Show bitrate with 'k' suffix
            bitrate_display = self.config.bitrate or 'auto-detect'
            if bitrate_display != 'auto-detect' and not bitrate_display.endswith('k'):
                bitrate_display = f"{bitrate_display}k"
            self.progress.info(f"{self.progress._format('⚙️', 'cyan')}  Bitrate: {bitrate_display}")

            self.progress.info(f"{self.progress._format('👷', 'cyan')}  Workers: {self.config.workers}")

            if self.config.no_optimize:
                self.progress.info(f"{self.progress._format('⚡', 'cyan')}  Optimization: Skipped")

            # Show chapter info
            if metadata.chapters:
                source = "edited metadata" if self.config.edited_metadata else "chapter file"
                if self.config.edited_metadata:
                    chapter_source = "edited in GUI"
                elif self.config.chapter_format:
                    chapter_source = f"{self.config.chapter_format} format"
                else:
                    chapter_source = "auto-detected"
                self.progress.info(f"{self.progress._format('📖', 'cyan')}  Chapters: {len(metadata.chapters)} from {chapter_source}")
            else:
                self.progress.info(f"{self.progress._format('📖', 'cyan')}  Chapters: None")

            self.progress.info("")  # Empty line

    def _convert_mp3s_to_m4b(self, mp3_files: List[str]) -> List[str]:
        """Convert MP3 files to M4B in parallel"""
        self.progress.step_start(f"Converting {len(mp3_files)} MP3 files to M4B")

        temp_files = {}
        results = []

        # Create temp files
        for i, mp3_file in enumerate(mp3_files):
            temp_filename = f"temp_part_{i+1:03d}.m4b"
            temp_file = os.path.join(self.config.temp_dir, temp_filename)
            temp_files[i] = (mp3_file, temp_file)

        # Track conversion progress
        completed = 0
        failed = 0

        # Always update progress - let the ProgressTracker decide what to do
        self.progress.progress(0, len(mp3_files))

        def worker_callback(future):
            nonlocal completed
            completed += 1
            # Always update progress
            self.progress.progress(completed, len(mp3_files))

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            # Submit all conversion tasks
            future_to_index = {}
            for i, (mp3_file, temp_file) in temp_files.items():
                future = executor.submit(self._convert_single_mp3, mp3_file, temp_file, i+1)
                future.add_done_callback(worker_callback)
                future_to_index[future] = i

            # Collect results
            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                mp3_file, temp_file = temp_files[i]
                try:
                    success, filename = future.result()
                    if success:
                        results.append((i, temp_file))
                    else:
                        failed += 1
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                except Exception as e:
                    failed += 1
                    self.progress.debug(f"Conversion failed for {os.path.basename(mp3_file)}: {e}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

        # Sort results by original index
        results.sort(key=lambda x: x[0])
        ordered_temp_files = [temp_file for _, temp_file in results]

        success_count = len(ordered_temp_files)
        self.progress.step_end(success_count > 0,
                              f"{success_count}/{len(mp3_files)} files, {failed} failed")

        return ordered_temp_files

    def _convert_single_mp3(self, mp3_path: str, output_path: str, task_id: int) -> Tuple[bool, str]:
        """Convert single MP3 file to M4B"""
        # Fix: Ensure bitrate has 'k' suffix
        bitrate = self.config.bitrate or "64k"
        if not bitrate.endswith('k'):
            bitrate = f"{bitrate}k"

        cmd = [
            self.ffmpeg, "-v", self._get_ffmpeg_verbosity(), "-nostdin",
            "-i", mp3_path,
            "-map", "0:a",  #Map only audio stream
            "-c:a", "aac",  # Always use AAC for M4B
            "-b:a", bitrate,
            "-f", "ipod",  # M4B format
            output_path,
            "-y"
        ]

        # Add sample rate if specified
        if self.config.sample_rate:
            cmd.insert(-2, "-ar")
            cmd.insert(-2, str(self.config.sample_rate))

        # Add channels if specified
        if self.config.channels:
            cmd.insert(-2, "-ac")
            cmd.insert(-2, str(self.config.channels))

        # Capture output based on verbosity
        if self.config.verbosity == Verbosity.DEBUG:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                self.progress.ffmpeg_output(f"STDOUT: {result.stdout}")
            if result.stderr:
                self.progress.ffmpeg_output(f"STDERR: {result.stderr}")
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)

        success = result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        return success, os.path.basename(mp3_path)

    def _get_m4b_durations(self) -> List[float]:
        """Get durations of all M4B files"""
        self.progress.step_start("Analyzing audio durations")

        durations = []
        accumulated = []
        total = 0.0

        for i, m4b_file in enumerate(self.intermediate_files):
            duration = self._get_audio_duration(m4b_file)
            durations.append(duration)
            total += duration
            accumulated.append(total)

            if self.config.verbosity == Verbosity.VERBOSE:
                filename = f"Part {i+1:03d}"
                self.progress.info(f"  {filename}: {duration:.2f}s (accumulated: {total:.2f}s)")

        self.progress.step_end(True, f"total: {timedelta(seconds=int(total))}")
        return accumulated

    def _get_audio_duration(self, file_path: str) -> float:
        """Get duration of audio file in seconds"""
        try:
            ffprobe_cmd = [
                self.ffprobe, "-v", self._get_ffmpeg_verbosity(),
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, check=True)
            if self.config.verbosity == Verbosity.DEBUG and result.stderr:
                self.progress.ffmpeg_output(f"ffprobe error: {result.stderr}")
            return float(result.stdout.strip())
        except Exception as e:
            if self.config.verbosity == Verbosity.DEBUG:
                self.progress.ffmpeg_output(f"ffprobe failed: {str(e)}")
            return 0.0

    def _create_metadata_file(self, metadata: chapter_parser.Metadata, accumulated_durations: List[float]) -> str:
        """Create metadata.txt file in ffmetadata format"""
        self.progress.step_start("Creating chapter metadata")

        # If we have accumulated durations, adjust chapter timings
        if accumulated_durations and metadata.chapters:
            total_seconds = accumulated_durations[-1] if accumulated_durations else 0

            # Find chapter timings based on accumulated durations
            adjusted_chapters = []
            for chapter in metadata.chapters:
                chapter_seconds = chapter.total_offset.total_seconds()

                # Find which accumulated duration this chapter belongs to
                for i, acc_duration in enumerate(accumulated_durations):
                    if chapter_seconds <= acc_duration + 0.1:
                        prev_duration = accumulated_durations[i-1] if i > 0 else 0
                        segment_offset = chapter_seconds - prev_duration
                        adjusted_seconds = segment_offset + prev_duration
                        adjusted_chapters.append(chapter_parser.Chapter(
                            title=chapter.title,
                            total_offset=timedelta(seconds=adjusted_seconds)
                        ))
                        break
                else:
                    # If chapter is beyond all accumulated durations, put at end
                    adjusted_chapters.append(chapter_parser.Chapter(
                        title=chapter.title,
                        total_offset=timedelta(seconds=total_seconds)
                    ))

            # Create adjusted metadata
            metadata = chapter_parser.Metadata(
                title=metadata.title,
                author=metadata.author,
                narrator=metadata.narrator,
                total_duration=timedelta(seconds=total_seconds),
                chapters=adjusted_chapters,
                year=metadata.year,
                genre=metadata.genre,
                comment=metadata.comment
            )

        # Create metadata.txt in ffmetadata format
        metadata_txt = os.path.join(self.config.temp_dir, "metadata.txt")

        # Use the export function from chapter_parser
        chapter_parser.export_ffmetadata(metadata, metadata_txt)

        self.progress.step_end(True, f"{len(metadata.chapters)} chapters")
        return metadata_txt

    def _find_cover_image(self) -> Optional[str]:
        """Find cover image"""
        if self.config.no_cover:
            return None

        # Use specified cover file
        if self.config.cover_file and os.path.exists(self.config.cover_file):
            return self.config.cover_file

        # Auto-detect cover image
        cover_extensions = ['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG']

        # Check in metadata directory
        metadata_dir = os.path.join(self.config.input_dir, "metadata")
        if os.path.exists(metadata_dir):
            for ext in cover_extensions:
                pattern = os.path.join(metadata_dir, f"*.{ext}")
                files = glob.glob(pattern)
                if files:
                    return files[0]

        # Check in input directory
        for ext in cover_extensions:
            pattern = os.path.join(self.config.input_dir, f"*.{ext}")
            files = glob.glob(pattern)
            if files:
                # Prefer files with "cover" in name
                for file in files:
                    if "cover" in os.path.basename(file).lower():
                        return file
                return files[0]

        return None

    def _create_concat_file(self) -> str:
        """Create concat file listing all M4B files"""
        concat_file = os.path.join(self.config.temp_dir, "concat_list.txt")

        with open(concat_file, 'w') as f:
            for m4b_file in self.intermediate_files:
                abs_path = os.path.abspath(m4b_file)
                f.write(f"file '{abs_path}'\n")

        # Debug: show contents of concat file
        if self.config.verbosity == Verbosity.DEBUG:
            with open(concat_file, 'r') as f:
                content = f.read()
                self.progress.debug(f"Concat file contents:\n{content}")

        return concat_file

    def _get_output_filename(self, metadata: chapter_parser.Metadata) -> str:
        """Determine output filename"""
        if self.config.output_name:
            filename = self.config.output_name
        else:
            # Create safe filename from title
            title = self.config.title or metadata.title
            filename = re.sub(r'[\\/*?:"<>|]', "_", title) if title else "audiobook"

        # Always use .m4b extension
        if not filename.lower().endswith(".m4b"):
            filename = f"{filename}.m4b"

        output_file = os.path.join(self.config.output_dir, filename)

        # Debug
        if self.config.verbosity == Verbosity.DEBUG:
            self.progress.debug(f"Output file path: {output_file}")
            self.progress.debug(f"Output directory exists: {os.path.exists(self.config.output_dir)}")

        # Handle overwrite
        if os.path.exists(output_file) and not self.config.overwrite:
            base, ext = os.path.splitext(output_file)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            output_file = f"{base}_{counter}{ext}"

            if self.config.verbosity == Verbosity.DEBUG:
                self.progress.debug(f"Renamed output file to avoid overwrite: {output_file}")

        return output_file

    def _concatenate_files(self, concat_file: str, metadata_txt: str,
                          cover_file: Optional[str], output_file: str):
        """Concatenate M4B files with metadata"""
        self.progress.step_start("Concatenating M4B files")

        cmd = [
            self.ffmpeg, "-y", "-v", self._get_ffmpeg_verbosity(), "-nostdin",
            "-protocol_whitelist", "file,pipe,concat",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file
        ]

        # Add cover image if available
        if cover_file:
            cmd.extend(["-i", cover_file])

        # Add metadata
        cmd.extend(["-i", metadata_txt])

        # Map streams
        if cover_file:
            cmd.extend([
                "-map", "0:a",
                "-map", "1:v",
                "-disposition:v:0", "attached_pic",
                "-map_metadata", "2",
                "-c:a", "copy",
                "-c:v", "copy",
                "-movflags", "+faststart"
            ])
        else:
            cmd.extend([
                "-map", "0:a",
                "-map_metadata", "1",
                "-c:a", "copy",
                "-movflags", "+faststart"
            ])

        # Add output file
        cmd.append(output_file)

        # Debug: Show the command being run
        if self.config.verbosity == Verbosity.DEBUG:
            self.progress.debug(f"ffmpeg command: {' '.join(cmd)}")

        # Capture output based on verbosity
        try:
            if self.config.verbosity == Verbosity.DEBUG:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.stdout:
                    self.progress.ffmpeg_output(f"ffmpeg output: {result.stdout}")
                if result.stderr:
                    self.progress.ffmpeg_output(f"ffmpeg error: {result.stderr}")
            else:
                result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                self.progress.step_end(False)
                # Show more detailed error
                error_msg = result.stderr if result.stderr else "Unknown error"
                self.progress.debug(f"Command failed with return code: {result.returncode}")
                self.progress.debug(f"Error output: {error_msg[:500]}")
                raise RuntimeError(f"Concatenation failed: {error_msg[:200]}")

            self.progress.step_end(True, f"{len(self.intermediate_files)} files combined")

        except Exception as e:
            self.progress.step_end(False)
            raise

    def _optimize_file(self, input_file: str, output_file: str):
        """Optimize M4B file"""
        if self.config.no_optimize:
            if input_file != output_file:
                shutil.move(input_file, output_file)
            return

        self.progress.step_start("Optimizing M4B file")

        cmd = [
            self.ffmpeg, "-y", "-v", self._get_ffmpeg_verbosity(), "-nostdin",
            "-i", input_file,
            "-c", "copy",
            "-f", "ipod",
            output_file
        ]

        # Capture output based on verbosity
        if self.config.verbosity == Verbosity.DEBUG:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                self.progress.ffmpeg_output(f"ffmpeg output: {result.stdout}")
            if result.stderr:
                self.progress.ffmpeg_output(f"ffmpeg error: {result.stderr}")
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.progress.warning("Optimization failed, using unoptimized file")
            if input_file != output_file:
                shutil.move(input_file, output_file)
        else:
            self.progress.step_end(True)

    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        # NEW: Clean up temp chapter directory if it exists
        if hasattr(self.config, 'temp_chapter_dir') and self.config.temp_chapter_dir:
            try:
                if os.path.exists(self.config.temp_chapter_dir):
                    shutil.rmtree(self.config.temp_chapter_dir)
                    self.progress.debug(f"Cleaned up temporary chapter directory: {self.config.temp_chapter_dir}")
            except Exception as e:
                self.progress.debug(f"Failed to clean up temp chapter directory: {e}")

        if self.config.keep_temp:
            self.progress.info("Keeping temporary files as requested")
            return

        self.progress.step_start("Cleaning up temporary files")

        cleaned = 0
        all_files = self.temp_files + self.intermediate_files

        for file_path in all_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned += 1
                except OSError:
                    pass

        # Try to remove temp directory if empty
        try:
            if os.path.exists(self.config.temp_dir) and not os.listdir(self.config.temp_dir):
                os.rmdir(self.config.temp_dir)
        except OSError:
            pass

        self.progress.step_end(True, f"{cleaned} files removed")

    def _show_summary(self, metadata: chapter_parser.Metadata, mp3_files: List[str],
                     output_file: str, accumulated_durations: List[float]):
        """Show conversion summary"""
        stats = {
            'input_dir': self.config.input_dir,
            'title': metadata.title,
            'author': metadata.author,
            'file_count': len(mp3_files),
            'bitrate': self.config.bitrate or "auto",
            'workers': self.config.workers,
            'output_file': output_file,
        }

        # Calculate sizes
        if os.path.exists(output_file):
            stats['output_size_mb'] = os.path.getsize(output_file) / (1024 * 1024)

        # Calculate input size
        try:
            input_size = sum(os.path.getsize(f) for f in mp3_files) / (1024 * 1024)
            stats['input_size_mb'] = input_size
        except:
            pass

        # Calculate audio duration
        if accumulated_durations:
            stats['audio_duration'] = accumulated_durations[-1]

        self.progress.summary(stats)

# -----------------------------
# GUI Launcher
# -----------------------------

def launch_gui(args):
    """Launch PyQt5 GUI with CLI args as defaults"""
    try:
        from PyQt5.QtWidgets import QApplication
        import sys
        import os

        # Get current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Check if gui directory exists
        gui_dir = os.path.join(current_dir, 'gui')
        if not os.path.exists(gui_dir):
            print(f"ERROR: 'gui' directory not found!")
            print(f"Expected at: {gui_dir}")
            sys.exit(1)

        # Check if main_window.py exists
        main_window_path = os.path.join(gui_dir, 'main_window.py')
        if not os.path.exists(main_window_path):
            print(f"ERROR: 'main_window.py' not found!")
            print(f"Expected at: {main_window_path}")
            sys.exit(1)

        # IMPORTANT: Add current directory to Python path
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)

        # Try to import using importlib (most reliable method)
        import importlib.util

        # Load the module
        spec = importlib.util.spec_from_file_location(
            "main_window",
            main_window_path
        )
        gui_module = importlib.util.module_from_spec(spec)

        # Execute the module
        spec.loader.exec_module(gui_module)

        # Get the ConverterMainWindow class
        if not hasattr(gui_module, 'ConverterMainWindow'):
            print("ERROR: ConverterMainWindow class not found in main_window.py")
            sys.exit(1)

        ConverterMainWindow = gui_module.ConverterMainWindow

        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("MP3 to M4B Converter")
        app.setOrganizationName("AudiobookTools")

        # Create and show main window
        window = ConverterMainWindow(args)
        window.show()

        # Start event loop
        sys.exit(app.exec_())

    except ImportError:
        print("ERROR: PyQt5 is not installed.")
        print("Please install it with: pip install PyQt5")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR launching GUI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# -----------------------------
# Command-Line Interface
# -----------------------------

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Convert MP3 files to M4B audiobooks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  CLI mode:            python PostRipM4B.py /path/to/audiobook
  CLI with options:    python PostRipM4B.py /path/to/audiobook --bitrate 128k --workers 8
  GUI mode:            python PostRipM4B.py --gui
  GUI with pre-fill:   python PostRipM4B.py --gui /path/to/audiobook --title "My Book"
        """
    )

    # GUI flag
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch graphical user interface"
    )

    # Input/Output
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=os.getcwd(),
        help="Directory containing MP3 files (default: current directory)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="Output directory for M4B file (default: <input_dir>/m4b/)"
    )
    parser.add_argument(
        "-n", "--output-name",
        help="Output filename (without extension, defaults to book title)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output file"
    )

    # Audio Quality
    parser.add_argument(
        "-b", "--bitrate",
        help="Audio bitrate (e.g., 64k, 128k, 256k, defaults to auto-detect)"
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        help="Sample rate in Hz (e.g., 44100, 48000, defaults to source)"
    )
    parser.add_argument(
        "--channels",
        type=int,
        choices=[1, 2],
        help="Audio channels (1=mono, 2=stereo, defaults to source)"
    )

    # Chapter Metadata
    chapter_group = parser.add_argument_group('Chapter Metadata')

    # Old flag for backward compatibility
    chapter_group.add_argument(
        "--metadata",
        help="Path to metadata file (default: auto-detect from ./metadata/metadata.json). "
             "Assumes Libby format. For other formats, use the specific flags below."
    )

    # New format-specific flags
    chapter_group.add_argument(
        "--libby-chapters",
        help="Path to Libby metadata.json file"
    )
    chapter_group.add_argument(
        "--ffmetadata-chapters",
        help="Path to ffmetadata.txt file"
    )
    chapter_group.add_argument(
        "--m4btool-chapters",
        help="Path to m4b-tool/tone chapters.txt file"
    )
    chapter_group.add_argument(
        "--audacity-chapters",
        help="Path to Audacity label file"
    )

    # Cover image
    parser.add_argument(
        "--cover",
        help="Path to cover image (default: auto-detect)"
    )

    # Book metadata (overrides)
    parser.add_argument(
        "--title",
        help="Override book title"
    )
    parser.add_argument(
        "--author",
        help="Override author"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Set release year"
    )
    parser.add_argument(
        "--genre",
        help="Set genre"
    )
    parser.add_argument(
        "--comment",
        help="Add comment/description"
    )

    # Processing
    parser.add_argument(
        "-w", "--workers",
        type=int,
        help="Number of parallel workers (default: auto-detect)"
    )
    parser.add_argument(
        "--no-optimize",
        action="store_true",
        help="Skip optimization step"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary files after completion"
    )
    parser.add_argument(
        "--temp-dir",
        help="Directory for temporary files (default: <input_dir>/tmp/)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries for failed conversions (default: 3)"
    )

    # Output Control
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Minimal output (errors only)"
    )
    output_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Detailed output"
    )
    output_group.add_argument(
        "--debug",
        action="store_true",
        help="Show ffmpeg output (implies --verbose)"
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    parser.add_argument(
        "--log-file",
        help="Write output to log file"
    )

    # Batch Processing
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all subdirectories as separate audiobooks"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively search for MP3 files"
    )
    parser.add_argument(
        "--pattern",
        default="*.mp3",
        help="File pattern to match (default: *.mp3)"
    )
    parser.add_argument(
        "--exclude",
        help="Exclude files matching pattern"
    )

    # Advanced
    parser.add_argument(
        "--ffmpeg-path",
        help="Custom path to ffmpeg binary"
    )
    parser.add_argument(
        "--ffprobe-path",
        help="Custom path to ffprobe binary"
    )
    parser.add_argument(
        "--no-cover",
        action="store_true",
        help="Don't embed cover image even if available"
    )
    parser.add_argument(
        "--force-reencode",
        action="store_true",
        help="Force re-encoding even if source is already in target format"
    )

    # GUI & Misc
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.10"
    )

    # Parse arguments
    args = parser.parse_args()

    # Store original values before any modifications
    original_input_dir = args.input_dir
    original_output_dir = args.output_dir

    # Convert to absolute paths FIRST
    if args.input_dir:
        args.input_dir = os.path.abspath(args.input_dir)

    if args.output_dir:
        args.output_dir = os.path.abspath(args.output_dir)

    # Check if input_dir was explicitly provided by user
    # (not just the argparse default)
    import sys
    input_dir_provided = False

    # Look for non-flag arguments in sys.argv
    # Skip script name (argv[0]) and --gui flag
    for arg in sys.argv[1:]:  # Start from 1 to skip script name
        if arg == '--gui':
            continue  # Skip the --gui flag itself
        if arg.startswith('--'):
            continue  # Skip other flags like --title, --author, etc.
        # Found a non-flag argument
        input_dir_provided = True
        break

    # Store this information on the args object
    args.input_dir_provided = input_dir_provided

    # GUI mode: special handling
    if args.gui:
        if not input_dir_provided:
            # User ran just --gui without specifying a directory
            # Clear input_dir so GUI uses Music directory default
            args.input_dir = None
            # Also clear output_dir unless explicitly provided
            if not original_output_dir:
                args.output_dir = None
        # If user provided a directory with --gui, keep it as is
    else:
        # CLI mode: always need proper defaults
        # Set output_dir default if not provided
        if not args.output_dir:
            args.output_dir = os.path.join(args.input_dir, "m4b")

    # Set temp_dir default if not provided (for both GUI and CLI)
    if args.temp_dir is None:
        if args.input_dir:
            args.temp_dir = os.path.join(args.input_dir, "tmp")
        else:
            # This handles the GUI case where input_dir is None
            args.temp_dir = os.path.join(get_default_music_dir(), "tmp")
    else:
        args.temp_dir = os.path.abspath(args.temp_dir)

    return args

# -----------------------------
# Main Entry Point
# -----------------------------

def main():
    """Main entry point"""
    # Force unbuffered output
    os.environ['PYTHONUNBUFFERED'] = '1'

    # Parse command-line arguments
    args = parse_args()

    # Launch GUI if requested
    if args.gui:
        launch_gui(args)
        return

    # Otherwise, run CLI version
    config = Config.from_args(args)
    converter = AudioBookConverter(config)
    success = converter.run()

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
