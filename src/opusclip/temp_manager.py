import tempfile
import shutil
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

class TempDir:
    """
    Context manager for creating a secure temporary directory that cleans up
    automatically upon exit.
    """
    
    def __init__(self, prefix: str = "opusclip_") -> None:
        self.prefix = prefix
        self.path: Optional[Path] = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self.path

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.path and self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
