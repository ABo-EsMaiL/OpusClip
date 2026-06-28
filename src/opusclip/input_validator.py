import urllib.parse
from pathlib import Path
from .exceptions import InputValidationError

ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi"}

def validate_video_path(path: str) -> Path:
    """
    Validates a local video file path.
    Resolves symlinks, checks extension, and ensures the file exists.
    """
    p = Path(path).resolve()
    
    if not p.exists():
        raise InputValidationError(f"File does not exist: {path}")
        
    if not p.is_file():
        raise InputValidationError(f"Path is not a file: {path}")
        
    if p.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise InputValidationError(f"Unsupported video extension: {p.suffix}")
        
    return p

def validate_youtube_url(url: str) -> str:
    """
    Validates a YouTube URL structure securely using urllib.parse.
    """
    parsed = urllib.parse.urlparse(url)
    
    if parsed.scheme not in ("http", "https"):
        raise InputValidationError(f"Invalid URL scheme: {parsed.scheme}")
        
    netloc = parsed.netloc.lower()
    valid_domains = {"youtube.com", "www.youtube.com", "youtu.be"}
    
    if netloc not in valid_domains:
        raise InputValidationError(f"Invalid YouTube domain: {parsed.netloc}")
        
    return url
