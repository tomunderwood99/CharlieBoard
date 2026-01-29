#!/usr/bin/env python3
"""Test script to monitor MBTA SSE stream keep-alive events and timing.

This script connects to the MBTA SSE stream using a non-existent route by default
to isolate and measure keep-alive/heartbeat events without actual vehicle data.
This helps determine the baseline keep-alive interval from the MBTA API.

Uses raw httpx streaming with manual SSE parsing to capture comment lines (": keep-alive")
which are not exposed by most SSE client libraries.


** RESULTS  **

Using keep-alive messages is possible, but requires switching to 
raw httpx streaming with manual SSE parsing to capture comment lines (": keep-alive").
I do not think it is worth the effort to use this approach, so I will continue using the
sseclient library. Technically the health status is untrustworthy during quiet hours, but
I think it is a good enough approximation for now.

"""

import sys
import os
import time
from datetime import datetime, timedelta

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import httpx
import json

class KeepAliveMonitor:
    """Monitor keep-alive events from MBTA SSE stream."""
    
    def __init__(self, api_key: str, route: str = "NonExistentRoute"):
        """Initialize the monitor.
        
        Args:
            api_key: MBTA API key
            route: MBTA route to monitor (default: NonExistentRoute to isolate keep-alives)
        """
        self.api_key = api_key
        self.route = route
        self.event_times = []
        self.keepalive_times = []
        self.data_event_times = []
    
    def run(self, duration_seconds: int = 300):
        """Run the monitor for specified duration.
        
        Args:
            duration_seconds: How long to monitor (default: 300 seconds = 5 minutes)
        """
        url = "https://api-v3.mbta.com/vehicles"
        headers = {"Accept": "text/event-stream"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        params = {
            "filter[route]": self.route,
            "include": "trip,stop"
        }
        
        print(f"\n{'='*70}")
        print(f"MBTA Keep-Alive Monitor")
        print(f"{'='*70}")
        print(f"Route: {self.route}")
        print(f"Duration: {duration_seconds} seconds")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        last_event_time = start_time
        event_count = 0
        keepalive_count = 0
        data_event_count = 0
        
        try:
            print(f"Connecting to MBTA SSE stream...")
            
            # Set timeout to 60 seconds to handle ~15-20 second keep-alive intervals
            timeout = httpx.Timeout(60.0, connect=10.0)
            
            with httpx.Client(timeout=timeout) as client:
                with client.stream("GET", url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    print(f"Connected! Monitoring events...\n")
                    
                    # Parse SSE stream manually to capture comment lines (keep-alives)
                    event_type = None
                    event_data = None
                    
                    for line in response.iter_lines():
                        current_time = time.time()
                        
                        # Check if duration exceeded
                        if current_time - start_time >= duration_seconds:
                            print(f"\n{'='*70}")
                            print(f"Duration limit reached ({duration_seconds}s). Stopping...")
                            print(f"{'='*70}")
                            break
                        
                        # Empty line marks end of a data event
                        if line == '':
                            if event_type is not None or event_data is not None:
                                # We have a complete data event
                                event_count += 1
                                data_event_count += 1
                                time_since_last = current_time - last_event_time
                                
                                self.data_event_times.append(current_time)
                                self.event_times.append(current_time)
                                
                                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                                
                                # Try to parse data
                                data_info = ""
                                if event_data:
                                    try:
                                        data = json.loads(event_data)
                                        if isinstance(data, dict):
                                            data_type = data.get('type', 'unknown')
                                            data_info = f", data_type='{data_type}'"
                                        elif isinstance(data, list):
                                            data_info = f", data_type='list', count={len(data)}"
                                    except (json.JSONDecodeError, Exception):
                                        data_info = ", data_type='unparseable'"
                                
                                print(f"[{timestamp}] Event #{event_count:4d} | DATA         | "
                                      f"Δt: {time_since_last:6.2f}s | event='{event_type}'{data_info}")
                                
                                last_event_time = current_time
                                
                                # Reset for next event
                                event_type = None
                                event_data = None
                            continue
                        
                        # Check for comment lines (keep-alive) - these start with ':'
                        if line.startswith(':'):
                            event_count += 1
                            keepalive_count += 1
                            time_since_last = current_time - last_event_time
                            
                            self.keepalive_times.append(current_time)
                            self.event_times.append(current_time)
                            
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            comment = line[1:].strip()  # Remove ':' and trim whitespace
                            print(f"[{timestamp}] Event #{event_count:4d} | KEEP-ALIVE   | "
                                  f"Δt: {time_since_last:6.2f}s | comment='{comment}'")
                            
                            last_event_time = current_time
                            continue
                        
                        # Parse event field
                        if line.startswith('event:'):
                            event_type = line[6:].strip()
                            continue
                        
                        # Parse data field
                        if line.startswith('data:'):
                            event_data = line[5:].strip()
                            continue
                    
        except KeyboardInterrupt:
            print(f"\n{'='*70}")
            print("Monitoring stopped by user (Ctrl+C)")
            print(f"{'='*70}")
        except Exception as e:
            print(f"\n{'='*70}")
            print(f"Error: {e}")
            print(f"{'='*70}")
        
        # Print statistics
        self.print_statistics(start_time, time.time(), event_count, keepalive_count, data_event_count)
    
    def print_statistics(self, start_time: float, end_time: float, 
                        event_count: int, keepalive_count: int, data_event_count: int):
        """Print statistics about the monitoring session."""
        duration = end_time - start_time
        
        print(f"\n{'='*70}")
        print("STATISTICS")
        print(f"{'='*70}")
        print(f"Total Duration:        {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"Total Events:          {event_count}")
        print(f"Keep-Alive Events:     {keepalive_count} ({keepalive_count/event_count*100:.1f}%)")
        print(f"Data Events:           {data_event_count} ({data_event_count/event_count*100:.1f}%)")
        
        if event_count > 1:
            avg_interval = duration / (event_count - 1)
            print(f"Avg Event Interval:    {avg_interval:.2f} seconds")
        
        # Keep-alive intervals
        if len(self.keepalive_times) > 1:
            keepalive_intervals = [
                self.keepalive_times[i] - self.keepalive_times[i-1] 
                for i in range(1, len(self.keepalive_times))
            ]
            avg_keepalive = sum(keepalive_intervals) / len(keepalive_intervals)
            min_keepalive = min(keepalive_intervals)
            max_keepalive = max(keepalive_intervals)
            
            print(f"\nKeep-Alive Timing:")
            print(f"  Average Interval:    {avg_keepalive:.2f} seconds")
            print(f"  Min Interval:        {min_keepalive:.2f} seconds")
            print(f"  Max Interval:        {max_keepalive:.2f} seconds")
        
        # Data event intervals
        if len(self.data_event_times) > 1:
            data_intervals = [
                self.data_event_times[i] - self.data_event_times[i-1] 
                for i in range(1, len(self.data_event_times))
            ]
            avg_data = sum(data_intervals) / len(data_intervals)
            min_data = min(data_intervals)
            max_data = max(data_intervals)
            
            print(f"\nData Event Timing:")
            print(f"  Average Interval:    {avg_data:.2f} seconds")
            print(f"  Min Interval:        {min_data:.2f} seconds")
            print(f"  Max Interval:        {max_data:.2f} seconds")
        
        print(f"{'='*70}\n")


def main():
    """Main entry point."""
    # Get API key from command line or environment variable
    api_key = os.environ.get('MBTA_API_KEY')
    # Use a non-existent route to ensure we only see keep-alive events
    # without any actual vehicle data events
    route = "NonExistentRoute"
    duration = 300  # 5 minutes default
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help']:
            print("Usage: python keepalive_test.py [duration_seconds] [route] [api_key]")
            print("  duration_seconds: How long to monitor (default: 300)")
            print("  route: MBTA route to monitor (default: NonExistentRoute)")
            print("         Note: Using a non-existent route isolates keep-alive events")
            print("  api_key: MBTA API key (default: from MBTA_API_KEY env var)")
            return
        duration = int(sys.argv[1])
    
    if len(sys.argv) > 2:
        route = sys.argv[2]
    
    if len(sys.argv) > 3:
        api_key = sys.argv[3]
    
    # Warn if no API key provided
    if not api_key:
        print("WARNING: No MBTA API key provided.")
        print("  Set the MBTA_API_KEY environment variable or pass it as the third argument.")
        print("  Get a free API key at: https://api-v3.mbta.com/")
        print("  The test will continue but may be rate-limited.\n")
    
    # Create and run monitor
    monitor = KeepAliveMonitor(api_key, route)
    monitor.run(duration)


if __name__ == "__main__":
    main()

