"""
Browser automation module.

This module provides browser control capabilities using Playwright
for automated browsing and screenshot capture.
"""

from .behavior import Behavior
from .controller import BrowserController, get_browser_controller

__all__ = [
    'Behavior',
    'BrowserController',
    'get_browser_controller',
]
