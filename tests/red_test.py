#!/usr/bin/env python3
"""
Simple script to turn all LEDs attached to pin 28 to red.
This script can be run independently to test LED functionality.
"""

import board
import neopixel
import time

def set_leds_to_red():
    """Turn all LEDs on pin 28 to red color."""
    
    # Configuration
    LED_PIN = board.D18  # GPIO pin 18
    LED_COUNT = 47      # Adjust this to match your actual LED count

    # Each line has its own LED count:
    # Red Line: 47 LEDs
    # Blue Line: 27 LEDs
    # Orange Line: 43 LEDs
    # Green Line: 131 LEDs (combined, one color key)
    #     - Green-B: 41 LEDs
    #     - Green-C: 31 LEDs
    #     - Green-D: 31 LEDs
    #     - Green-E: 37 LEDs
    
    BRIGHTNESS = 1.0     # Full brightness
    
    try:
        # Initialize the LED strip
        print(f"Initializing {LED_COUNT} LEDs on pin 28...")
        pixels = neopixel.NeoPixel(
            LED_PIN,
            LED_COUNT,
            brightness=BRIGHTNESS,
            auto_write=False,
            pixel_order=neopixel.GRB
        )
        
        # Set all LEDs to red
        print("Setting all LEDs to red...")
        red_color = (255, 0, 0)  # Red in RGB format
        pixels.fill(red_color)
        pixels.show()
        
        print(f"Successfully set {LED_COUNT} LEDs to red!")
        print("Press Ctrl+C to exit...")
        
        # Keep the LEDs on until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTurning off all LEDs...")
        pixels.fill((0, 0, 0))  # Turn off all LEDs
        pixels.show()
        print("All LEDs turned off. Goodbye!")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have the required libraries installed:")
        print("pip install adafruit-circuitpython-neopixel")

if __name__ == "__main__":
    set_leds_to_red()