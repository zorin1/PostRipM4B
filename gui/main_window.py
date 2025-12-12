# gui/main_window.py (fix the import section)
import os
import sys
from pathlib import Path
import time
from datetime import timedelta
import argparse
import subprocess
import tempfile
import shutil  # Add this import

# Get the absolute path to the parent directory (where PostRipM4B.py is)
current_file = Path(__file__).resolve()
gui_dir = current_file.parent  # gui folder
project_dir = gui_dir.parent   # parent folder (where PostRipM4B.py is)

# Add project directory to Python path
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# Now we can import from PostRipM4B.py directly
try:
    # Import everything from PostRipM4B
    from PostRipM4B import (
        Config, AudioBookConverter, Verbosity, OutputStyle, get_default_music_dir,
        ProgressTracker
    )
    import chapter_parser  # NEW: Import the chapter parser
except ImportError as e:
    print(f"ERROR: Failed to import from PostRipM4B: {e}")
    raise

# PyQt5 imports
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTabWidget, QGroupBox, QLabel, QLineEdit,
                             QPushButton, QSpinBox, QComboBox, QCheckBox,
                             QTextEdit, QProgressBar, QFileDialog, QMessageBox,
                             QApplication, QGridLayout, QSplitter, QListWidget,
                             QListWidgetItem, QToolButton, QStyle, QStatusBar, QDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QIcon, QFont, QPixmap

# Import the new chapter editor - FIXED IMPORT
try:
    # First try direct import from same directory
    from chapter_editor import ChapterEditorDialog
except ImportError:
    # Try to load it dynamically
    try:
        chapter_editor_path = gui_dir / 'chapter_editor.py'
        if chapter_editor_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("chapter_editor", str(chapter_editor_path))
            chapter_editor_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(chapter_editor_module)
            ChapterEditorDialog = chapter_editor_module.ChapterEditorDialog
        else:
            print(f"ERROR: chapter_editor.py not found at {chapter_editor_path}")
            ChapterEditorDialog = None
    except Exception as e:
        print(f"ERROR: Could not load chapter_editor: {e}")
        ChapterEditorDialog = None


class WorkerThread(QThread):
    """Thread for running conversion without freezing GUI"""
    progress_signal = pyqtSignal(str, str)  # (message_type, message)
    finished_signal = pyqtSignal(bool, str)  # (success, output_file)
    stats_signal = pyqtSignal(dict)  # Conversion statistics

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.converter = None

    def run(self):
        try:
            self.converter = AudioBookConverter(self.config)

            # Store original methods for reference (though we won't call them)
            progress = self.converter.progress

            # Replace ALL output methods with signal emitters
            # This prevents console output and sends everything to GUI

            progress.step_start = lambda msg: self.progress_signal.emit('step_start', msg)
            progress.step_end = lambda success=True, extra="": self.progress_signal.emit('step_end', f"{success}:{extra}")
            progress.info = lambda msg: self.progress_signal.emit('info', msg)
            progress.header = lambda msg: self.progress_signal.emit('header', msg)
            progress.success = lambda msg: self.progress_signal.emit('success', msg)
            progress.warning = lambda msg: self.progress_signal.emit('warning', msg)
            progress.error = lambda msg: self.progress_signal.emit('error', msg)
            progress.debug = lambda msg: self.progress_signal.emit('debug', msg)
            progress.ffmpeg_output = lambda msg: self.progress_signal.emit('ffmpeg_output', msg)
            progress.summary = lambda stats: self.stats_signal.emit(stats)
            progress.progress = lambda current, total, msg="": self.progress_signal.emit('progress', f"{current}/{total}:{msg}")

            success = self.converter.run()
            self.finished_signal.emit(success, self.converter.output_file if success else "")

        except Exception as e:
            self.progress_signal.emit('error', str(e))
            self.finished_signal.emit(False, "")


class MP3AnalyzerThread(QThread):
    """Thread for analyzing MP3 files to get total duration"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(float, list)  # (total_duration, [file_durations])
    error_signal = pyqtSignal(str)

    def __init__(self, input_dir, pattern="*.mp3", recursive=False):
        super().__init__()
        self.input_dir = input_dir
        self.pattern = pattern
        self.recursive = recursive

    def run(self):
        try:
            # Find MP3 files
            import fnmatch
            import os

            mp3_files = []

            if self.recursive:
                for root, dirs, files in os.walk(self.input_dir):
                    for file in files:
                        if fnmatch.fnmatch(file, self.pattern):
                            mp3_files.append(os.path.join(root, file))
            else:
                for file in os.listdir(self.input_dir):
                    if fnmatch.fnmatch(file, self.pattern):
                        mp3_files.append(os.path.join(self.input_dir, file))

            if not mp3_files:
                self.error_signal.emit(f"No MP3 files found in {self.input_dir}")
                return

            # Sort files naturally
            import re
            mp3_files.sort(key=lambda x: [int(t) if t.isdigit() else t.lower()
                                         for t in re.split(r'(\d+)', os.path.basename(x))])

            self.progress_signal.emit(f"Found {len(mp3_files)} MP3 files")

            # Get ffprobe path
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                self.error_signal.emit("ffprobe not found. Please install ffmpeg.")
                return

            # Analyze each file
            total_duration = 0.0
            file_durations = []

            for i, mp3_file in enumerate(mp3_files):
                self.progress_signal.emit(f"Analyzing {os.path.basename(mp3_file)}...")

                try:
                    cmd = [
                        ffprobe, "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        mp3_file
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    duration = float(result.stdout.strip())
                    total_duration += duration
                    file_durations.append(duration)
                except Exception as e:
                    self.progress_signal.emit(f"Warning: Could not analyze {os.path.basename(mp3_file)}: {str(e)}")
                    file_durations.append(0.0)

            self.finished_signal.emit(total_duration, file_durations)

        except Exception as e:
            self.error_signal.emit(f"Analysis failed: {str(e)}")


class ConverterMainWindow(QMainWindow):
    def __init__(self, cli_args=None):
        super().__init__()

        # Store CLI args
        self.cli_args = cli_args

        self.config = None
        self.worker_thread = None
        self.mp3_analyzer_thread = None
        self.output_file = None
        self.current_metadata = None  # Store loaded metadata
        self.mp3_duration = 0.0  # Store total MP3 duration

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("MP3 to M4B Audiobook Converter")
        self.setGeometry(100, 100, 900, 700)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Add tabs
        self.tab_widget.addTab(self.create_input_tab(), "📁 Input")
        self.tab_widget.addTab(self.create_audio_tab(), "🔊 Audio")
        self.tab_widget.addTab(self.create_metadata_tab(), "📚 Metadata")
        self.tab_widget.addTab(self.create_advanced_tab(), "⚙️ Advanced")
        self.tab_widget.addTab(self.create_batch_tab(), "🔄 Batch")

        main_layout.addWidget(self.tab_widget)

        # Progress/output area
        main_layout.addWidget(self.create_progress_area())

        # Control buttons
        main_layout.addWidget(self.create_control_buttons())

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Now that UI is created, apply CLI args or defaults
        self.apply_cli_args_or_defaults()

        # Also apply any CLI args that were provided
        self.apply_cli_args()

        self.status_bar.showMessage("Ready")

    def create_input_tab(self):
        """Create the input/output tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Source directory
        source_group = QGroupBox("Source Directory")
        source_layout = QGridLayout()

        self.source_label = QLabel("MP3 Files Location:")
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Select directory containing MP3 files")
        self.source_browse_btn = QPushButton("Browse...")
        self.source_browse_btn.clicked.connect(self.browse_source)

        source_layout.addWidget(self.source_label, 0, 0)
        source_layout.addWidget(self.source_edit, 0, 1)
        source_layout.addWidget(self.source_browse_btn, 0, 2)

        # File options
        self.recursive_check = QCheckBox("Search subdirectories for MP3 files")
        self.pattern_edit = QLineEdit("*.mp3")
        self.exclude_edit = QLineEdit()

        source_layout.addWidget(self.recursive_check, 1, 0, 1, 2)
        source_layout.addWidget(QLabel("File pattern:"), 2, 0)
        source_layout.addWidget(self.pattern_edit, 2, 1)
        source_layout.addWidget(QLabel("Exclude pattern:"), 3, 0)
        source_layout.addWidget(self.exclude_edit, 3, 1)

        source_group.setLayout(source_layout)

        # Destination directory
        dest_group = QGroupBox("Destination")
        dest_layout = QGridLayout()

        self.dest_label = QLabel("Output Directory:")
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Where to save the M4B file")
        self.dest_browse_btn = QPushButton("Browse...")
        self.dest_browse_btn.clicked.connect(self.browse_destination)

        dest_layout.addWidget(self.dest_label, 0, 0)
        dest_layout.addWidget(self.dest_edit, 0, 1)
        dest_layout.addWidget(self.dest_browse_btn, 0, 2)

        # Output filename
        self.filename_label = QLabel("Output Filename:")
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("Leave empty to use book title")

        dest_layout.addWidget(self.filename_label, 1, 0)
        dest_layout.addWidget(self.filename_edit, 1, 1)

        # Overwrite option
        self.overwrite_check = QCheckBox("Overwrite existing file")

        dest_layout.addWidget(self.overwrite_check, 2, 0, 1, 2)

        dest_group.setLayout(dest_layout)

        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QHBoxLayout()

        perf_layout.addWidget(QLabel("Parallel Workers:"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, 16)  # 0 means Auto
        self.workers_spin.setValue(0)  # Default to Auto like CLI
        self.workers_spin.setSpecialValueText("Auto")
        perf_layout.addWidget(self.workers_spin)

        perf_layout.addStretch()
        perf_group.setLayout(perf_layout)

        # Auto-update output directory when source changes
        def update_output_dir():
            source_text = self.source_edit.text()
            if source_text and source_text.strip():
                source_path = Path(source_text.strip())
                if source_path.exists():
                    # Use source/m4b as output directory
                    output_path = source_path / 'm4b'
                    self.dest_edit.setText(str(output_path))

        # Connect the signal
        self.source_edit.textChanged.connect(update_output_dir)

        # Add to layout
        layout.addWidget(source_group)
        layout.addWidget(dest_group)
        layout.addWidget(perf_group)
        layout.addStretch()

        return tab

    def create_audio_tab(self):
        """Create the audio settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Bitrate settings
        bitrate_group = QGroupBox("Audio Quality")
        bitrate_layout = QHBoxLayout()

        self.bitrate_auto = QCheckBox("Auto-detect from source")
        self.bitrate_auto.setChecked(True)
        self.bitrate_auto.toggled.connect(self.toggle_bitrate_manual)

        self.bitrate_label = QLabel("Bitrate:")
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["64k", "96k", "128k", "160k", "192k", "256k", "320k"])
        self.bitrate_combo.setCurrentText("128k")
        self.bitrate_combo.setEnabled(False)

        bitrate_layout.addWidget(self.bitrate_auto)
        bitrate_layout.addWidget(self.bitrate_label)
        bitrate_layout.addWidget(self.bitrate_combo)
        bitrate_layout.addStretch()

        bitrate_group.setLayout(bitrate_layout)

        # Advanced audio settings
        adv_group = QGroupBox("Advanced Audio Settings")
        adv_layout = QGridLayout()

        # Sample rate
        self.sample_rate_label = QLabel("Sample Rate:")
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["Source", "22050", "44100", "48000"])
        self.sample_rate_combo.setCurrentText("Source")

        # Channels
        self.channels_label = QLabel("Channels:")
        self.channels_combo = QComboBox()
        self.channels_combo.addItems(["Source", "1 (Mono)", "2 (Stereo)"])
        self.channels_combo.setCurrentText("Source")

        adv_layout.addWidget(self.sample_rate_label, 0, 0)
        adv_layout.addWidget(self.sample_rate_combo, 0, 1)
        adv_layout.addWidget(self.channels_label, 1, 0)
        adv_layout.addWidget(self.channels_combo, 1, 1)

        adv_group.setLayout(adv_layout)

        # Processing options
        proc_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout()

        self.optimize_check = QCheckBox("Optimize final M4B file (recommended)")
        self.optimize_check.setChecked(True)

        self.keep_temp_check = QCheckBox("Keep temporary files")

        self.force_reencode_check = QCheckBox("Force re-encoding")

        proc_layout.addWidget(self.optimize_check)
        proc_layout.addWidget(self.keep_temp_check)
        proc_layout.addWidget(self.force_reencode_check)

        proc_group.setLayout(proc_layout)

        layout.addWidget(bitrate_group)
        layout.addWidget(adv_group)
        layout.addWidget(proc_group)
        layout.addStretch()

        return tab

    def create_metadata_tab(self):
        """Create the metadata tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Basic metadata
        meta_group = QGroupBox("Book Information")
        meta_layout = QGridLayout()

        meta_layout.addWidget(QLabel("Title:"), 0, 0)
        self.title_edit = QLineEdit()
        meta_layout.addWidget(self.title_edit, 0, 1, 1, 2)

        meta_layout.addWidget(QLabel("Author:"), 1, 0)
        self.author_edit = QLineEdit()
        meta_layout.addWidget(self.author_edit, 1, 1, 1, 2)

        meta_layout.addWidget(QLabel("Year:"), 2, 0)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1000, 2100)
        self.year_spin.setValue(2024)
        meta_layout.addWidget(self.year_spin, 2, 1)

        meta_layout.addWidget(QLabel("Genre:"), 2, 2)
        self.genre_edit = QLineEdit("Audiobook")
        meta_layout.addWidget(self.genre_edit, 2, 3)

        meta_layout.addWidget(QLabel("Comment:"), 3, 0)
        self.comment_edit = QLineEdit()
        self.comment_edit.setPlaceholderText("Optional comment or description")
        meta_layout.addWidget(self.comment_edit, 3, 1, 1, 3)

        meta_group.setLayout(meta_layout)

        # External files
        files_group = QGroupBox("Chapter & Cover Files")
        files_layout = QGridLayout()

        # Chapter format selection
        self.chapter_format_label = QLabel("Chapter Format:")
        self.chapter_format_combo = QComboBox()
        self.chapter_format_combo.addItems([
            "Auto-detect (from file extension)",
            "Libby (metadata.json)",
            "FFmetadata (metadata.txt)",
            "m4b-tool (chapters.txt)",
            "Audacity Labels"
        ])
        self.chapter_format_combo.currentTextChanged.connect(self.on_chapter_format_changed)

        files_layout.addWidget(self.chapter_format_label, 0, 0)
        files_layout.addWidget(self.chapter_format_combo, 0, 1)

        # Chapter file
        self.chapter_file_label = QLabel("Chapter File:")
        self.chapter_file_edit = QLineEdit()
        self.chapter_file_edit.setPlaceholderText("Select or leave empty for auto-detection")
        self.chapter_file_browse = QPushButton("Browse...")
        self.chapter_file_browse.clicked.connect(self.browse_chapter_file)
        self.chapter_file_clear = QPushButton("Clear")
        self.chapter_file_clear.clicked.connect(lambda: self.chapter_file_edit.clear())

        files_layout.addWidget(self.chapter_file_label, 1, 0)
        files_layout.addWidget(self.chapter_file_edit, 1, 1)
        files_layout.addWidget(self.chapter_file_browse, 1, 2)
        files_layout.addWidget(self.chapter_file_clear, 1, 3)

        # Cover image
        self.cover_label = QLabel("Cover Image:")
        self.cover_edit = QLineEdit()
        self.cover_edit.setPlaceholderText("Auto-detect cover.jpg/png")
        self.cover_browse = QPushButton("Browse...")
        self.cover_browse.clicked.connect(self.browse_cover_image)
        self.cover_clear = QPushButton("Clear")
        self.cover_clear.clicked.connect(lambda: self.cover_edit.clear())
        self.no_cover_check = QCheckBox("No cover")

        files_layout.addWidget(self.cover_label, 2, 0)
        files_layout.addWidget(self.cover_edit, 2, 1)
        files_layout.addWidget(self.cover_browse, 2, 2)
        files_layout.addWidget(self.cover_clear, 2, 3)
        files_layout.addWidget(self.no_cover_check, 3, 1, 1, 2)

        files_group.setLayout(files_layout)

        # Detected chapters
        self.chapters_group = QGroupBox("Chapter Information")
        self.chapters_layout = QVBoxLayout()

        # Status label
        self.chapters_status_label = QLabel("No chapters loaded")
        self.chapters_status_label.setWordWrap(True)
        self.chapters_layout.addWidget(self.chapters_status_label)

        # Chapter info display
        self.chapters_info_label = QLabel()
        self.chapters_info_label.setWordWrap(True)
        self.chapters_info_label.setVisible(False)
        self.chapters_layout.addWidget(self.chapters_info_label)

        # Buttons
        buttons_layout = QHBoxLayout()

        # Replace "Preview Chapters" with "Edit Chapters"
        self.edit_chapters_btn = QPushButton("✏️ Edit Chapters...")
        self.edit_chapters_btn.clicked.connect(self.edit_chapters)
        self.edit_chapters_btn.setEnabled(False)

        self.load_chapters_btn = QPushButton("📖 Load Chapters")
        self.load_chapters_btn.clicked.connect(self.load_and_analyze_chapters)

        buttons_layout.addWidget(self.edit_chapters_btn)
        buttons_layout.addWidget(self.load_chapters_btn)
        buttons_layout.addStretch()

        self.chapters_layout.addLayout(buttons_layout)

        # Add a note about MP3 analysis
        note_label = QLabel("Note: MP3 files will be analyzed to get accurate timing information.")
        note_label.setStyleSheet("font-style: italic; color: gray;")
        note_label.setWordWrap(True)
        self.chapters_layout.addWidget(note_label)

        self.chapters_group.setLayout(self.chapters_layout)

        layout.addWidget(meta_group)
        layout.addWidget(files_group)
        layout.addWidget(self.chapters_group)
        layout.addStretch()

        return tab

    def create_advanced_tab(self):
        """Create the advanced settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # FFmpeg paths
        ffmpeg_group = QGroupBox("FFmpeg Paths")
        ffmpeg_layout = QGridLayout()

        ffmpeg_layout.addWidget(QLabel("FFmpeg:"), 0, 0)
        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_edit.setPlaceholderText("Auto-detect")
        self.ffmpeg_browse = QPushButton("Browse...")
        self.ffmpeg_browse.clicked.connect(lambda: self.browse_executable(self.ffmpeg_edit))

        ffmpeg_layout.addWidget(self.ffmpeg_edit, 0, 1)
        ffmpeg_layout.addWidget(self.ffmpeg_browse, 0, 2)

        ffmpeg_layout.addWidget(QLabel("FFprobe:"), 1, 0)
        self.ffprobe_edit = QLineEdit()
        self.ffprobe_edit.setPlaceholderText("Auto-detect")
        self.ffprobe_browse = QPushButton("Browse...")
        self.ffprobe_browse.clicked.connect(lambda: self.browse_executable(self.ffprobe_edit))

        ffmpeg_layout.addWidget(self.ffprobe_edit, 1, 1)
        ffmpeg_layout.addWidget(self.ffprobe_browse, 1, 2)

        ffmpeg_group.setLayout(ffmpeg_layout)

        # Temporary directory
        temp_group = QGroupBox("Temporary Files")
        temp_layout = QHBoxLayout()

        self.temp_edit = QLineEdit()
        self.temp_edit.setPlaceholderText("Auto (input_dir/tmp/)")
        self.temp_browse = QPushButton("Browse...")
        self.temp_browse.clicked.connect(self.browse_temp_dir)

        temp_layout.addWidget(self.temp_edit)
        temp_layout.addWidget(self.temp_browse)

        temp_group.setLayout(temp_layout)

        # Retry settings
        retry_group = QGroupBox("Error Handling")
        retry_layout = QHBoxLayout()

        retry_layout.addWidget(QLabel("Maximum retries:"))
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        retry_layout.addWidget(self.retry_spin)
        retry_layout.addStretch()

        retry_group.setLayout(retry_layout)

        # Verbosity
        verbosity_group = QGroupBox("Output Verbosity")
        verbosity_layout = QVBoxLayout()

        self.verbosity_normal = QCheckBox("Normal (recommended)")
        self.verbosity_normal.setChecked(True)
        self.verbosity_verbose = QCheckBox("Verbose")
        self.verbosity_debug = QCheckBox("Debug (show ffmpeg output)")

        verbosity_group.setLayout(verbosity_layout)
        verbosity_layout.addWidget(self.verbosity_normal)
        verbosity_layout.addWidget(self.verbosity_verbose)
        verbosity_layout.addWidget(self.verbosity_debug)

        layout.addWidget(ffmpeg_group)
        layout.addWidget(temp_group)
        layout.addWidget(retry_group)
        layout.addWidget(verbosity_group)
        layout.addStretch()

        return tab

    def create_batch_tab(self):
        """Create the batch processing tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Batch mode
        batch_group = QGroupBox("Batch Processing")
        batch_layout = QVBoxLayout()

        self.batch_check = QCheckBox("Process all subdirectories")
        self.batch_check.toggled.connect(self.toggle_batch_mode)

        self.batch_list = QListWidget()
        self.batch_list.setSelectionMode(QListWidget.MultiSelection)

        self.scan_batch_btn = QPushButton("Scan Subdirectories")
        self.scan_batch_btn.clicked.connect(self.scan_batch_directories)

        select_buttons = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(lambda: self.batch_list.selectAll())
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(lambda: self.batch_list.clearSelection())

        select_buttons.addWidget(self.select_all_btn)
        select_buttons.addWidget(self.deselect_all_btn)
        select_buttons.addStretch()

        batch_layout.addWidget(self.batch_check)
        batch_layout.addWidget(QLabel("Found directories:"))
        batch_layout.addWidget(self.batch_list)
        batch_layout.addWidget(self.scan_batch_btn)
        batch_layout.addLayout(select_buttons)

        batch_group.setLayout(batch_layout)

        # Output pattern
        pattern_group = QGroupBox("Output Filename Pattern")
        pattern_layout = QVBoxLayout()

        self.pattern_edit_batch = QLineEdit("{title} by {author}")
        pattern_layout.addWidget(QLabel("Pattern (available: {title}, {author}, {year}):"))
        pattern_layout.addWidget(self.pattern_edit_batch)
        pattern_layout.addWidget(QLabel("Example: 'My Book by Author' becomes 'My Book by Author.m4b'"))

        pattern_group.setLayout(pattern_layout)

        layout.addWidget(batch_group)
        layout.addWidget(pattern_group)
        layout.addStretch()

        return tab

    def create_progress_area(self):
        """Create the progress/output area"""
        group = QGroupBox("Progress")
        layout = QVBoxLayout()

        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        layout.addWidget(self.log_output)

        # Stats area
        stats_layout = QGridLayout()

        self.time_label = QLabel("Time: --:--:--")
        self.eta_label = QLabel("ETA: --:--:--")
        self.speed_label = QLabel("Speed: --x")
        self.workers_label = QLabel("Workers: --")

        stats_layout.addWidget(self.time_label, 0, 0)
        stats_layout.addWidget(self.eta_label, 0, 1)
        stats_layout.addWidget(self.speed_label, 1, 0)
        stats_layout.addWidget(self.workers_label, 1, 1)

        layout.addLayout(stats_layout)

        group.setLayout(layout)
        return group

    def create_control_buttons(self):
        """Create the control buttons area"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        self.convert_btn = QPushButton("Convert")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setStyleSheet("font-weight: bold; padding: 10px;")

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_conversion)
        self.pause_btn.setEnabled(False)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_conversion)
        self.cancel_btn.setEnabled(False)

        self.open_folder_btn = QPushButton("Open Output Folder")
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.open_folder_btn.setEnabled(False)

        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)

        layout.addWidget(self.convert_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.open_folder_btn)
        layout.addWidget(self.clear_log_btn)
        layout.addStretch()

        return widget

    # Helper methods
    def browse_source(self):
        """Browse for source directory"""
        default_dir = get_default_music_dir()
        directory = QFileDialog.getExistingDirectory(
            self, "Select Source Directory",
            str(default_dir),
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.source_edit.setText(directory)
            # Auto-set output directory
            if not self.dest_edit.text():
                output_dir = Path(directory) / 'm4b'
                self.dest_edit.setText(str(output_dir))

    def browse_destination(self):
        """Browse for destination directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory",
            self.dest_edit.text() or str(get_default_music_dir()),
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.dest_edit.setText(directory)

    def browse_chapter_file(self):
        """Browse for chapter file"""
        # Determine file filter based on selected format
        format_index = self.chapter_format_combo.currentIndex()

        # Map format index to file filters
        filters = {
            0: "All supported files (*.json *.txt);;Libby JSON (*.json);;FFmetadata (*.txt);;m4b-tool chapters (*.txt);;Audacity labels (*.txt);;All files (*.*)",
            1: "Libby JSON files (*.json);;All files (*.*)",
            2: "FFmetadata files (*.txt);;All files (*.*)",
            3: "m4b-tool chapters (*.txt);;All files (*.*)",
            4: "Audacity label files (*.txt);;All files (*.*)"
        }

        file_filter = filters.get(format_index, "All files (*.*)")

        # Start from source directory if available
        start_dir = self.source_edit.text() or str(get_default_music_dir())

        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Chapter File",
            start_dir,
            file_filter
        )
        if filename:
            self.chapter_file_edit.setText(filename)
            # Try to auto-detect format if "Auto-detect" is selected
            if format_index == 0:
                detected_format = chapter_parser.detect_chapter_format(filename)
                if detected_format:
                    # Update combo box to show detected format
                    format_map = {
                        'libby': "Libby (metadata.json)",
                        'ffmetadata': "FFmetadata (metadata.txt)",
                        'm4btool': "m4b-tool (chapters.txt)",
                        'audacity': "Audacity Labels"
                    }
                    if detected_format in format_map:
                        self.chapter_format_combo.setCurrentText(format_map[detected_format])

    def browse_cover_image(self):
        """Browse for cover image"""
        file_filter = "Image files (*.jpg *.jpeg *.png *.bmp);;All files (*.*)"
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image",
            self.source_edit.text() or str(get_default_music_dir()),
            file_filter
        )
        if filename:
            self.cover_edit.setText(filename)

    def browse_executable(self, line_edit):
        """Browse for executable file"""
        file_filter = "Executable files (*.exe);;All files (*.*)" if sys.platform == 'win32' else "All files (*.*)"
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Executable",
            line_edit.text() or "",
            file_filter
        )
        if filename:
            line_edit.setText(filename)

    def browse_temp_dir(self):
        """Browse for temporary directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Temporary Directory",
            self.temp_edit.text() or self.source_edit.text(),
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.temp_edit.setText(directory)

    def toggle_bitrate_manual(self, checked):
        """Enable/disable manual bitrate selection"""
        self.bitrate_combo.setEnabled(not checked)

    def toggle_batch_mode(self, checked):
        """Enable/disable batch mode controls"""
        self.batch_list.setEnabled(checked)
        self.scan_batch_btn.setEnabled(checked)
        self.select_all_btn.setEnabled(checked)
        self.deselect_all_btn.setEnabled(checked)
        self.pattern_edit_batch.setEnabled(checked)

    def on_chapter_format_changed(self, text):
        """Handle chapter format selection change"""
        pass

    def scan_batch_directories(self):
        """Scan for subdirectories with MP3 files"""
        source_dir = self.source_edit.text()
        if not source_dir or not Path(source_dir).exists():
            QMessageBox.warning(self, "Warning", "Please select a valid source directory first")
            return

        self.batch_list.clear()
        source_path = Path(source_dir)

        for item in source_path.iterdir():
            if item.is_dir():
                # Check if directory contains MP3 files
                mp3_files = list(item.glob("*.mp3"))
                if mp3_files:
                    item_text = f"{item.name} ({len(mp3_files)} MP3 files)"
                    list_item = QListWidgetItem(item_text)
                    list_item.setData(Qt.UserRole, str(item))
                    list_item.setCheckState(Qt.Checked)
                    self.batch_list.addItem(list_item)

    def load_and_analyze_chapters(self):
        """Load chapters and analyze MP3 files for duration"""
        chapter_file = self.chapter_file_edit.text()

        # If no chapter file specified, try to auto-detect
        if not chapter_file or not Path(chapter_file).exists():
            # Try auto-detection
            source_dir = self.source_edit.text()
            if not source_dir or not Path(source_dir).exists():
                QMessageBox.warning(self, "Warning", "Please select a valid source directory first")
                return

            # Look for common chapter files
            possible_files = [
                Path(source_dir) / "metadata" / "metadata.json",
                Path(source_dir) / "metadata.txt",
                Path(source_dir) / "chapters.txt"
            ]

            for file_path in possible_files:
                if file_path.exists():
                    chapter_file = str(file_path)
                    self.chapter_file_edit.setText(chapter_file)
                    break

            if not chapter_file:
                QMessageBox.warning(self, "Warning",
                                  "No chapter file specified and none could be auto-detected.")
                return

        try:
            # Get selected format
            format_text = self.chapter_format_combo.currentText()
            format_map = {
                "Auto-detect (from file extension)": None,
                "Libby (metadata.json)": 'libby',
                "FFmetadata (metadata.txt)": 'ffmetadata',
                "m4b-tool (chapters.txt)": 'm4btool',
                "Audacity Labels": 'audacity'
            }

            chapter_format = format_map.get(format_text)

            # Load chapters
            self.current_metadata = chapter_parser.load_chapters(chapter_file, format=chapter_format)

            # Update metadata fields if they're empty
            if not self.title_edit.text() and self.current_metadata.title:
                self.title_edit.setText(self.current_metadata.title)
            if not self.author_edit.text() and self.current_metadata.author:
                self.author_edit.setText(self.current_metadata.author)

            # Show loading message
            self.chapters_status_label.setText("Loading chapters...")
            self.chapters_info_label.setVisible(False)
            self.edit_chapters_btn.setEnabled(False)

            # Start MP3 analysis to get accurate duration
            self.analyze_mp3_duration()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load chapters: {str(e)}")

    def analyze_mp3_duration(self):
        """Analyze MP3 files to get total duration"""
        source_dir = self.source_edit.text()
        if not source_dir or not Path(source_dir).exists():
            QMessageBox.warning(self, "Warning", "Please select a valid source directory first")
            return

        # Show progress
        self.chapters_status_label.setText("Analyzing MP3 files for accurate timing...")
        self.status_bar.showMessage("Analyzing MP3 files...")

        # Create and start analyzer thread
        self.mp3_analyzer_thread = MP3AnalyzerThread(
            source_dir,
            pattern=self.pattern_edit.text(),
            recursive=self.recursive_check.isChecked()
        )

        self.mp3_analyzer_thread.progress_signal.connect(self.on_mp3_analysis_progress)
        self.mp3_analyzer_thread.finished_signal.connect(self.on_mp3_analysis_finished)
        self.mp3_analyzer_thread.error_signal.connect(self.on_mp3_analysis_error)
        self.mp3_analyzer_thread.start()

    def on_mp3_analysis_progress(self, message):
        """Handle MP3 analysis progress updates"""
        self.chapters_status_label.setText(message)

    def on_mp3_analysis_finished(self, total_duration, file_durations):
        """Handle MP3 analysis completion"""
        self.mp3_duration = total_duration

        # Update UI with chapter information
        self.update_chapter_display()

        # Enable edit button
        self.edit_chapters_btn.setEnabled(True)

        self.status_bar.showMessage(f"MP3 analysis complete: {timedelta(seconds=int(total_duration))}")

    def on_mp3_analysis_error(self, error_message):
        """Handle MP3 analysis error"""
        # Use estimated duration from metadata if available
        if self.current_metadata:
            self.mp3_duration = self.current_metadata.total_duration.total_seconds()
            self.update_chapter_display()
            self.edit_chapters_btn.setEnabled(True)

            QMessageBox.warning(self, "Warning",
                              f"{error_message}\n\nUsing estimated duration from chapter file: {timedelta(seconds=int(self.mp3_duration))}")
        else:
            QMessageBox.warning(self, "Error", error_message)

    def update_chapter_display(self):
        """Update the chapter display with loaded information"""
        if not self.current_metadata:
            return

        # Update status label
        self.chapters_status_label.setText(f"✅ Loaded {len(self.current_metadata.chapters)} chapters")

        # Update info label with chapter details
        info_text = f"<b>Title:</b> {self.current_metadata.title}<br>"
        if self.current_metadata.author:
            info_text += f"<b>Author:</b> {self.current_metadata.author}<br>"

        # Use analyzed duration if available, otherwise use metadata duration
        duration = self.mp3_duration if self.mp3_duration > 0 else self.current_metadata.total_duration.total_seconds()
        info_text += f"<b>Total duration:</b> {timedelta(seconds=int(duration))}<br>"
        info_text += f"<b>Chapters:</b> {len(self.current_metadata.chapters)}"

        self.chapters_info_label.setText(info_text)
        self.chapters_info_label.setVisible(True)

    def edit_chapters(self):
        """Open the chapter editor dialog"""
        if not self.current_metadata:
            QMessageBox.warning(self, "Warning", "No chapters loaded. Please load chapters first.")
            return

        if ChapterEditorDialog is None:
            QMessageBox.warning(self, "Error", "Chapter editor module not available.")
            return

        # Create editor dialog
        editor = ChapterEditorDialog(
            self.current_metadata,
            self.mp3_duration,
            self
        )

        # Connect signal for updated metadata
        editor.chapters_updated.connect(self.on_chapters_updated)

        # Show dialog
        if editor.exec_() == QDialog.Accepted:
            # The signal handler will update everything
            pass

    def on_chapters_updated(self, updated_metadata):
        """Handle updated metadata from chapter editor"""
        self.current_metadata = updated_metadata
        self.update_chapter_display()

        # Update metadata fields
        self.title_edit.setText(updated_metadata.title or "")
        self.author_edit.setText(updated_metadata.author or "")
        if updated_metadata.year:
            self.year_spin.setValue(updated_metadata.year)
        if updated_metadata.genre:
            self.genre_edit.setText(updated_metadata.genre)
        if updated_metadata.comment:
            self.comment_edit.setText(updated_metadata.comment)

        QMessageBox.information(self, "Chapters Updated",
                              f"Updated {len(updated_metadata.chapters)} chapters.")

    def apply_cli_args_or_defaults(self):
        """Apply CLI arguments if provided, otherwise set defaults"""
        # Get default Music directory
        default_music_dir = str(get_default_music_dir())
        default_output_dir = str(Path(default_music_dir) / 'm4b')

        # Check if user provided an input directory via CLI
        user_provided_dir = False
        if (self.cli_args and
            hasattr(self.cli_args, 'input_dir_provided') and
            self.cli_args.input_dir_provided and
            hasattr(self.cli_args, 'input_dir') and
            self.cli_args.input_dir):
            user_provided_dir = True

        if user_provided_dir:
            # User explicitly provided a directory via CLI
            source_dir = str(Path(self.cli_args.input_dir).absolute())
            self.source_edit.setText(source_dir)

            # Set output directory
            if hasattr(self.cli_args, 'output_dir') and self.cli_args.output_dir:
                self.dest_edit.setText(str(Path(self.cli_args.output_dir).absolute()))
            else:
                # Default to source/m4b
                output_dir = str(Path(source_dir) / 'm4b')
                self.dest_edit.setText(output_dir)

            # Set temp directory if provided
            if hasattr(self.cli_args, 'temp_dir') and self.cli_args.temp_dir:
                self.temp_edit.setText(str(Path(self.cli_args.temp_dir).absolute()))
        else:
            # No directory provided via CLI, use Music directory default
            self.source_edit.setText(default_music_dir)
            self.dest_edit.setText(default_output_dir)
            # Leave temp dir empty for auto-detection

    def apply_cli_args(self):
        """Apply CLI arguments to GUI fields"""
        if not self.cli_args:
            return

        # Check if user provided an input directory
        user_provided_dir = False
        if (hasattr(self.cli_args, 'input_dir_provided') and
            self.cli_args.input_dir_provided and
            hasattr(self.cli_args, 'input_dir') and
            self.cli_args.input_dir):
            user_provided_dir = True

        # Only apply input/output directory if user provided them
        if user_provided_dir:
            # Input/Output settings
            if hasattr(self.cli_args, 'input_dir') and self.cli_args.input_dir:
                source_dir = str(Path(self.cli_args.input_dir).absolute())
                self.source_edit.setText(source_dir)
                # Auto-update output directory based on new source
                if not hasattr(self.cli_args, 'output_dir') or not self.cli_args.output_dir:
                    output_dir = str(Path(source_dir) / 'm4b')
                    self.dest_edit.setText(output_dir)

            if hasattr(self.cli_args, 'output_dir') and self.cli_args.output_dir:
                self.dest_edit.setText(str(Path(self.cli_args.output_dir).absolute()))

            if hasattr(self.cli_args, 'output_name') and self.cli_args.output_name:
                self.filename_edit.setText(self.cli_args.output_name)

            if hasattr(self.cli_args, 'overwrite') and self.cli_args.overwrite:
                self.overwrite_check.setChecked(True)

        # Audio settings
        if hasattr(self.cli_args, 'bitrate') and self.cli_args.bitrate:
            self.bitrate_auto.setChecked(False)
            self.bitrate_combo.setCurrentText(self.cli_args.bitrate)

        if hasattr(self.cli_args, 'sample_rate') and self.cli_args.sample_rate:
            if self.cli_args.sample_rate == 'source':
                self.sample_rate_combo.setCurrentText("Source")
            else:
                self.sample_rate_combo.setCurrentText(str(self.cli_args.sample_rate))

        if hasattr(self.cli_args, 'channels') and self.cli_args.channels:
            if self.cli_args.channels == 'source':
                self.channels_combo.setCurrentText("Source")
            elif self.cli_args.channels == 1:
                self.channels_combo.setCurrentText("1 (Mono)")
            elif self.cli_args.chapters == 2:
                self.channels_combo.setCurrentText("2 (Stereo)")

        # Metadata settings
        if hasattr(self.cli_args, 'title') and self.cli_args.title:
            self.title_edit.setText(self.cli_args.title)

        if hasattr(self.cli_args, 'author') and self.cli_args.author:
            self.author_edit.setText(self.cli_args.author)

        if hasattr(self.cli_args, 'year') and self.cli_args.year:
            self.year_spin.setValue(int(self.cli_args.year))

        if hasattr(self.cli_args, 'genre') and self.cli_args.genre:
            self.genre_edit.setText(self.cli_args.genre)

        if hasattr(self.cli_args, 'comment') and self.cli_args.comment:
            self.comment_edit.setText(self.cli_args.comment)

        # Chapter files
        chapter_file = None
        chapter_format = None

        # Check for specific chapter format flags
        if hasattr(self.cli_args, 'libby_chapters') and self.cli_args.libby_chapters:
            chapter_file = str(Path(self.cli_args.libby_chapters).absolute())
            chapter_format = "Libby (metadata.json)"
        elif hasattr(self.cli_args, 'ffmetadata_chapters') and self.cli_args.ffmetadata_chapters:
            chapter_file = str(Path(self.cli_args.ffmetadata_chapters).absolute())
            chapter_format = "FFmetadata (metadata.txt)"
        elif hasattr(self.cli_args, 'm4btool_chapters') and self.cli_args.m4btool_chapters:
            chapter_file = str(Path(self.cli_args.m4btool_chapters).absolute())
            chapter_format = "m4b-tool (chapters.txt)"
        elif hasattr(self.cli_args, 'audacity_chapters') and self.cli_args.audacity_chapters:
            chapter_file = str(Path(self.cli_args.audacity_chapters).absolute())
            chapter_format = "Audacity Labels"
        # Fallback to old --metadata flag for backward compatibility
        elif hasattr(self.cli_args, 'metadata') and self.cli_args.metadata:
            chapter_file = str(Path(self.cli_args.metadata).absolute())
            chapter_format = "Libby (metadata.json)"

        if chapter_file:
            self.chapter_file_edit.setText(chapter_file)
            if chapter_format:
                self.chapter_format_combo.setCurrentText(chapter_format)

        # Cover image
        if hasattr(self.cli_args, 'cover') and self.cli_args.cover:
            self.cover_edit.setText(str(Path(self.cli_args.cover).absolute()))
        elif hasattr(self.cli_args, 'no_cover') and self.cli_args.no_cover:
            self.no_cover_check.setChecked(True)

        # Processing settings
        if hasattr(self.cli_args, 'workers') and self.cli_args.workers:
            self.workers_spin.setValue(self.cli_args.workers)

        if hasattr(self.cli_args, 'no_optimize') and self.cli_args.no_optimize:
            self.optimize_check.setChecked(False)

        if hasattr(self.cli_args, 'keep_temp') and self.cli_args.keep_temp:
            self.keep_temp_check.setChecked(True)

        if hasattr(self.cli_args, 'force_reencode') and self.cli_args.force_reencode:
            self.force_reencode_check.setChecked(True)

        # Temporary directory
        if hasattr(self.cli_args, 'temp_dir') and self.cli_args.temp_dir:
            self.temp_edit.setText(str(Path(self.cli_args.temp_dir).absolute()))

        # Retry settings
        if hasattr(self.cli_args, 'max_retries') and self.cli_args.max_retries:
            self.retry_spin.setValue(self.cli_args.max_retries)

        # FFmpeg paths
        if hasattr(self.cli_args, 'ffmpeg_path') and self.cli_args.ffmpeg_path:
            self.ffmpeg_edit.setText(str(Path(self.cli_args.ffmpeg_path).absolute()))

        if hasattr(self.cli_args, 'ffprobe_path') and self.cli_args.ffprobe_path:
            self.ffprobe_edit.setText(str(Path(self.cli_args.ffprobe_path).absolute()))

        # Verbosity
        if hasattr(self.cli_args, 'debug') and self.cli_args.debug:
            self.verbosity_debug.setChecked(True)
        elif hasattr(self.cli_args, 'verbose') and self.cli_args.verbose:
            self.verbosity_verbose.setChecked(True)
        else:
            self.verbosity_normal.setChecked(True)

        # Batch processing
        if hasattr(self.cli_args, 'batch') and self.cli_args.batch:
            self.batch_check.setChecked(True)

        if hasattr(self.cli_args, 'recursive') and self.cli_args.recursive:
            self.recursive_check.setChecked(True)

        if hasattr(self.cli_args, 'pattern') and self.cli_args.pattern:
            self.pattern_edit.setText(self.cli_args.pattern)

        if hasattr(self.cli_args, 'exclude') and self.cli_args.exclude:
            self.exclude_edit.setText(self.cli_args.exclude)

    def start_conversion(self):
        """Start the conversion process"""
        # Validate inputs
        if not self.validate_inputs():
            return

        # Reset UI elements for new conversion
        self.progress_bar.setValue(0)
        self.log_output.clear()

        # Reset status labels
        self.time_label.setText("Time: --:--:--")
        self.eta_label.setText("ETA: --:--:--")
        self.speed_label.setText("Speed: --x")
        self.workers_label.setText("Workers: --")

        # Clear previous output file reference
        self.output_file = None
        self.open_folder_btn.setEnabled(False)

        # Create config from GUI
        self.config = self.create_config_from_gui()

        # Disable controls during conversion
        self.set_conversion_controls(False)

        # Start worker thread
        self.worker_thread = WorkerThread(self.config)
        self.worker_thread.progress_signal.connect(self.update_progress)
        self.worker_thread.finished_signal.connect(self.conversion_finished)
        self.worker_thread.stats_signal.connect(self.update_stats)
        self.worker_thread.start()

        # Start timer for elapsed time
        self.start_time = time.time()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)

        self.status_bar.showMessage("Conversion started...")

    def create_config_from_gui(self):
        """Create Config object from GUI values"""
        config = Config()

        # Input/Output
        config.input_dir = self.source_edit.text()
        config.output_dir = self.dest_edit.text()
        config.output_name = self.filename_edit.text() or None
        config.overwrite = self.overwrite_check.isChecked()

        # Audio settings
        if not self.bitrate_auto.isChecked():
            config.bitrate = self.bitrate_combo.currentText()

        sample_rate_text = self.sample_rate_combo.currentText()
        if sample_rate_text != "Source":
            config.sample_rate = int(sample_rate_text)

        channels_text = self.channels_combo.currentText()
        if channels_text == "1 (Mono)":
            config.channels = 1
        elif channels_text == "2 (Stereo)":
            config.channels = 2

        # Chapter metadata - use edited metadata if available
        if self.current_metadata:
            # Save current metadata to a temporary file
            import tempfile
            temp_dir = tempfile.mkdtemp()
            temp_chapter_file = os.path.join(temp_dir, "edited_chapters.txt")

            try:
                # Export edited metadata to ffmetadata format
                chapter_parser.export_ffmetadata(self.current_metadata, temp_chapter_file)
                config.chapter_file = temp_chapter_file
                config.chapter_format = 'ffmetadata'

                # Store temp directory for cleanup
                config._temp_chapter_dir = temp_dir
            except Exception as e:
                print(f"Warning: Could not save edited chapters: {e}")
                # Fall back to original chapter file
                if self.chapter_file_edit.text():
                    config.chapter_file = self.chapter_file_edit.text()
        elif self.chapter_file_edit.text():
            config.chapter_file = self.chapter_file_edit.text()

        # Book metadata - use edited values
        config.title = self.title_edit.text().strip() or None
        config.author = self.author_edit.text().strip() or None
        config.year = self.year_spin.value() or None
        config.genre = self.genre_edit.text().strip() or None
        config.comment = self.comment_edit.text().strip() or None

        # Cover image
        config.cover_file = self.cover_edit.text() if not self.no_cover_check.isChecked() else None
        config.no_cover = self.no_cover_check.isChecked()

        # Processing
        workers_value = self.workers_spin.value()
        if workers_value == 0:
            config.workers = None
        else:
            config.workers = workers_value

        config.no_optimize = not self.optimize_check.isChecked()
        config.keep_temp = self.keep_temp_check.isChecked()
        config.force_reencode = self.force_reencode_check.isChecked()

        config.temp_dir = self.temp_edit.text() or None
        config.max_retries = self.retry_spin.value()

        # FFmpeg paths
        config.ffmpeg_path = self.ffmpeg_edit.text() or None
        config.ffprobe_path = self.ffprobe_edit.text() or None

        # Verbosity
        if self.verbosity_debug.isChecked():
            config.verbosity = Verbosity.DEBUG
        elif self.verbosity_verbose.isChecked():
            config.verbosity = Verbosity.VERBOSE
        else:
            config.verbosity = Verbosity.NORMAL

        # Batch processing
        config.batch = self.batch_check.isChecked()
        config.recursive = self.recursive_check.isChecked()
        config.pattern = self.pattern_edit.text()
        config.exclude = self.exclude_edit.text() or None

        return config

    def validate_inputs(self):
        """Validate user inputs before conversion"""
        # Check source directory
        source_dir = self.source_edit.text()
        if not source_dir:
            QMessageBox.warning(self, "Warning", "Please select a source directory")
            return False

        if not Path(source_dir).exists():
            QMessageBox.warning(self, "Warning", f"Source directory does not exist:\n{source_dir}")
            return False

        # Check for MP3 files
        pattern = self.pattern_edit.text()
        mp3_files = list(Path(source_dir).glob(pattern))
        if not mp3_files:
            QMessageBox.warning(self, "Warning",
                              f"No {pattern} files found in:\n{source_dir}")
            return False

        # Check output directory
        output_dir = self.dest_edit.text()
        if not output_dir:
            QMessageBox.warning(self, "Warning", "Please select an output directory")
            return False

        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        except:
            QMessageBox.warning(self, "Warning", f"Cannot create output directory:\n{output_dir}")
            return False

        # Check chapter file if specified (not required for conversion)
        chapter_file = self.chapter_file_edit.text()
        if chapter_file and not Path(chapter_file).exists():
            QMessageBox.warning(self, "Warning", f"Chapter file does not exist:\n{chapter_file}")
            return False

        return True

    def update_progress(self, msg_type, message):
        """Update progress display"""
        if msg_type == 'step_start':
            self.log_output.append(f"▶ {message}...")
        elif msg_type == 'step_end':
            success, extra = message.split(':', 1) if ':' in message else (message, '')
            icon = "✓" if success == "True" else "✗"
            self.log_output.append(f"  {icon} {extra}" if extra else f"  {icon}")
        elif msg_type == 'info':
            self.log_output.append(f"ℹ {message}")
        elif msg_type == 'header':
            self.log_output.append(f"\n════ {message} ════")
        elif msg_type == 'success':
            self.log_output.append(f"✓ {message}")
        elif msg_type == 'warning':
            self.log_output.append(f"⚠ {message}")
        elif msg_type == 'error':
            self.log_output.append(f"✗ ERROR: {message}")
        elif msg_type == 'debug':
            self.log_output.append(f"🔧 {message}")
        elif msg_type == 'ffmpeg_output':
            self.log_output.append(f"  {message}")
        elif msg_type == 'progress':
            if ':' in message:
                progress_info, progress_msg = message.split(':', 1)
                if '/' in progress_info:
                    current, total = progress_info.split('/')
                    try:
                        current_int = int(current)
                        total_int = int(total)
                        self.progress_bar.setMaximum(total_int)
                        self.progress_bar.setValue(current_int)
                        percent = (current_int / total_int) * 100 if total_int > 0 else 0
                        if progress_msg:
                            self.status_bar.showMessage(f"Processing: {progress_msg} ({percent:.1f}%)")
                        else:
                            self.status_bar.showMessage(f"Processing: {percent:.1f}% complete")
                    except ValueError:
                        if progress_msg:
                            self.status_bar.showMessage(f"Processing: {progress_msg}")

        # Auto-scroll to bottom
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def update_stats(self, stats):
        """Update statistics display"""
        pass

    def update_timer(self):
        """Update elapsed time display"""
        if hasattr(self, 'start_time'):
            elapsed = time.time() - self.start_time
            self.time_label.setText(f"Time: {timedelta(seconds=int(elapsed))}")

    def conversion_finished(self, success, output_file):
        """Handle conversion completion"""
        if hasattr(self, 'timer'):
            self.timer.stop()

        self.set_conversion_controls(True)

        if success:
            self.output_file = output_file
            self.open_folder_btn.setEnabled(True)
            self.status_bar.showMessage(f"Conversion successful! Output: {output_file}")
            QMessageBox.information(self, "Success",
                                  f"Conversion completed successfully!\n\n"
                                  f"Output file: {output_file}")
        else:
            self.status_bar.showMessage("Conversion failed")
            QMessageBox.warning(self, "Error", "Conversion failed. Check the log for details.")

    def set_conversion_controls(self, enabled):
        """Enable/disable controls during conversion"""
        self.convert_btn.setEnabled(enabled)
        self.pause_btn.setEnabled(not enabled)
        self.cancel_btn.setEnabled(not enabled)

        for i in range(self.tab_widget.count()):
            self.tab_widget.setTabEnabled(i, enabled)

    def pause_conversion(self):
        """Pause/resume conversion"""
        QMessageBox.information(self, "Info", "Pause functionality not yet implemented")

    def cancel_conversion(self):
        """Cancel ongoing conversion"""
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(self, "Cancel Conversion",
                                       "Are you sure you want to cancel the conversion?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.worker_thread.terminate()
                self.worker_thread.wait()
                self.status_bar.showMessage("Conversion cancelled")
                self.set_conversion_controls(True)

    def open_output_folder(self):
        """Open the output folder in file explorer"""
        if self.output_file and Path(self.output_file).exists():
            if sys.platform == 'win32':
                os.startfile(Path(self.output_file).parent)
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(Path(self.output_file).parent)])
            else:
                subprocess.run(['xdg-open', str(Path(self.output_file).parent)])

    def clear_log(self):
        """Clear the log output"""
        self.log_output.clear()

    def closeEvent(self, event):
        """Handle window close event"""
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(self, "Conversion in Progress",
                                       "A conversion is in progress. Are you sure you want to quit?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.worker_thread.terminate()
                self.worker_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
