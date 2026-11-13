import sys
from pathlib import Path

# Add project root and backend directory to sys.path for Vercel serverless runtime
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "backend"))

from backend.app.main import app
