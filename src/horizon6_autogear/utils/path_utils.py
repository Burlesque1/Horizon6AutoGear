"""
Path utility functions for Horizon6AutoGear

Extracted from helper.py to break circular dependency:
- helper.py → keyboard_helper.py → car_info.py → helper.py (CIRCULAR)
- helper.py → keyboard_helper.py → car_info.py → path_utils.py (ACYCLIC)

This module contains only stdlib dependencies to avoid circular imports.
"""

import os
from typing import Optional


def get_config_path(config_folder: Optional[str], filename: str) -> str:
    """
    Get full path to config file

    Args:
        config_folder: Config folder path (can be None)
        filename: Config file name

    Returns:
        Full path to config file, or just filename if config_folder is None
    """
    return os.path.join(config_folder, filename) if config_folder else filename
