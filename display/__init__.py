"""
MBTA LED Controller - Display Module

This module contains all display-related functionality including LED control,
display modes, and mode management.

Hardware-dependent imports (LEDController) are lazy so pure helpers like
speed_estimator can be unit-tested off-device.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .controller.led_controller import LEDController
    from .mode_manager import ModeManager

__all__ = ['LEDController', 'ModeManager']


def __getattr__(name: str):
    if name == 'LEDController':
        from .controller.led_controller import LEDController
        return LEDController
    if name == 'ModeManager':
        from .mode_manager import ModeManager
        return ModeManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
