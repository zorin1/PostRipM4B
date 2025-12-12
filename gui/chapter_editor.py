# gui/chapter_editor.py (simplified version)
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QLineEdit, QPushButton, QSpinBox,
                             QTextEdit, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog,
                             QAbstractItemView, QComboBox, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from datetime import timedelta
import os
from pathlib import Path
import chapter_parser


class ChapterEditorDialog(QDialog):
    """Dialog for editing chapters and metadata"""

    chapters_updated = pyqtSignal(object)  # Emits updated Metadata object

    def __init__(self, metadata: chapter_parser.Metadata,
                 audio_duration: float, parent=None):
        super().__init__(parent)
        self.metadata = metadata.copy()  # Work with a copy
        self.audio_duration = audio_duration
        self.original_metadata = metadata  # Keep original for comparison
        self.modified = False

        self.init_ui()
        self.update_chapters_table()
        self.update_validation_status()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Chapter Editor")
        self.setGeometry(100, 100, 900, 700)

        # Main layout
        layout = QVBoxLayout(self)

        # Metadata section
        metadata_group = QGroupBox("📚 Book Metadata")
        metadata_layout = QVBoxLayout()

        # Title
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Title:"))
        self.title_edit = QLineEdit(self.metadata.title or "")
        self.title_edit.textChanged.connect(self.on_metadata_changed)
        title_layout.addWidget(self.title_edit)
        metadata_layout.addLayout(title_layout)

        # Author
        author_layout = QHBoxLayout()
        author_layout.addWidget(QLabel("Author:"))
        self.author_edit = QLineEdit(self.metadata.author or "")
        self.author_edit.textChanged.connect(self.on_metadata_changed)
        author_layout.addWidget(self.author_edit)
        metadata_layout.addLayout(author_layout)

        # Year and Genre
        year_genre_layout = QHBoxLayout()

        # Year
        year_genre_layout.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1000, 2100)
        self.year_spin.setValue(self.metadata.year or 2024)
        self.year_spin.valueChanged.connect(self.on_metadata_changed)
        year_genre_layout.addWidget(self.year_spin)

        year_genre_layout.addWidget(QLabel("Genre:"))
        self.genre_edit = QLineEdit(self.metadata.genre or "Audiobook")
        self.genre_edit.textChanged.connect(self.on_metadata_changed)
        year_genre_layout.addWidget(self.genre_edit)

        year_genre_layout.addStretch()
        metadata_layout.addLayout(year_genre_layout)

        # Comment
        comment_layout = QVBoxLayout()
        comment_layout.addWidget(QLabel("Comment:"))
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(60)
        self.comment_edit.setText(self.metadata.comment or "")
        self.comment_edit.textChanged.connect(self.on_metadata_changed)
        comment_layout.addWidget(self.comment_edit)
        metadata_layout.addLayout(comment_layout)

        metadata_group.setLayout(metadata_layout)
        layout.addWidget(metadata_group)

        # Chapters section
        chapters_group = QGroupBox(f"📖 Chapters ({len(self.metadata.chapters)} chapters)")
        chapters_layout = QVBoxLayout()

        # Chapters table
        self.chapters_table = QTableWidget()
        self.chapters_table.setColumnCount(5)
        self.chapters_table.setHorizontalHeaderLabels([
            "#", "Start Time", "End Time", "Duration", "Title"
        ])
        self.chapters_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.chapters_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.chapters_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.chapters_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)

        chapters_layout.addWidget(self.chapters_table)

        # Chapter controls
        controls_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Add Chapter")
        self.add_btn.clicked.connect(self.add_chapter)

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_chapter)

        self.move_up_btn = QPushButton("🔼 Move Up")
        self.move_up_btn.clicked.connect(lambda: self.move_chapter('up'))

        self.move_down_btn = QPushButton("🔽 Move Down")
        self.move_down_btn.clicked.connect(lambda: self.move_chapter('down'))

        controls_layout.addWidget(self.add_btn)
        controls_layout.addWidget(self.delete_btn)
        controls_layout.addWidget(self.move_up_btn)
        controls_layout.addWidget(self.move_down_btn)
        controls_layout.addStretch()

        chapters_layout.addLayout(controls_layout)
        chapters_group.setLayout(chapters_layout)
        layout.addWidget(chapters_group)

        # Info and validation section
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout()

        # Audio duration
        duration_str = self.format_time(self.audio_duration)
        self.duration_label = QLabel(f"Total audio duration: {duration_str}")
        info_layout.addWidget(self.duration_label)

        # Validation status
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.validation_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Dialog buttons
        buttons_layout = QHBoxLayout()

        self.use_btn = QPushButton("✅ Use These Chapters")
        self.use_btn.clicked.connect(self.accept)
        self.use_btn.setStyleSheet("font-weight: bold; padding: 5px;")

        self.save_btn = QPushButton("💾 Save to File...")
        self.save_btn.clicked.connect(self.save_to_file)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        buttons_layout.addWidget(self.use_btn)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

        # Connect table signals
        self.chapters_table.itemChanged.connect(self.on_table_item_changed)
        self.chapters_table.itemSelectionChanged.connect(self.update_button_states)

        # Initial button state update
        self.update_button_states()

    def format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS.sss"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_remainder = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds_remainder:06.3f}"

    def parse_time(self, time_str: str) -> float:
        """Parse HH:MM:SS.sss format to seconds"""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            pass
        return 0.0

    def update_chapters_table(self):
        """Update the chapters table with current metadata"""
        self.chapters_table.blockSignals(True)
        self.chapters_table.setRowCount(len(self.metadata.chapters))

        for i, chapter in enumerate(self.metadata.chapters):
            # Chapter number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
            self.chapters_table.setItem(i, 0, num_item)

            # Start time
            start_time = chapter.total_offset.total_seconds()
            start_item = QTableWidgetItem(self.format_time(start_time))
            self.chapters_table.setItem(i, 1, start_item)

            # End time
            end_time = self.metadata.get_chapter_end_time(i, self.audio_duration)
            end_item = QTableWidgetItem(self.format_time(end_time))
            end_item.setFlags(end_item.flags() & ~Qt.ItemIsEditable)
            self.chapters_table.setItem(i, 2, end_item)

            # Duration
            duration = self.metadata.get_chapter_duration(i, self.audio_duration)
            duration_item = QTableWidgetItem(self.format_time(duration))
            duration_item.setFlags(duration_item.flags() & ~Qt.ItemIsEditable)
            self.chapters_table.setItem(i, 3, duration_item)

            # Title
            title_item = QTableWidgetItem(chapter.title)
            self.chapters_table.setItem(i, 4, title_item)

        self.chapters_table.blockSignals(False)

    def on_table_item_changed(self, item):
        """Handle changes in table items"""
        row = item.row()
        col = item.column()

        if col == 1:  # Start time changed
            try:
                # Parse HH:MM:SS.sss format
                time_str = item.text()
                total_seconds = self.parse_time(time_str)

                if total_seconds >= 0:
                    # Update chapter
                    self.metadata.update_chapter(row, start_time=total_seconds)
                    self.modified = True
                    self.update_chapters_table()
                    self.update_validation_status()
                else:
                    # Revert to original value
                    original_time = self.metadata.chapters[row].total_offset.total_seconds()
                    item.setText(self.format_time(original_time))
            except ValueError:
                # Revert to original value
                original_time = self.metadata.chapters[row].total_offset.total_seconds()
                item.setText(self.format_time(original_time))

        elif col == 4:  # Title changed
            new_title = item.text()
            if new_title.strip():
                self.metadata.update_chapter(row, title=new_title)
                self.modified = True
                self.update_validation_status()
            else:
                # Revert to original title
                original_title = self.metadata.chapters[row].title
                item.setText(original_title)

    def on_metadata_changed(self):
        """Handle metadata field changes"""
        self.modified = True
        self.update_validation_status()

    def add_chapter(self):
        """Add a new chapter"""
        # Get selected row or add at end
        selected_rows = self.chapters_table.selectedIndexes()
        insert_position = selected_rows[0].row() + 1 if selected_rows else len(self.metadata.chapters)

        # Calculate default start time (middle between surrounding chapters or end)
        if insert_position == 0:
            # First chapter
            start_time = 0
        elif insert_position >= len(self.metadata.chapters):
            # Last chapter - add near the end
            if self.metadata.chapters:
                last_time = self.metadata.chapters[-1].total_offset.total_seconds()
                start_time = min(last_time + 60, self.audio_duration - 60)
            else:
                start_time = 0
        else:
            # Between chapters
            prev_time = self.metadata.chapters[insert_position - 1].total_offset.total_seconds()
            next_time = self.metadata.chapters[insert_position].total_offset.total_seconds()
            start_time = (prev_time + next_time) / 2

        # Ensure start time is valid
        start_time = max(0, min(start_time, self.audio_duration - 1))

        # Add chapter
        success = self.metadata.add_chapter(
            title=f"Chapter {insert_position + 1}",
            start_time=start_time,
            position=insert_position
        )

        if success:
            self.modified = True
            self.update_chapters_table()
            self.update_validation_status()
            # Select the new chapter
            self.chapters_table.selectRow(insert_position)

    def delete_chapter(self):
        """Delete selected chapter"""
        selected_rows = self.chapters_table.selectedIndexes()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        if row < 0 or row >= len(self.metadata.chapters):
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete chapter '{self.metadata.chapters[row].title}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = self.metadata.delete_chapter(row)
            if success:
                self.modified = True
                self.update_chapters_table()
                self.update_validation_status()

    def move_chapter(self, direction: str):
        """Move selected chapter up or down"""
        selected_rows = self.chapters_table.selectedIndexes()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        success = self.metadata.move_chapter(row, direction)

        if success:
            self.modified = True
            self.update_chapters_table()
            self.update_validation_status()
            # Select the moved chapter
            new_row = row - 1 if direction == 'up' else row + 1
            self.chapters_table.selectRow(new_row)

    def update_button_states(self):
        """Update button enabled states based on selection"""
        selected_rows = self.chapters_table.selectedIndexes()
        has_selection = bool(selected_rows)

        self.delete_btn.setEnabled(has_selection)
        self.move_up_btn.setEnabled(has_selection and selected_rows[0].row() > 0)
        self.move_down_btn.setEnabled(has_selection and
                                     selected_rows[0].row() < len(self.metadata.chapters) - 1)

    def update_validation_status(self):
        """Update validation status display"""
        # Update metadata from fields
        self.metadata.title = self.title_edit.text().strip()
        self.metadata.author = self.author_edit.text().strip()
        self.metadata.year = self.year_spin.value()
        self.metadata.genre = self.genre_edit.text().strip()
        self.metadata.comment = self.comment_edit.toPlainText().strip()

        # Validate
        errors = self.metadata.validate(self.audio_duration)

        if errors:
            self.validation_label.setText("❌ Issues found (hover for details)")
            self.validation_label.setStyleSheet("color: red; font-weight: bold;")
            # Show first error as tooltip
            self.validation_label.setToolTip("\n".join(errors))
            self.use_btn.setEnabled(False)
        else:
            self.validation_label.setText("✅ All chapters valid")
            self.validation_label.setStyleSheet("color: green; font-weight: bold;")
            self.validation_label.setToolTip("")
            self.use_btn.setEnabled(True)

        # Update chapters count in group title
        chapters_group = self.findChild(QGroupBox, "")
        if chapters_group:
            chapters_group.setTitle(f"📖 Chapters ({len(self.metadata.chapters)} chapters)")

    def save_to_file(self):
        """Save edited chapters to a file"""
        if not self.modified:
            QMessageBox.information(self, "No Changes", "No changes to save.")
            return

        # Get format from user
        format_dialog = QDialog(self)
        format_dialog.setWindowTitle("Save Format")
        format_dialog.setModal(True)

        layout = QVBoxLayout(format_dialog)
        layout.addWidget(QLabel("Select export format:"))

        format_combo = QComboBox()
        format_combo.addItems([
            "FFmetadata (metadata.txt)",
            "m4b-tool (chapters.txt)",
            "Audacity Labels"
        ])
        layout.addWidget(format_combo)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        format_map = {
            "FFmetadata (metadata.txt)": 'ffmetadata',
            "m4b-tool (chapters.txt)": 'm4btool',
            "Audacity Labels": 'audacity'
        }

        def on_ok():
            format_dialog.accept()

        def on_cancel():
            format_dialog.reject()

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(on_cancel)

        if format_dialog.exec_() != QDialog.Accepted:
            return

        selected_format = format_map.get(format_combo.currentText(), 'ffmetadata')

        # Get save location
        file_filter = {
            'ffmetadata': "FFmetadata files (*.txt);;All files (*.*)",
            'm4btool': "m4b-tool chapters (*.txt);;All files (*.*)",
            'audacity': "Audacity label files (*.txt);;All files (*.*)"
        }.get(selected_format, "All files (*.*)")

        default_name = f"{self.metadata.title.replace(' ', '_')}_chapters.txt"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Chapters",
            default_name,
            file_filter
        )

        if filename:
            try:
                chapter_parser.export_chapters(self.metadata, filename, selected_format)
                QMessageBox.information(self, "Saved", f"Chapters saved to:\n{filename}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save chapters:\n{str(e)}")

    def accept(self):
        """Accept the dialog and emit updated metadata"""
        # Final validation
        errors = self.metadata.validate(self.audio_duration)
        if errors:
            QMessageBox.warning(self, "Validation Error",
                              "Please fix the following issues:\n\n" + "\n".join(errors))
            return

        # Emit updated metadata
        self.chapters_updated.emit(self.metadata)
        super().accept()

    def reject(self):
        """Reject the dialog"""
        if self.modified:
            reply = QMessageBox.question(
                self, "Discard Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        super().reject()
