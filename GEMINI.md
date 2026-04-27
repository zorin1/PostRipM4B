# PostRipM4B

PostRipM4B is a tool to convert MP3 files (typically from LibbyRip) into formatted M4B audiobooks with chapters, cover art, and metadata. It now includes a Dockerized web interface for easier use.

## Project Overview

- **Core Functionality:** Audio file processing (MP3 to M4B), metadata handling, chapter generation, and cover art embedding using `ffmpeg`.
- **Technologies:** Python, PyQt5 (for the original GUI), FastAPI (for the web interface), Docker.
- **Architecture:** 
    - `PostRipM4B.py`: Main CLI/GUI entry point.
    - `converter_service.py`: Extracted core conversion logic.
    - `web_server.py`: FastAPI web interface.
    - `chapter_parser.py`: Logic for parsing Libby/FFmpeg/etc. chapter formats.

## Building and Running

### Docker (Recommended)

1. Build the image:
   ```bash
   docker-compose build
   ```
2. Run the application:
   ```bash
   docker-compose up
   ```
3. Access the web interface at `http://localhost:8080`.

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install fastapi uvicorn python-multipart
   ```
2. Ensure `ffmpeg` is installed and in your PATH.
3. Run CLI:
   ```bash
   python PostRipM4B.py /path/to/audiobook
   ```

## Development Conventions

- **Logic Separation:** Keep core conversion logic in `converter_service.py` to allow multiple interfaces (CLI, GUI, Web).
- **Metadata Handling:** The system relies on `chapter_parser.py` to handle various input formats. New formats should be integrated there.
- **Dockerization:** Any new dependencies must be added to the `Dockerfile`.
- **Validation:** Always verify output M4B files against the input MP3s for quality and metadata accuracy.
