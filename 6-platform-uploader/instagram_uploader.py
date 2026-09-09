"""v3 adapter export. Use the Studio for approval and durable upload state."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tech_shorts.publishers import Instagram as InstagramUploader

if __name__ == "__main__":
    raise SystemExit("Run python -m tech_shorts serve from the repository root.")
