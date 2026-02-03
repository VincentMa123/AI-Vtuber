# Re-export for backward compatibility
from .behavior import Behavior
from .controller import BrowserController, get_browser_controller

__all__ = [
    'Behavior',
    'BrowserController',
    'get_browser_controller',
]
