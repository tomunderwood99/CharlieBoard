import board
import neopixel
from typing import List, Tuple
from config.bedtime import BedtimeManager
from config.constants import (
    NETWORK_DISCONNECTED_COLOR,
    NETWORK_RECONNECTING_COLOR,
    LED_OFF,
    BRIGHTNESS_MIN,
    BRIGHTNESS_MAX,
)
import logging

logger = logging.getLogger(__name__)

class LEDController:
    """Controls the physical LED strip display."""
    
    def __init__(self, led_count: int, color_key_count: int = 3, brightness: float = 1.0, power_state: str = 'off',
                 bedtime_start: str = "22:00", bedtime_end: str = "06:00", metrics=None):
        """Initialize the LED controller.
        
        Args:
            led_count: Number of LEDs for train display
            color_key_count: Number of LEDs used for color key
            brightness: Initial brightness (0.0 to 1.0)
            power_state: Initial power state ('on' or 'off')
            bedtime_start: Time to turn off display (24-hour format "HH:MM")
            bedtime_end: Time to turn on display (24-hour format "HH:MM")
            metrics: Optional SystemMetrics instance for tracking LED updates
        """
        self.led_count = led_count
        self.color_key_count = color_key_count
        self.total_leds = led_count + color_key_count
        self.user_power_state = power_state == 'on'
        self._last_colors = [LED_OFF] * self.led_count
        self._last_color_key = [LED_OFF] * self.color_key_count
        self._network_status = 'connected'
        self.metrics = metrics
        
        # Initialize bedtime manager
        self.bedtime_manager = BedtimeManager(bedtime_start, bedtime_end)
        
        # Initialize the LED strip
        self.pixels = neopixel.NeoPixel(
            board.D18,  # GPIO pin
            self.total_leds,
            brightness=brightness,
            auto_write=False,
            pixel_order=neopixel.GRB
        )
        
        # Turn off all LEDs initially
        self.clear_display()
    
    def is_display_on(self) -> bool:
        """Check if display should be on based on power state and bedtime.
        
        Returns:
            bool: True if display should be on
        """
        if not self.user_power_state:
            return False
            
        if self.bedtime_manager.is_bedtime():
            return False
            
        return True
    
    def update_display(self, colors: List[Tuple[int, int, int]], color_key: List[Tuple[int, int, int]]) -> None:
        """Update the LED display with new colors.
        
        Args:
            colors: List of RGB tuples for train display LEDs
            color_key: List of RGB tuples for color key LEDs
        """
        # Store the colors for power-on restore
        self._last_colors = colors[:self.led_count]
        self._last_color_key = color_key[:self.color_key_count]

        if not self.is_display_on():
            self.clear_display()
            # Record LED update for health monitoring even when display is off
            if self.metrics:
                self.metrics.record_led_update()
            return
        
        # If network is disconnected, show network status instead
        if self._network_status != 'connected':
            self._show_network_status()
            return
        
        # Update train display LEDs
        for i, color in enumerate(colors):
            if i < self.led_count:
                self.pixels[i] = color
        
        # Update color key LEDs
        for i, color in enumerate(color_key):
            if i < self.color_key_count:
                self.pixels[-(i+1)] = color
        
        self.pixels.show()
        
        # Record LED update for health monitoring
        if self.metrics:
            self.metrics.record_led_update()
    
    def _show_network_status(self) -> None:
        """Display network status using LEDs."""
        if self._network_status == 'disconnected':
            color = NETWORK_DISCONNECTED_COLOR
        else:  # reconnecting
            color = NETWORK_RECONNECTING_COLOR
        
        # Fill all LEDs with the status color
        self.pixels.fill(color)
        self.pixels.show()
        
        # Record LED update for health monitoring
        if self.metrics:
            self.metrics.record_led_update()
    
    def set_network_status(self, status: str) -> None:
        """Update network status and display.
        
        Args:
            status: Network status ('connected', 'disconnected', or 'reconnecting')
        """
        if status not in ['connected', 'disconnected', 'reconnecting']:
            raise ValueError(f"Invalid network status: {status}")
        
        self._network_status = status
        
        if self.is_display_on():
            if status == 'connected':
                # Restore normal display
                self.update_display(self._last_colors, self._last_color_key)
            else:
                # Show network status
                self._show_network_status()
    
    def set_brightness(self, brightness: float) -> None:
        """Set the brightness of the LED strip.
        
        Args:
            brightness: Brightness value between 0.0 and 1.0
        """
        self.pixels.brightness = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, brightness))
        if self.is_display_on():
            self.pixels.show()
            # Record LED update for health monitoring
            if self.metrics:
                self.metrics.record_led_update()
    
    def set_power(self, power_state: str) -> None:
        """Set the user power state of the LED strip.
        
        Args:
            power_state: 'on' or 'off'
        """
        old_state = self.is_display_on()
        self.user_power_state = power_state == 'on'
        new_state = self.is_display_on()
        
        # Only update display if state actually changed
        if old_state != new_state:
            if new_state:
                if self._network_status != 'connected':
                    self._show_network_status()
                else:
                    # Restore last known state
                    self.update_display(self._last_colors, self._last_color_key)
            else:
                self.clear_display()
                # Note: clear_display() already calls record_led_update()
    
    def update_bedtime(self, bedtime_start: str, bedtime_end: str) -> None:
        """Update bedtime hours.
        
        Args:
            bedtime_start: Time to turn off display (24-hour format "HH:MM")
            bedtime_end: Time to turn on display (24-hour format "HH:MM")
        """
        old_state = self.is_display_on()
        self.bedtime_manager.update_bedtime(bedtime_start, bedtime_end)
        new_state = self.is_display_on()
        
        # Only update display if state changed
        if old_state != new_state:
            if new_state:
                if self._network_status != 'connected':
                    self._show_network_status()
                else:
                    # Coming out of bedtime, restore last state
                    self.update_display(self._last_colors, self._last_color_key)
            else:
                # Entering bedtime, clear display
                self.clear_display()
                # Note: clear_display() already calls record_led_update()
    
    def clear_display(self) -> None:
        """Turn off all LEDs."""
        self.pixels.fill(LED_OFF)
        self.pixels.show()
        
        # Record LED update for health monitoring
        if self.metrics:
            self.metrics.record_led_update()
    
    def clear_station_leds(self) -> None:
        """Clear station/train LEDs but keep the color key lit.
        
        This is useful during quiet hours when no trains are running but
        the display is still on and we want to show the color key.
        """
        if not self.is_display_on():
            # If display is off, just clear everything normally
            self.clear_display()
            return
        
        # Clear station LEDs (train display area)
        for i in range(self.led_count):
            self.pixels[i] = LED_OFF
        
        # Keep color key lit with last known colors
        for i, color in enumerate(self._last_color_key):
            if i < self.color_key_count:
                self.pixels[-(i+1)] = color
        
        self.pixels.show()
        
        # Record LED update for health monitoring
        if self.metrics:
            self.metrics.record_led_update()
    
    def cleanup(self) -> None:
        """Clean up resources before shutting down."""
        self.clear_display() 