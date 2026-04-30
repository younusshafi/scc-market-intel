"""
Local tender probe runner.

Usage (from backend/ directory):
    python -m app.jobs.probe_tenders

Connects to the Render Postgres database using DATABASE_URL from .env
(looks in both backend/ and project root). Prints progress to stdout.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path


def _load_env():
    """Load .env from backend/ or project root, whichever has DATABASE_URL."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        # pydantic-settings handles .env too, but we want early loading
        pass
    else:
        # Try backend/.env first, then project root .env
        backend_dir = Path(__file__).resolve().parent.parent.parent
        for env_path in [backend_dir / ".env", backend_dir.parent / ".env"]:
            if env_path.exists():
                load_dotenv(env_path, override=False)

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL not set.")
        print()
        print("Add it to backend/.env:")
        print("  DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        print()
        print("You can find it in Render dashboard -> your PostgreSQL -> External Database URL")
        sys.exit(1)


def run_probe_job():
    """Execute the tender probe pipeline against the remote database."""
    from app.core.database import SessionLocal
    from app.scrapers.tender_probe import run_tender_probe

    db = SessionLocal()
    try:
        result = run_tender_probe(db)
        return result
    finally:
        db.close()


if __name__ == "__main__":
    # Load env before importing app modules (they read settings at import time)
    _load_env()

    # Configure logging to stdout with verbose output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # Quiet down noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    start = datetime.now()
    print("=" * 70)
    print("  SCC Tender Probe — Local Runner")
    print(f"  Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database: {os.environ.get('DATABASE_URL', '?')[:50]}...")
    print("=" * 70)
    print()

    try:
        result = run_probe_job()
        elapsed = (datetime.now() - start).total_seconds()
        print()
        print("=" * 70)
        print(f"  COMPLETE — {elapsed:.0f}s")
        print("=" * 70)
        for k, v in result.items():
            print(f"  {k}: {v}")
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds()
        print()
        print("=" * 70)
        print(f"  FAILED after {elapsed:.0f}s — {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
