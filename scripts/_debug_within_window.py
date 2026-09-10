"""Debug: isolate why _within_window returns False."""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone

date_str = "2026-07-10T12:00:00Z"
window_start = "2026-07-08"
window_end   = "2026-07-17"

raw = date_str.strip()
fmt = "%Y-%m-%dT%H:%M:%SZ"
print(f"raw={raw!r}, len(fmt)={len(fmt)}, raw[:len(fmt)]={raw[:len(fmt)]!r}")

try:
    parsed = datetime.strptime(raw[:len(fmt)], fmt)
    print(f"parsed ok: {parsed}")
except Exception as e:
    print(f"parse failed: {e}")

# Check bound parsing
for s in (window_start, window_end):
    fmt2 = "%Y-%m-%d"
    try:
        d = datetime.strptime(s[:len(fmt2)], fmt2)
        d = d.replace(tzinfo=timezone.utc)
        print(f"bound {s!r} => {d}")
    except Exception as e:
        print(f"bound parse failed for {s!r}: {e}")
