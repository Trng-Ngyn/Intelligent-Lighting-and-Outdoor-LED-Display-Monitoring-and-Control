from pathlib import Path
import time

ready_file = Path("/tmp/w5-ingestion-ready")
if not ready_file.exists():
    raise SystemExit(1)
if time.time() - ready_file.stat().st_mtime > 30:
    raise SystemExit(1)
