import os
from pathlib import Path
import shutil
from typing import Optional
from PostRipM4B import Config, AudioBookConverter, Verbosity

def convert_audiobook(input_dir: str, title: Optional[str] = None, author: Optional[str] = None, bitrate: str = "64k"):
    """Core logic to convert audiobook, with auto-detection of metadata."""
    
    # Setup config
    config = Config(
        input_dir=input_dir,
        output_dir=os.path.join(input_dir, "output"),
        title=title,
        author=author,
        bitrate=bitrate,
        verbosity=Verbosity.NORMAL
    )
    
    # Ensure output directory exists
    os.makedirs(config.output_dir, exist_ok=True)
    
    # Run conversion
    # The AudioBookConverter class handles auto-detection of metadata/chapters
    # if config.title or config.author are not provided.
    converter = AudioBookConverter(config)
    converter.run()
    
    return {"status": "success", "output": config.output_dir}
