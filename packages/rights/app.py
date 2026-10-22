"""Vercel FastAPI entrypoint. Local: RIGHTS_DEV=1 uvicorn app:app."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'service'))
from main import app
