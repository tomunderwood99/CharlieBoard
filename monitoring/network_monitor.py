#!/usr/bin/env python3
"""
Network Monitor Classes for MBTA LED Controller

This module provides proactive network monitoring functionality that runs
independently of the main SSE stream. While the SSE stream handles its own
reconnection when it fails, this monitor provides:

1. Proactive detection: Identifies network issues before the SSE stream times out
2. LED feedback: Updates the LED display to show network status (red=disconnected)
3. WiFi recovery: Attempts to restart the wireless interface on connection loss

Design note: This runs as a separate thread polling every 30 seconds. On a Pi Zero 2W,
this overhead is minimal (brief network request). The proactive monitoring
improves user experience by providing immediate visual feedback when network issues
occur, rather than waiting for the SSE stream to timeout.

If you want to disable this for lower resource usage, you can remove the NetworkMonitor
initialization from mbta_stream.py and handle network status purely based on SSE failures.
"""

import subprocess
import time
import logging
import threading
import requests
from typing import Optional, Callable
from datetime import datetime, timedelta
from config.constants import (
    NETWORK_MAX_RETRIES,
    NETWORK_CHECK_INTERVAL_SECONDS,
    NETWORK_REQUEST_TIMEOUT_SECONDS,
    WIFI_INTERFACE_DOWN_WAIT_SECONDS,
    WIFI_INTERFACE_UP_WAIT_SECONDS,
    WIFI_RECONNECTION_WAIT_SECONDS,
)

logger = logging.getLogger(__name__)

class NetworkMonitor:
    """Monitors network connectivity and handles reconnection attempts."""
    
    def __init__(self, 
                 on_disconnect: Optional[Callable] = None,
                 on_reconnect: Optional[Callable] = None,
                 max_retries: int = NETWORK_MAX_RETRIES,
                 check_interval: int = NETWORK_CHECK_INTERVAL_SECONDS):
        """Initialize the network monitor.
        
        Args:
            on_disconnect: Callback function when network disconnects
            on_reconnect: Callback function when network reconnects
            max_retries: Maximum number of reconnection attempts
            check_interval: Seconds between connectivity checks
        """
        self.on_disconnect = on_disconnect
        self.on_reconnect = on_reconnect
        self.max_retries = max_retries
        self.check_interval = check_interval
        
        self._is_connected = True
        self._last_connected = datetime.now()
        self._retry_count = 0
        self._should_run = True
        self._lock = threading.Lock()
        
        # Start monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self._monitor_thread.start()
    
    def _check_connection(self) -> bool:
        """Check if network is connected.
        
        Returns:
            bool: True if connected
        """
        try:
            # Try to reach a reliable endpoint
            response = requests.get("https://api-v3.mbta.com/", timeout=NETWORK_REQUEST_TIMEOUT_SECONDS)
            return response.status_code == 200
        except Exception:
            return False
    
    def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to WiFi.
        
        Returns:
            bool: True if reconnection successful
        """
        try:
            # Restart the wireless interface
            subprocess.run(['sudo', 'ifconfig', 'wlan0', 'down'], timeout=NETWORK_REQUEST_TIMEOUT_SECONDS)
            time.sleep(WIFI_INTERFACE_DOWN_WAIT_SECONDS)
            subprocess.run(['sudo', 'ifconfig', 'wlan0', 'up'], timeout=NETWORK_REQUEST_TIMEOUT_SECONDS)
            time.sleep(WIFI_INTERFACE_UP_WAIT_SECONDS)  # Wait for interface to initialize
            
            # Check if reconnection worked
            return self._check_connection()
        except Exception:
            return False
    
    def _monitor_connection(self) -> None:
        """Monitor network connection and handle reconnection."""
        while self._should_run:
            is_connected = self._check_connection()
            
            with self._lock:
                if is_connected and not self._is_connected:
                    # Network restored
                    logger.info("Network connection restored")
                    self._is_connected = True
                    self._last_connected = datetime.now()
                    self._retry_count = 0
                    if self.on_reconnect:
                        self.on_reconnect()
                
                elif not is_connected and self._is_connected:
                    # Network lost
                    logger.warning("Network connection lost")
                    self._is_connected = False
                    if self.on_disconnect:
                        self.on_disconnect()
                    
                    # Attempt reconnection
                    while (not self._is_connected and 
                           self._retry_count < self.max_retries and 
                           self._should_run):
                        logger.info(f"Attempting reconnection (attempt {self._retry_count + 1}/{self.max_retries})")
                        if self._attempt_reconnect():
                            self._is_connected = True
                            self._last_connected = datetime.now()
                            if self.on_reconnect:
                                self.on_reconnect()
                            break
                        self._retry_count += 1
                        time.sleep(WIFI_RECONNECTION_WAIT_SECONDS)  # Wait between attempts
            
            time.sleep(self.check_interval)
    
    def is_connected(self) -> bool:
        """Check if network is currently connected.
        
        Returns:
            bool: True if connected
        """
        with self._lock:
            return self._is_connected
    
    def get_status(self) -> dict:
        """Get current network status.
        
        Returns:
            dict: Network status information
        """
        with self._lock:
            return {
                'connected': self._is_connected,
                'last_connected': self._last_connected.isoformat(),
                'retry_count': self._retry_count
            }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self._should_run = False
        if self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
