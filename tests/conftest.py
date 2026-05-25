"""
Pytest configuration for Horizon6AutoGear
"""
import sys
from pathlib import Path

# Add project root and src to Python path
project_root = Path(__file__).parent.parent
src_path = project_root / 'src'

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
