#!/usr/bin/env python3
"""Detect changed slide sections between old and new .md files.

Usage: python3 detect_changed_slides.py <old_file> <new_file>
Output: space-separated list of changed slide numbers (empty if none)
"""
import re, sys

def slide_ranges(text):
    """Return {slide_num: (start, end)} for each ## Slide N section."""
    boundaries = []
    for m in re.finditer(r'^## Slide (\d+)', text, re.MULTILINE):
        boundaries.append((int(m.group(1)), m.start()))
    ranges = {}
    for i, (num, start) in enumerate(boundaries):
        end = boundaries[i+1][1] if i+1 < len(boundaries) else len(text)
        ranges[num] = (start, end)
    return ranges

if len(sys.argv) != 3:
    print("unknown", file=sys.stderr)
    sys.exit(1)

old_path, new_path = sys.argv[1], sys.argv[2]
old = open(old_path, 'r', encoding='utf-8').read() if __import__('os').path.exists(old_path) else ''
new = open(new_path, 'r', encoding='utf-8').read()

old_ranges = slide_ranges(old)
new_ranges = slide_ranges(new)

changed = set()
for num, (ns, ne) in new_ranges.items():
    if num not in old_ranges:
        changed.add(num)
    else:
        os_, oe_ = old_ranges[num]
        if new[ns:ne].strip() != old[os_:oe_].strip():
            changed.add(num)

# Deleted slides also need cleanup (rendered HTML will be orphaned)
deleted = set(old_ranges.keys()) - set(new_ranges.keys())
# Include deleted slides as "changed" so they get cleaned up
changed.update(deleted)

print(' '.join(str(s) for s in sorted(changed)))
