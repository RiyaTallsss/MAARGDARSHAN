#!/usr/bin/env python3
"""
Diagnose what the stuck OSM cache generation process is doing
"""

import sys
import psutil
import os

def main():
    # Find the process
    target_pid = None
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'generate_osm_cache.py' in cmdline and 'grep' not in cmdline:
                target_pid = proc.info['pid']
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not target_pid:
        print("No generate_osm_cache.py process found")
        return 1
    
    print(f"Found process PID: {target_pid}")
    print()
    
    try:
        proc = psutil.Process(target_pid)
        
        # Get process info
        print("Process Information:")
        print(f"  Status: {proc.status()}")
        print(f"  CPU: {proc.cpu_percent(interval=1.0)}%")
        print(f"  Memory: {proc.memory_info().rss / 1024 / 1024:.1f} MB")
        print(f"  Runtime: {(psutil.time.time() - proc.create_time()) / 60:.1f} minutes")
        print()
        
        # Get open files
        print("Open Files:")
        for f in proc.open_files():
            print(f"  {f.path}")
        print()
        
        # Get threads
        print(f"Threads: {proc.num_threads()}")
        print()
        
        # Check if it's doing I/O
        io_counters = proc.io_counters()
        print("I/O Counters:")
        print(f"  Read: {io_counters.read_bytes / 1024 / 1024:.1f} MB")
        print(f"  Write: {io_counters.write_bytes / 1024 / 1024:.1f} MB")
        print()
        
        # Try to get stack trace (requires gdb on Mac)
        print("To get a Python stack trace, run:")
        print(f"  sudo py-bt {target_pid}")
        print()
        print("Or attach with:")
        print(f"  sudo lldb -p {target_pid}")
        print("  Then type: bt")
        
    except psutil.AccessDenied:
        print("Access denied - try running with sudo")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
