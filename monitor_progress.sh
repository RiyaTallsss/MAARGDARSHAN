#!/bin/bash
# Monitor OSM cache generation progress

echo "Monitoring OSM cache generation..."
echo "Press Ctrl+C to stop monitoring"
echo ""

while true; do
    clear
    echo "============================================"
    echo "OSM Cache Generation Progress Monitor"
    echo "============================================"
    echo ""
    
    # Show running processes
    echo "Running Processes:"
    ps aux | grep generate_osm_cache | grep -v grep | awk '{printf "  PID: %s | CPU: %s%% | MEM: %s%% | Runtime: %s\n", $2, $3, $4, $10}'
    echo ""
    
    # Show memory usage
    echo "Memory Usage:"
    ps aux | grep generate_osm_cache | grep -v grep | awk '{sum+=$4} END {printf "  Total: %.1f%% of system RAM\n", sum}'
    echo ""
    
    # Check for output files
    echo "Output Files:"
    if ls /tmp/tmp*.json.gz 2>/dev/null | head -1 > /dev/null; then
        ls -lh /tmp/tmp*.json.gz 2>/dev/null | awk '{printf "  %s (%s)\n", $9, $5}'
    else
        echo "  No cache files created yet (still parsing...)"
    fi
    echo ""
    
    # Estimate
    echo "Estimate:"
    oldest_runtime=$(ps aux | grep generate_osm_cache | grep -v grep | awk '{print $10}' | sort -r | head -1)
    echo "  Oldest process runtime: $oldest_runtime"
    echo "  Expected total time: 20-30 minutes"
    echo "  Likely remaining: 5-10 minutes"
    echo ""
    
    echo "Refreshing in 10 seconds..."
    sleep 10
done
