"""Compatibility launcher. All production stages use the shared v3 engine.
Run from the repository root: python -m tech_shorts serve
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tech_shorts.web import create_app

app = create_app()

if __name__ == "__main__":
    from tech_shorts.__main__ import main
    sys.argv = [sys.argv[0], "serve", *sys.argv[1:]]
    main()
