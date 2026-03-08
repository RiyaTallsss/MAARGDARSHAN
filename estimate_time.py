import re
from datetime import datetime

# Read log file
with open('osm_cache_generation.log', 'r') as f:
    lines = f.readlines()

# Find first and last progress lines
progress_lines = [l for l in lines if 'Processed' in l and 'ways' in l]

if len(progress_lines) < 2:
    print("Not enough data yet")
    exit(1)

first = progress_lines[0]
last = progress_lines[-1]

# Parse timestamps and way counts
def parse_line(line):
    timestamp_str = line.split(' - ')[0]
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
    ways = int(re.search(r'Processed ([\d,]+) ways', line).group(1).replace(',', ''))
    return timestamp, ways

first_time, first_ways = parse_line(first)
last_time, last_ways = parse_line(last)

# Calculate rate
elapsed_seconds = (last_time - first_time).total_seconds()
ways_processed = last_ways - first_ways
rate = ways_processed / elapsed_seconds if elapsed_seconds > 0 else 0

print(f"Progress Analysis:")
print(f"  First: {first_ways:,} ways at {first_time.strftime('%H:%M:%S')}")
print(f"  Last:  {last_ways:,} ways at {last_time.strftime('%H:%M:%S')}")
print(f"  Elapsed: {elapsed_seconds:.0f} seconds ({elapsed_seconds/60:.1f} minutes)")
print(f"  Rate: {rate:,.0f} ways/second")
print()

# Estimate total (based on typical OSM PBF files)
# Northern zone likely has 3-4 million ways total
estimated_total_ways = 3500000  # Conservative estimate

remaining_ways = estimated_total_ways - last_ways
remaining_seconds = remaining_ways / rate if rate > 0 else 0
remaining_minutes = remaining_seconds / 60

print(f"Estimation (assuming ~{estimated_total_ways:,} total ways):")
print(f"  Current: {last_ways:,} / {estimated_total_ways:,} ({last_ways/estimated_total_ways*100:.1f}%)")
print(f"  Remaining: {remaining_ways:,} ways")
print(f"  Estimated time remaining: {remaining_minutes:.1f} minutes")
print(f"  Estimated completion: {(last_time.timestamp() + remaining_seconds)}")

# Also show completion percentage
completion_pct = (last_ways / estimated_total_ways) * 100
print(f"\nCompletion: {completion_pct:.1f}%")
