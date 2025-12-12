#!/usr/bin/env python3
"""
chapter_parser.py - Module for parsing various chapter formats

Supported formats:
1. Libby (metadata.json) - JSON format from LibbyRip
2. ffmetadata - FFmpeg metadata format (metadata.txt)
3. m4btool - chapters.txt format used by m4b-tool and tone
4. audacity - Audacity label format

All parsing functions return a standardized Metadata object.
"""

import os
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import timedelta
from typing import List, Optional, Tuple, Dict, Any
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# -----------------------------
# Data Classes
# -----------------------------

@dataclass
class Chapter:
    title: str
    total_offset: timedelta

    def to_dict(self) -> Dict[str, Any]:
        """Convert chapter to dictionary for serialization"""
        return {
            'title': self.title,
            'total_offset': self.total_offset.total_seconds()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chapter':
        """Create chapter from dictionary"""
        return cls(
            title=data['title'],
            total_offset=timedelta(seconds=data['total_offset'])
        )

@dataclass
class Metadata:
    title: str
    author: Optional[str]
    narrator: Optional[str]
    total_duration: timedelta
    chapters: List[Chapter]

    # Additional fields that might be useful
    year: Optional[int] = None
    genre: Optional[str] = None
    comment: Optional[str] = None

    def __post_init__(self):
        """Ensure chapters are sorted by time"""
        self.chapters.sort(key=lambda c: c.total_offset)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for serialization"""
        return {
            'title': self.title,
            'author': self.author,
            'narrator': self.narrator,
            'total_duration': self.total_duration.total_seconds(),
            'chapters': [chapter.to_dict() for chapter in self.chapters],
            'year': self.year,
            'genre': self.genre,
            'comment': self.comment
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Metadata':
        """Create metadata from dictionary"""
        return cls(
            title=data['title'],
            author=data.get('author'),
            narrator=data.get('narrator'),
            total_duration=timedelta(seconds=data['total_duration']),
            chapters=[Chapter.from_dict(ch) for ch in data['chapters']],
            year=data.get('year'),
            genre=data.get('genre'),
            comment=data.get('comment')
        )

    def copy(self) -> 'Metadata':
        """Create a deep copy of the metadata"""
        return Metadata.from_dict(self.to_dict())

    def validate(self, audio_duration: Optional[float] = None) -> List[str]:
        """
        Validate metadata and return list of errors.

        Args:
            audio_duration: Total audio duration in seconds (optional)

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if not self.title or not self.title.strip():
            errors.append("Title is required")

        if not self.author or not self.author.strip():
            errors.append("Author is required")

        # Validate chapters
        if self.chapters:
            # Check chapter titles
            for i, chapter in enumerate(self.chapters):
                if not chapter.title or not chapter.title.strip():
                    errors.append(f"Chapter {i+1}: Title is required")

            # Check start times are in order
            for i in range(len(self.chapters) - 1):
                if self.chapters[i].total_offset >= self.chapters[i + 1].total_offset:
                    errors.append(f"Chapters {i+1} and {i+2}: Start times must be in increasing order")

            # Check against audio duration if provided
            if audio_duration is not None:
                last_chapter_end = self.get_chapter_end_time(len(self.chapters) - 1, audio_duration)
                if last_chapter_end > audio_duration:
                    errors.append(f"Last chapter ends at {timedelta(seconds=last_chapter_end)}, "
                                 f"but audio duration is only {timedelta(seconds=audio_duration)}")

        return errors

    def get_chapter_end_time(self, chapter_index: int, audio_duration: float) -> float:
        """
        Get end time for a chapter.

        Args:
            chapter_index: Index of the chapter
            audio_duration: Total audio duration in seconds

        Returns:
            End time in seconds
        """
        if chapter_index < len(self.chapters) - 1:
            # End time is next chapter's start time
            return self.chapters[chapter_index + 1].total_offset.total_seconds()
        else:
            # Last chapter ends at audio duration
            return audio_duration

    def get_chapter_duration(self, chapter_index: int, audio_duration: float) -> float:
        """
        Get duration for a chapter.

        Args:
            chapter_index: Index of the chapter
            audio_duration: Total audio duration in seconds

        Returns:
            Duration in seconds
        """
        start_time = self.chapters[chapter_index].total_offset.total_seconds()
        end_time = self.get_chapter_end_time(chapter_index, audio_duration)
        return end_time - start_time

    def add_chapter(self, title: str, start_time: float, position: Optional[int] = None) -> bool:
        """
        Add a new chapter.

        Args:
            title: Chapter title
            start_time: Start time in seconds
            position: Position to insert (None for append)

        Returns:
            True if successful
        """
        new_chapter = Chapter(title=title, total_offset=timedelta(seconds=start_time))

        if position is None:
            self.chapters.append(new_chapter)
        else:
            if position < 0 or position > len(self.chapters):
                return False
            self.chapters.insert(position, new_chapter)

        # Re-sort chapters
        self.chapters.sort(key=lambda c: c.total_offset)
        return True

    def delete_chapter(self, chapter_index: int) -> bool:
        """
        Delete a chapter.

        Args:
            chapter_index: Index of chapter to delete

        Returns:
            True if successful
        """
        if chapter_index < 0 or chapter_index >= len(self.chapters):
            return False

        del self.chapters[chapter_index]
        return True

    def move_chapter(self, chapter_index: int, direction: str) -> bool:
        """
        Move a chapter up or down in the list.
        Note: This only changes display order, not timing.

        Args:
            chapter_index: Index of chapter to move
            direction: 'up' or 'down'

        Returns:
            True if successful
        """
        if direction == 'up':
            if chapter_index <= 0:
                return False
            # Swap with previous chapter
            self.chapters[chapter_index], self.chapters[chapter_index - 1] = \
                self.chapters[chapter_index - 1], self.chapters[chapter_index]
            return True
        elif direction == 'down':
            if chapter_index >= len(self.chapters) - 1:
                return False
            # Swap with next chapter
            self.chapters[chapter_index], self.chapters[chapter_index + 1] = \
                self.chapters[chapter_index + 1], self.chapters[chapter_index]
            return True
        return False

    def update_chapter(self, chapter_index: int, title: Optional[str] = None,
                       start_time: Optional[float] = None) -> bool:
        """
        Update chapter properties.

        Args:
            chapter_index: Index of chapter to update
            title: New title (None to keep current)
            start_time: New start time in seconds (None to keep current)

        Returns:
            True if successful
        """
        if chapter_index < 0 or chapter_index >= len(self.chapters):
            return False

        chapter = self.chapters[chapter_index]
        if title is not None:
            chapter.title = title
        if start_time is not None:
            chapter.total_offset = timedelta(seconds=start_time)

        # Re-sort chapters if start time changed
        if start_time is not None:
            self.chapters.sort(key=lambda c: c.total_offset)

        return True

# -----------------------------
# Parser Functions (Existing - unchanged)
# -----------------------------

def parse_libby_chapters(file_path: str) -> Metadata:
    """
    Parse Libby metadata.json format.

    Format: JSON with spines and chapters
    Example structure:
    {
        "title": "Book Title",
        "creator": [
            {"role": "author", "name": "Author Name"},
            {"role": "narrator", "name": "Narrator Name"}
        ],
        "spine": [
            {"duration": 3600.5, "title": "Part 1"},
            ...
        ],
        "chapters": [
            {"title": "Chapter 1", "offset": 0, "spine": 0},
            ...
        ]
    }
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract spines and chapters
    spines = data.get("spine", [])
    chapters_raw = data.get("chapters", [])

    # Calculate spine offsets
    spine_offsets = [sum(spine.get("duration", 0) for spine in spines[:i])
                    for i in range(len(spines))]

    # Parse chapters
    chapters = []
    for ch in chapters_raw:
        spine_idx = ch.get("spine", 0)
        offset_seconds = ch.get("offset", 0)
        total_seconds = offset_seconds + spine_offsets[spine_idx]

        chapters.append(Chapter(
            title=ch.get("title", "").strip(),
            total_offset=timedelta(seconds=total_seconds)
        ))

    # Extract contributors
    contributors = {}
    for c in data.get("creator", []):
        role = c.get("role", "").lower()
        name = c.get("name", "").strip()
        if role and name:
            contributors[role] = name

    # Calculate total duration
    total_duration = timedelta(seconds=sum(spine.get("duration", 0) for spine in spines))

    return Metadata(
        title=data.get("title", "").strip(),
        author=contributors.get("author"),
        narrator=contributors.get("narrator"),
        total_duration=total_duration,
        chapters=chapters,
        year=data.get("year"),
        genre=data.get("genre"),
        comment=data.get("comment")
    )

def parse_ffmetadata_chapters(file_path: str) -> Metadata:
    """
    Parse FFmpeg metadata format.

    Format:
    ;FFMETADATA1
    title=Book Title
    artist=Author Name
    [CHAPTER]
    TIMEBASE=1/1000
    START=0
    END=300000
    title=Chapter 1
    [CHAPTER]
    ...
    """
    chapters = []
    metadata = {
        'title': '',
        'author': None,
        'narrator': None,
        'total_duration': timedelta(seconds=0)
    }

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip comments and empty lines
        if not line or line.startswith(';'):
            i += 1
            continue

        # Parse metadata lines
        if '=' in line and not line.startswith('['):
            key, value = line.split('=', 1)
            key = key.strip().lower()
            value = value.strip()

            if key == 'title':
                metadata['title'] = value
            elif key == 'artist':
                metadata['author'] = value
            elif key == 'comment' and 'narrator' in value.lower():
                # Try to extract narrator from comment
                metadata['narrator'] = value

        # Parse chapter sections
        elif line.startswith('[CHAPTER]'):
            chapter_data = {}
            i += 1

            while i < len(lines) and not lines[i].strip().startswith('['):
                sub_line = lines[i].strip()
                if '=' in sub_line:
                    key, value = sub_line.split('=', 1)
                    chapter_data[key.strip().lower()] = value.strip()
                i += 1

            # Create chapter if we have the required data
            if 'start' in chapter_data and 'title' in chapter_data:
                try:
                    # Convert milliseconds to seconds
                    start_ms = int(chapter_data['start'])
                    start_seconds = start_ms / 1000.0

                    chapters.append(Chapter(
                        title=chapter_data['title'],
                        total_offset=timedelta(seconds=start_seconds)
                    ))

                    # Update total duration from last chapter's END
                    if 'end' in chapter_data:
                        end_ms = int(chapter_data['end'])
                        end_seconds = end_ms / 1000.0
                        if end_seconds > metadata['total_duration'].total_seconds():
                            metadata['total_duration'] = timedelta(seconds=end_seconds)
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse chapter data: {chapter_data}")

            continue  # Don't increment i again since we already did

        i += 1

    # Sort chapters by start time
    chapters.sort(key=lambda c: c.total_offset)

    return Metadata(
        title=metadata['title'] or os.path.basename(file_path).rsplit('.', 1)[0],
        author=metadata['author'],
        narrator=metadata['narrator'],
        total_duration=metadata['total_duration'],
        chapters=chapters
    )

def parse_m4btool_chapters(file_path: str) -> Metadata:
    """
    Parse m4b-tool/tone chapters.txt format.

    Format: One chapter per line
    HH:MM:SS.sss Chapter Title
    or with tabs: HH:MM:SS.sss\tChapter Title

    Example:
    00:00:00.000 Chapter 1
    00:05:30.500 Chapter 2
    01:23:45.000 Chapter 3
    """
    chapters = []
    max_duration = 0.0

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Split by whitespace (space or tab)
            # First part is timestamp, rest is title
            parts = line.split(None, 1)
            if len(parts) < 2:
                logger.warning(f"Line {line_num}: Invalid format, skipping: {line}")
                continue

            timestamp_str, title = parts

            # Parse timestamp (HH:MM:SS.sss or HH:MM:SS)
            try:
                if '.' in timestamp_str:
                    hours, mins, secs_ms = timestamp_str.split(':')
                    seconds, milliseconds = secs_ms.split('.')
                    total_seconds = (
                        int(hours) * 3600 +
                        int(mins) * 60 +
                        int(seconds) +
                        int(milliseconds.ljust(3, '0')[:3]) / 1000.0
                    )
                else:
                    hours, mins, seconds = timestamp_str.split(':')
                    total_seconds = (
                        int(hours) * 3600 +
                        int(mins) * 60 +
                        int(seconds)
                    )

                chapters.append(Chapter(
                    title=title.strip(),
                    total_offset=timedelta(seconds=total_seconds)
                ))

                # Track max duration for total duration estimate
                if total_seconds > max_duration:
                    max_duration = total_seconds

            except (ValueError, TypeError) as e:
                logger.warning(f"Line {line_num}: Failed to parse timestamp '{timestamp_str}': {e}")
                continue

    # Sort by timestamp
    chapters.sort(key=lambda c: c.total_offset)

    # Use filename as title
    title = os.path.basename(file_path).rsplit('.', 1)[0]

    return Metadata(
        title=title,
        author=None,
        narrator=None,
        total_duration=timedelta(seconds=max_duration),
        chapters=chapters
    )

def parse_audacity_chapters(file_path: str) -> Metadata:
    """
    Parse Audacity label format.

    Format: Tab-separated values
    StartTime\tEndTime\tTitle
    or space-separated

    Example:
    0.000000	300.500000	Chapter 1
    300.500000	600.750000	Chapter 2
    """
    chapters = []
    max_duration = 0.0

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Split by whitespace (tab or space)
            parts = line.split()
            if len(parts) < 3:
                logger.warning(f"Line {line_num}: Invalid format, skipping: {line}")
                continue

            try:
                start_time_str = parts[0]
                # end_time_str = parts[1]  # Not used for chapter start
                title = ' '.join(parts[2:])  # Rest is title

                # Parse start time (seconds with decimal)
                start_seconds = float(start_time_str)

                chapters.append(Chapter(
                    title=title.strip(),
                    total_offset=timedelta(seconds=start_seconds)
                ))

                # Track max duration for total duration estimate
                if start_seconds > max_duration:
                    max_duration = start_seconds

                # Also check end time for total duration
                if len(parts) > 1:
                    try:
                        end_seconds = float(parts[1])
                        if end_seconds > max_duration:
                            max_duration = end_seconds
                    except ValueError:
                        pass

            except (ValueError, TypeError) as e:
                logger.warning(f"Line {line_num}: Failed to parse line: {e}")
                continue

    # Sort by start time
    chapters.sort(key=lambda c: c.total_offset)

    # Use filename as title
    title = os.path.basename(file_path).rsplit('.', 1)[0]

    return Metadata(
        title=title,
        author=None,
        narrator=None,
        total_duration=timedelta(seconds=max_duration),
        chapters=chapters
    )

def detect_chapter_format(file_path: str) -> Optional[str]:
    """
    Try to detect the format of a chapter file.
    Note: This is not 100% reliable but can provide a guess.
    """
    if not os.path.exists(file_path):
        return None

    ext = os.path.splitext(file_path)[1].lower()

    # Check by extension first
    if ext == '.json':
        return 'libby'
    elif ext == '.txt':
        # Need to examine content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()

                if first_line.startswith(';FFMETADATA'):
                    return 'ffmetadata'
                # Check for timestamp format (HH:MM:SS)
                elif re.match(r'^\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\s', first_line):
                    return 'm4btool'
                # Check for decimal timestamp format
                elif re.match(r'^\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s', first_line):
                    return 'audacity'
        except:
            pass

    return None

def load_chapters(file_path: str, format: Optional[str] = None) -> Metadata:
    """
    Main function to load chapters from any supported format.

    Args:
        file_path: Path to chapter file
        format: One of 'libby', 'ffmetadata', 'm4btool', 'audacity'
                If None, will try to auto-detect

    Returns:
        Metadata object with chapters
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Chapter file not found: {file_path}")

    # Auto-detect format if not specified
    if format is None:
        format = detect_chapter_format(file_path)
        if format is None:
            raise ValueError(f"Could not detect chapter format for: {file_path}")

    # Dispatch to appropriate parser
    if format == 'libby':
        return parse_libby_chapters(file_path)
    elif format == 'ffmetadata':
        return parse_ffmetadata_chapters(file_path)
    elif format == 'm4btool':
        return parse_m4btool_chapters(file_path)
    elif format == 'audacity':
        return parse_audacity_chapters(file_path)
    else:
        raise ValueError(f"Unsupported chapter format: {format}")

def export_chapters(metadata: Metadata, output_path: str, format: str = 'ffmetadata'):
    """
    Export chapters to a specific format.

    Args:
        metadata: Metadata object with chapters
        output_path: Where to save the exported file
        format: One of 'ffmetadata', 'm4btool', 'audacity'
    """
    if format == 'ffmetadata':
        export_ffmetadata(metadata, output_path)
    elif format == 'm4btool':
        export_m4btool(metadata, output_path)
    elif format == 'audacity':
        export_audacity(metadata, output_path)
    else:
        raise ValueError(f"Unsupported export format: {format}")

def export_ffmetadata(metadata: Metadata, output_path: str):
    """Export to FFmpeg metadata format."""
    lines = [";FFMETADATA1"]

    if metadata.title:
        lines.append(f"title={metadata.title}")
    if metadata.author:
        lines.append(f"artist={metadata.author}")
    if metadata.year:
        lines.append(f"date={metadata.year}")
    if metadata.genre:
        lines.append(f"genre={metadata.genre}")
    if metadata.comment:
        lines.append(f"comment={metadata.comment}")

    lines.append("")

    # Add chapters
    for i, chapter in enumerate(metadata.chapters):
        start_ms = int(chapter.total_offset.total_seconds() * 1000)

        # Calculate end time (next chapter start or total duration)
        if i < len(metadata.chapters) - 1:
            end_ms = int(metadata.chapters[i + 1].total_offset.total_seconds() * 1000)
        else:
            end_ms = int(metadata.total_duration.total_seconds() * 1000)

        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={start_ms}")
        lines.append(f"END={end_ms}")
        lines.append(f"title={chapter.title}")
        lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def export_m4btool(metadata: Metadata, output_path: str):
    """Export to m4b-tool chapters.txt format."""
    lines = []

    for chapter in metadata.chapters:
        total_seconds = chapter.total_offset.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60

        # Format as HH:MM:SS.sss
        timestamp = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
        lines.append(f"{timestamp} {chapter.title}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def export_audacity(metadata: Metadata, output_path: str):
    """Export to Audacity label format."""
    lines = []

    for i, chapter in enumerate(metadata.chapters):
        start_seconds = chapter.total_offset.total_seconds()

        # Calculate end time (next chapter start or total duration)
        if i < len(metadata.chapters) - 1:
            end_seconds = metadata.chapters[i + 1].total_offset.total_seconds()
        else:
            end_seconds = metadata.total_duration.total_seconds()

        lines.append(f"{start_seconds:.6f}\t{end_seconds:.6f}\t{chapter.title}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
