"""
Horizon6AutoGear - Automatic gear shifting for Forza Horizon 5

A real-time 60Hz gear shifting system that optimizes performance
based on telemetry data from Forza Horizon 5.

Package structure:
- core: Core classes (Forza, CarInfo)
- shifting: Gear calculation and keyboard input
- utils: Utility functions and logging
- config: Configuration constants

This package is in active migration from flat structure to
proper Python packaging.
"""

__version__ = "1.0.0"
__author__ = "Horizon6AutoGear Team"

# Package metadata - single source of truth for version
PROJECT_NAME = "Horizon6AutoGear"
VERSION = __version__

# CLI entry point for pyproject.toml
def main():
    """Main entry point for CLI launcher."""
    from . import __main__
    __main__.main() if hasattr(__main__, 'main') else None
