"""Debug: test _within_window with Nemo's actual lastmod."""
import sys
sys.path.insert(0, '.')
from services.source_drilldown import _within_window

lastmod = "2026-07-09"
ws = "2026-07-08"
we = "2026-07-17"
print(f"_within_window({lastmod!r}, {ws!r}, {we!r}) = {_within_window(lastmod, ws, we)}")
