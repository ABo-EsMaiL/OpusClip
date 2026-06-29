"""Test package."""

import os
import sys

# Ensure the src directory is on the path for imports.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.abspath(os.path.join(_this_dir, "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)
