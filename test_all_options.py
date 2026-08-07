#!/usr/bin/env python3
"""
Comprehensive test suite for PostRipM4b.py
Tests most command-line options in a single run with proper validation
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path
import shutil

# CONFIGURATION - Path to the converter script
SCRIPT_DIR = Path(__file__).parent
CONVERTER_SCRIPT = SCRIPT_DIR / "PostRipM4B.sh"

# Size expectations for a 10.5 hour (37,875 second) audiobook:
# Formula: bitrate_kbps × seconds / 8 / 1024 = size_MB
BASE_SIZE_64K = 303  # MB for 64k AAC
BASE_SIZE_128K = 606  # MB for 128k AAC
BASE_SIZE_192K = 850  # MB for 192k AAC

# Expected chapter count from your metadata
EXPECTED_CHAPTERS = 4  # Update this based on your metadata.json

# Batch-mode test data: a parent folder whose immediate subfolders are each a
# separate LibbyRip audiobook (each with its own MP3s + metadata).
# These live under ~/Music. If they are missing the batch tests are skipped.
BATCH_TEST_DIR = Path.home() / "Music" / "TestBatchBooks"
BATCH_BOOKS = [
    {
        "title": "Real Tigers",
        "author": "Mick Herron",
        "folder": "Mick Herron - Real Tigers",
        "has_metadata": True,
        "chapters": 4,
    },
    {
        "title": "Standing by the Wall",
        "author": "Mick Herron",
        "folder": "Mick Herron - Standing by the Wall",
        "has_metadata": True,
        "chapters": 6,
    },
    {
        # No metadata/metadata.json inside this folder: the converter must fall
        # back to the directory name for Title/Album/Sort Name (+ Track=1/Media=2).
        "title": "No Metadata Book",
        "author": None,
        "folder": "No Metadata Book",
        "has_metadata": False,
        "chapters": 0,
    },
]

def parse_test_output_from_args(test_name, cmd_args):
    """
    Parse cmd_args to find:
    - Output directory from -o flag (default: ./m4b)
    - Output name from -n flag (default: test_name)
    Returns output path in format: {output_dir}/{output_name}.m4b
    """
    # Default values
    output_dir = Path("./m4b")
    output_name = test_name  # Default to test_name if -n not found

    # Parse command arguments
    i = 0
    while i < len(cmd_args):
        arg = cmd_args[i]

        if arg == "-o" and i + 1 < len(cmd_args):
            # Handle -o for output directory
            output_path = Path(cmd_args[i + 1])

            # If it's a file path (has extension), get parent directory
            if output_path.suffix:  # Has an extension like .m4b
                output_dir = output_path.parent or Path(".")
            else:
                # It's a directory path
                output_dir = output_path
            i += 2  # Skip the value

        elif arg == "-n" and i + 1 < len(cmd_args):
            # Handle -n for output name
            output_name = cmd_args[i + 1]
            i += 2  # Skip the value

        else:
            i += 1  # Move to next argument

    # Build the output path
    test_output = output_dir / f"{output_name}.m4b"
    return test_output

def get_music_directory():
    """Prompt for music directory with better input handling"""
    while True:
        default_path = os.path.expanduser("~/Music")
        user_input = input(f"Enter music directory [default: {default_path}]: ").strip()

        # Handle empty input
        if not user_input:
            test_dir = default_path
        else:
            # Strip any quotes and expand user home directory
            test_dir = os.path.expanduser(user_input.strip("'\" "))
            # Handle dot (current directory)
            if test_dir == ".":
                test_dir = os.getcwd()

        # Check if directory exists
        if os.path.exists(test_dir):
            return test_dir
        else:
            print(f"❌ Directory not found: {test_dir}")
            print("Please enter a valid directory path.")
            # Offer to create it
            create = input(f"Create directory '{test_dir}'? (y/n): ").lower()
            if create == 'y':
                os.makedirs(test_dir, exist_ok=True)
                return test_dir
            # Otherwise, retry

def run_test(test_name, cmd_args, expected_size_range=None, expected_chapters=None, delete_previous_file=True):
    """Run a single test and return results with proper validation"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"CMD: {CONVERTER_SCRIPT} {' '.join(cmd_args)}")
    print('='*60)

    # Clean up previous test output
    test_output = f"./m4b/{test_name}.m4b"
    if os.path.exists(test_output) and delete_previous_file:
        os.remove(test_output)

    test_output = parse_test_output_from_args(test_name, cmd_args)

    # Clean up current test output
    if os.path.exists(test_output) and delete_previous_file:
        os.remove(test_output)

    # Ensure converter script is executable
    converter_path = Path(CONVERTER_SCRIPT)
    if not converter_path.exists():
        print(f"❌ ERROR: Converter script not found: {converter_path}")
        return {
            'name': test_name,
            'success': False,
            'file_exists': False,
            'elapsed': 0,
            'file_info': {},
            'size_ok': False,
            'chapters_ok': False,
            'chapter_count': 0,
            'cmd': f"{CONVERTER_SCRIPT} {' '.join(cmd_args)}"
        }

    # Make sure it's executable
    try:
        converter_path.chmod(0o755)
    except:
        pass  # Ignore if we can't change permissions

    # Run the command
    start_time = time.time()
    cmd = [str(CONVERTER_SCRIPT)] + cmd_args  # Run bash script directly
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_time

    # Check results
    success = result.returncode == 0
    file_exists = os.path.exists(test_output)

    # Get file info if it exists
    file_info = {}
    chapter_count = 0
    chapter_titles = []

    if file_exists:
        file_size = os.path.getsize(test_output) / (1024 * 1024)  # MB
        file_info['size_mb'] = round(file_size, 2)

        # PROPER CHAPTER CHECK using ffprobe
        try:
            ffprobe_cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_chapters",
                test_output
            ]
            chapter_result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
            if chapter_result.returncode == 0:
                chapter_data = json.loads(chapter_result.stdout)
                chapter_count = len(chapter_data.get('chapters', []))
                file_info['chapter_count'] = chapter_count

                # Get chapter titles if available
                chapters = []
                for ch in chapter_data.get('chapters', []):
                    title = ch.get('tags', {}).get('title', 'Untitled')
                    start = float(ch.get('start_time', 0))
                    end = float(ch.get('end_time', 0))
                    chapters.append({
                        'title': title,
                        'start': start,
                        'end': end,
                        'duration': end - start
                    })
                    chapter_titles.append(title)
                file_info['chapters'] = chapters
                file_info['chapter_titles'] = chapter_titles
        except Exception as e:
            print(f"  Warning: Could not read chapters: {e}")

        # Get bitrate and cover info using mediainfo
        try:
            mediainfo = subprocess.run(
                ["mediainfo", "--Output=JSON", test_output],
                capture_output=True,
                text=True
            )
            if mediainfo.returncode == 0:
                mediainfo_data = json.loads(mediainfo.stdout)
                file_info['mediainfo'] = mediainfo_data

                # Extract bitrate and cover info
                tracks = mediainfo_data.get('media', {}).get('track', [])
                for track in tracks:
                    if track.get('@type') == 'Audio':
                        bitrate = track.get('BitRate', 'N/A')
                        file_info['bitrate'] = bitrate
                    if track.get('@type') == 'General':
                        if track.get('Cover') == 'Yes':
                            file_info['has_cover'] = True
        except:
            pass

    # Check if size is in expected range
    size_ok = True
    if expected_size_range and file_exists:
        min_size, max_size = expected_size_range
        file_size = file_info.get('size_mb', 0)
        size_ok = min_size <= file_size <= max_size

    # Check if chapter count matches expected
    chapters_ok = True
    if expected_chapters is not None and file_exists:
        chapters_ok = (chapter_count == expected_chapters)

    # Determine overall pass/fail
    overall_success = success and file_exists and size_ok and chapters_ok

    # Print results
    status = "✓ PASS" if overall_success else "✗ FAIL"
    print(f"\nRESULT: {status}")
    print(f"Time: {elapsed:.1f}s")

    if file_exists:
        print(f"File: {test_output}")
        print(f"Size: {file_info.get('size_mb', 0):.2f} MB")
        print(f"Chapters: {chapter_count}")

        # Show chapter details
        if chapter_titles:
            print("Chapter titles:")
            for i, title in enumerate(chapter_titles[:4]):  # Show first 4
                if title != 'Untitled':
                    print(f"  {i+1}. {title}")
            if len(chapter_titles) > 4:
                print(f"  ... and {len(chapter_titles) - 4} more")
        elif chapter_count > 0:
            print(f"  (Found {chapter_count} chapters but no titles)")

        # Show bitrate and cover info
        if 'bitrate' in file_info:
            print(f"Bitrate: {file_info['bitrate']}")
        if file_info.get('has_cover'):
            print("Cover: Embedded ✓")
        elif 'no-cover' in ' '.join(cmd_args):
            print("Cover: Not embedded (as requested)")
        else:
            print("Cover: Not found ⚠")

        # Show what failed
        failures = []
        if not size_ok:
            failures.append(f"Size: {file_info.get('size_mb', 0):.2f} MB (expected {expected_size_range[0]}-{expected_size_range[1]} MB)")
        if not chapters_ok and expected_chapters is not None:
            failures.append(f"Chapters: got {chapter_count}, expected {expected_chapters}")

        if failures:
            print("\nFAILURE DETAILS:")
            for f in failures:
                print(f"  ⚠ {f}")
    else:
        print("File not created!")

    if result.stderr and not success:
        print(f"\nERROR OUTPUT:\n{result.stderr[:500]}...")

    return {
        'name': test_name,
        'success': overall_success,
        'file_exists': file_exists,
        'elapsed': elapsed,
        'file_info': file_info,
        'size_ok': size_ok,
        'chapters_ok': chapters_ok,
        'chapter_count': chapter_count,
        'cmd': ' '.join(cmd)
    }

def probe_m4b_tags(m4b_path):
    """Read the metadata tags of an M4B file via ffprobe (dict of lowercase keys)."""
    try:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_entries", "format_tags", str(m4b_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return {}
        data = json.loads(res.stdout)
        tags = data.get("format", {}).get("tags", {}) or {}
        return {str(k).lower(): str(v) for k, v in tags.items()}
    except Exception:
        return {}

def probe_m4b_details(m4b_path):
    """Probe an M4B for container/codec/chapter info via ffprobe."""
    try:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", "-show_chapters", str(m4b_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return {}
        data = json.loads(res.stdout)
        fmt = data.get("format", {}) or {}
        streams = data.get("streams", []) or []
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        return {
            "format_name": fmt.get("format_name", ""),
            "audio_codec": audio.get("codec_name", ""),
            "chapters": len(data.get("chapters") or []),
        }
    except Exception:
        return {}

def run_output_pattern_test():
    """Test the new --output-pattern flag (single-book mode)."""
    name = "Test_Output_Pattern"
    book = BATCH_BOOKS[0]
    src = BATCH_TEST_DIR / book["folder"]
    result = {
        'name': name,
        'success': False,
        'file_exists': False,
        'elapsed': 0,
        'file_info': {},
        'size_ok': True,
        'chapters_ok': True,
        'chapter_count': 0,
        'cmd': None,
        'skipped': False,
    }

    if not src.exists():
        print(f"  ⚠ Batch test data not found ({src}); skipping {name}")
        result['skipped'] = True
        result['success'] = True
        return result

    expected_name = f"{book['title']} by {book['author']}.m4b"
    out_dir = src / "m4b"
    expected_file = out_dir / expected_name

    if out_dir.exists():
        shutil.rmtree(out_dir)

    cmd_args = ["--quiet", "--output-pattern", "{title} by {author}"]

    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"CMD: {CONVERTER_SCRIPT} {src} {' '.join(cmd_args)}")
    print('='*60)

    start_time = time.time()
    cmd = [str(CONVERTER_SCRIPT), str(src)] + cmd_args
    result_cmd = str(CONVERTER_SCRIPT) + " " + " ".join([str(src)] + cmd_args)
    result['cmd'] = result_cmd
    sub = subprocess.run(cmd, capture_output=True, text=True)
    result['elapsed'] = time.time() - start_time

    result['success'] = sub.returncode == 0 and expected_file.exists()
    result['file_exists'] = expected_file.exists()
    if expected_file.exists():
        result['file_info']['size_mb'] = round(expected_file.stat().st_size / (1024 * 1024), 2)

    status = "✓ PASS" if result['success'] else "✗ FAIL"
    print(f"\nRESULT: {status}")
    print(f"Time: {result['elapsed']:.1f}s")
    print(f"Expected file: {expected_file}")
    print(f"File exists: {result['file_exists']}")
    if sub.stderr and sub.returncode != 0:
        print(f"\nERROR OUTPUT:\n{sub.stderr[:500]}...")

    return result

def run_batch_test(batch_dir=BATCH_TEST_DIR):
    """Verify CLI --batch converts every subfolder as its own audiobook."""
    name = "Test_Batch"
    result = {
        'name': name,
        'success': False,
        'file_exists': False,
        'elapsed': 0,
        'file_info': {},
        'size_ok': True,
        'chapters_ok': True,
        'chapter_count': 0,
        'cmd': None,
        'skipped': False,
    }

    if not batch_dir.exists() or not any((batch_dir / b["folder"]).exists() for b in BATCH_BOOKS):
        print(f"  Skipped batch test - batch directory not found: {batch_dir}")
        result['skipped'] = True
        result['success'] = True
        return result

    # Fresh outputs: each book writes to its own <folder>/m4b
    for b in BATCH_BOOKS:
        out = batch_dir / b["folder"] / "m4b"
        if out.exists():
            shutil.rmtree(out)

    cmd_args = ["--batch", "--quiet"]
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"CMD: {CONVERTER_SCRIPT} {batch_dir} {' '.join(cmd_args)}")
    print('='*60)

    start_time = time.time()
    cmd = [str(CONVERTER_SCRIPT), str(batch_dir)] + cmd_args
    result['cmd'] = " ".join(str(a) for a in cmd)
    sub = subprocess.run(cmd, capture_output=True, text=True)
    result['elapsed'] = time.time() - start_time

    # Verify each book produced exactly one .m4b in its own <folder>/m4b
    all_books_ok = True
    total_size = 0.0
    found = 0
    for b in BATCH_BOOKS:
        out = batch_dir / b["folder"] / "m4b"
        files = sorted(out.glob("*.m4b")) if out.exists() else []
        ok = len(files) >= 1
        all_books_ok = all_books_ok and ok
        if ok:
            found += 1
            total_size += files[0].stat().st_size / (1024 * 1024)
            print(f"  ✓ {b['title']}: {files[0].name} ({len(files)} file(s))")

            # Output-format validity: must be an MP4/M4A container with AAC audio.
            details = probe_m4b_details(files[0])
            is_valid_m4b = (
                "mp4" in details.get("format_name", "").lower() or
                "m4a" in details.get("format_name", "").lower()
            ) and details.get("audio_codec", "").lower() == "aac"
            chapters_match = details.get("chapters") == b.get("chapters")
            all_books_ok = all_books_ok and is_valid_m4b and chapters_match
            print(f"      format={details.get('format_name')!r} "
                  f"codec={details.get('audio_codec')!r} chapters={details.get('chapters')} "
                  f"(expected {b.get('chapters')}) -> "
                  f"{'✓' if is_valid_m4b and chapters_match else '✗'}")

            # For a book with no metadata file, verify the folder-name fallback:
            # Title/Album/Sort Name == directory name, Track == 1, Media Type == 2.
            if not b.get("has_metadata", True):
                tags = probe_m4b_tags(files[0])
                expected = b["title"]
                checks = {
                    "title": tags.get("title"),
                    "album": tags.get("album"),
                    "sort_name": (tags.get("sort_name") or tags.get("sortname") or tags.get("sonm")),
                    "track": (tags.get("track") or "").split("/")[0] if tags.get("track") else None,
                    "media_type": tags.get("media_type"),
                }
                expected_track = "1"
                expected_media = "2"
                fallback_ok = (checks["title"] == expected and
                               checks["sort_name"] == expected and
                               checks["track"] == expected_track and
                               checks["media_type"] == expected_media)
                all_books_ok = all_books_ok and fallback_ok
                print(f"      folder-name fallback tags: title={checks['title']!r} "
                      f"album={checks['album']!r} sort={checks['sort_name']!r} "
                      f"track={checks['track']!r} media_type={checks['media_type']!r} "
                      f"-> {'✓' if fallback_ok else '✗'}")
        else:
            print(f"  ✗ {b['title']}: no .m4b in {out}")

    result['success'] = sub.returncode == 0 and all_books_ok
    result['file_exists'] = all_books_ok
    result['file_info']['size_mb'] = round(total_size, 2)

    status = "✓ PASS" if result['success'] else "✗ FAIL"
    print(f"\nRESULT: {status} (expected {len(BATCH_BOOKS)} books)")
    print(f"Time: {result['elapsed']:.1f}s")
    print(f"Books with output: {found}/{len(BATCH_BOOKS)}")
    if sub.stderr and sub.returncode != 0:
        print(f"\nERROR OUTPUT:\n{sub.stderr[:500]}...")

    return result

def main():
    # Change to test directory
    test_dir = os.path.expanduser(input("Enter music directory [default: ~/Music]: ").strip() or "~/Music") 
    os.chdir(test_dir)

    # Ensure output directory exists
    os.makedirs("./m4b", exist_ok=True)
    os.makedirs("./test_output", exist_ok=True)

    print("="*60)
    print(f"COMPREHENSIVE TEST SUITE FOR {os.path.basename(CONVERTER_SCRIPT)}")
    print("="*60)

    # Check if converter script exists
    if not os.path.exists(CONVERTER_SCRIPT):
        print(f"\n❌ ERROR: Converter script not found at: {CONVERTER_SCRIPT}")
        print("Please update the CONVERTER_SCRIPT path in this test file.")
        return 1

    # First, check how many chapters are in the original metadata
    try:
        metadata_path = "./metadata/metadata.json"
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            actual_chapters = len(metadata.get('chapters', []))
            print(f"\nFound {actual_chapters} chapters in metadata.json")
            if actual_chapters != EXPECTED_CHAPTERS:
                print(f"⚠ Warning: EXPECTED_CHAPTERS={EXPECTED_CHAPTERS} but metadata has {actual_chapters}")
                print("Update EXPECTED_CHAPTERS in the test script if needed.")
    except:
        print("Could not read metadata.json to verify chapter count")

    print("\n" + "="*60)
    print("STARTING TESTS")
    print("="*60)

    all_results = []

    # Test 1: Basic functionality (auto-detect, should be ~64k)
    all_results.append(run_test(
        "Test_Basic",
        ["--quiet", "-n", "Test_Basic"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # # Test 2: Different bitrates
    # all_results.append(run_test(
    #     "Test_64k",
    #     ["-b", "64k", "--quiet", "-n", "Test_64k"],
    #     expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
    #     expected_chapters=EXPECTED_CHAPTERS
    # ))
    #
    # all_results.append(run_test(
    #     "Test_128k",
    #     ["-b", "128", "--quiet", "-n", "Test_128k"],  # Test without 'k'
    #     expected_size_range=(BASE_SIZE_128K - 20, BASE_SIZE_128K + 20),
    #     expected_chapters=EXPECTED_CHAPTERS
    # ))

    all_results.append(run_test(
        "Test_192k",
        ["-b", "192k", "--quiet", "-n", "Test_192k"],
        expected_size_range=(BASE_SIZE_192K - 30, BASE_SIZE_192K + 30),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # Test 3: Different worker counts (size should be same as 64k)
    all_results.append(run_test(
        "Test_6_workers",
        ["-w", "6", "--quiet", "-n", "Test_6_workers"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # all_results.append(run_test(
    #     "Test_8_workers",
    #     ["-w", "8", "--quiet", "-n", "Test_8_workers"],
    #     expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
    #     expected_chapters=EXPECTED_CHAPTERS
    # ))

    # Test 4: Output modes (size should be same as 64k)
    all_results.append(run_test(
        "Test_Verbose",
        ["-v", "-n", "Test_Verbose"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    all_results.append(run_test(
        "Test_Debug",
        ["--debug", "-n", "Test_Debug", "--temp-dir", "./test_tmp"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # Test 5: Metadata options (size should be same as 64k)
    all_results.append(run_test(
        "Test_Metadata",
        [
            "--title", "Custom Book Title",
            "--author", "Test Author",
            "--year", "2024",
            "--genre", "Test Genre",
            "--comment", "Test comment for metadata",
            "--quiet",
            "-n", "Test_Metadata"
        ],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # Test 6: Processing options (size should be same as 64k)
    all_results.append(run_test(
        "Test_No_Optimize",
        ["--no-optimize", "--quiet", "-n", "Test_No_Optimize"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    all_results.append(run_test(
        "Test_Keep_Temp",
        ["--keep-temp", "--quiet", "-n", "Test_Keep_Temp", "--temp-dir", "./test_temp"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # Test 7: Cover options (size might be slightly smaller without cover)
    all_results.append(run_test(
        "Test_No_Cover",
        ["--no-cover", "--quiet", "-n", "Test_No_Cover"],
        expected_size_range=(BASE_SIZE_64K - 15, BASE_SIZE_64K + 5),  # Smaller without cover
        expected_chapters=EXPECTED_CHAPTERS
    ))

    #Test 8: Different output locations (size should be same as 64k)
    all_results.append(run_test(
        "Test_Custom_Output",
        ["-o", "./test_output", "--quiet", "-n", "Test_Custom_Output"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # Test 9: Overwrite test (run twice, size should be same as 64k)
    run_test("Test_Overwrite_1",
             ["--quiet", "-n", "Test_Overwrite"],
             expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
             expected_chapters=EXPECTED_CHAPTERS)

    all_results.append(run_test(
        "Test_Overwrite_2",
        ["--overwrite", "--quiet", "-n", "Test_Overwrite"],
        expected_size_range=(BASE_SIZE_64K - 10, BASE_SIZE_64K + 10),
        expected_chapters=EXPECTED_CHAPTERS, delete_previous_file=False
    ))

    # Test 10: Comprehensive test (160k bitrate)
    # 160k size: 160 × 37875 / 8 / 1024 = ~740 MB
    all_results.append(run_test(
        "Test_Comprehensive",
        [
            "-b", "160k",
            "-w", "4",
            "--title", "Comprehensive Test Title",
            "--author", "Comprehensive Author",
            "--year", "2024",
            "--genre", "Mystery",
            "--comment", "Testing all options together",
            "--no-optimize",
            "--keep-temp",
            "--temp-dir", "./comprehensive_temp",
            "-o", "./test_output",
            "--verbose",
            "-n", "Test_Comprehensive"
        ],
        expected_size_range=(730, 750),  # 160k AAC
        expected_chapters=EXPECTED_CHAPTERS
    ))

    # Test 11: New --output-pattern flag (v1.3)
    all_results.append(run_output_pattern_test())

    # Test 12: Batch mode (v1.3) - convert every subfolder as its own book
    all_results.append(run_batch_test())

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for r in all_results if r['success'])
    total = len(all_results)
    skipped = sum(1 for r in all_results if r.get('skipped'))

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Skipped (batch data not present): {skipped}")
    print(f"Success Rate: {(passed/total*100):.1f}%")

    print("\n" + "="*60)
    print("DETAILED RESULTS")
    print("="*60)

    for result in all_results:
        status = "✓" if result['success'] else "✗"
        size = result['file_info'].get('size_mb', 0)
        ch_count = result.get('chapter_count', 0)
        print(f"{status} {result['name']:25} {result['elapsed']:6.1f}s  {size:7.2f}MB  Ch:{ch_count:2d}")

    # Show failures in detail
    failures = [r for r in all_results if not r['success']]
    if failures:
        print("\n" + "="*60)
        print("FAILURE ANALYSIS")
        print("="*60)
        for result in failures:
            print(f"\n{result['name']}:")
            if not result['file_exists']:
                print("  ✗ File not created")
            if not result.get('size_ok', True):
                print(f"  ✗ Wrong size: {result['file_info'].get('size_mb', 0):.2f}MB")
            if not result.get('chapters_ok', True):
                print(f"  ✗ Wrong chapter count: got {result.get('chapter_count', 0)}, expected {EXPECTED_CHAPTERS}")

    # Cleanup temporary directories
    for temp_dir in ["./test_tmp", "./test_temp", "./comprehensive_temp"]:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    print(f"\nTest files saved in: ./m4b/ and ./test_output/")
    print("Note: Some test files may be identical (same bitrate settings)")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
