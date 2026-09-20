"""Step 0: check Python, packages, settings and folders.

Run:  python 00_check_setup.py
"""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
problems = 0


def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg):
    global problems
    problems += 1
    print(f"  [FIX]  {msg}")


def note(msg):
    print(f"  [NOTE] {msg}")


print("\n1) Python version")
if sys.version_info >= (3, 9):
    ok(f"Python {sys.version.split()[0]}")
else:
    bad(f"Python {sys.version.split()[0]} is too old. Install Python 3.9 or newer.")

print("\n2) Packages")
for module, pip_name in [("pandas", "pandas"), ("matplotlib", "matplotlib"),
                         ("requests", "requests"), ("dotenv", "python-dotenv"),
                         ("pytest", "pytest")]:
    try:
        mod = importlib.import_module(module)
        ok(f"{pip_name} {getattr(mod, '__version__', '')}".strip())
    except ImportError:
        bad(f"{pip_name} is missing. Run:  python -m pip install -r requirements.txt")

print("\n3) Virtual environment")
if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
    ok(f"Running inside a virtual environment ({sys.prefix})")
else:
    note("Not inside a virtual environment. It works, but activating .venv is recommended.")

print("\n4) Settings file (.env)")
env_path = ROOT / ".env"
if not env_path.exists():
    bad("No .env file. Copy .env.example to .env and fill it in.")
else:
    ok(".env found")
    try:
        from dotenv import dotenv_values

        values = dotenv_values(env_path)
        agent = (values.get("SEC_USER_AGENT") or "").strip()
        if not agent or "@" not in agent:
            bad("SEC_USER_AGENT must be your name and email, e.g. "
                "'Tayo Ortiz you@example.com'. The SEC rejects requests without it.")
        else:
            ok("SEC_USER_AGENT is set (name and email present)")
        key = (values.get("ALPHAVANTAGE_API_KEY") or "").strip()
        if not key or key.lower().startswith("paste"):
            note("No Alpha Vantage key. Prices come from data/prices_manual.csv, "
                 "and valuation ratios stay blank without it.")
        else:
            ok(f"ALPHAVANTAGE_API_KEY is set (ends in ...{key[-4:]})")
            note("The free tier allows 25 requests a day. Prices are cached daily.")
    except ImportError:
        note("Install python-dotenv to check the .env contents.")

print("\n5) Manual price file")
prices = ROOT / "data" / "prices_manual.csv"
if prices.exists():
    try:
        import pandas as pd

        frame = pd.read_csv(prices)
        filled = frame.dropna(subset=["price"]) if "price" in frame else frame.iloc[0:0]
        ok(f"data/prices_manual.csv has {len(filled)} price(s) filled in")
    except Exception as exc:
        bad(f"Could not read data/prices_manual.csv: {exc}")
else:
    note("No data/prices_manual.csv. Create it to type prices in by hand.")

print("\n6) Cached filings")
cache = ROOT / "data" / "cache"
files = sorted(cache.glob("facts_*.json")) if cache.exists() else []
if files:
    demo = (cache / "_DEMO_DATA_DO_NOT_TRUST.txt").exists()
    names = ", ".join(f.stem.replace("facts_", "") for f in files)
    ok(f"{len(files)} company file(s): {names}" + (" - DEMO (invented)" if demo else ""))
else:
    note("Nothing fetched yet. Run:  python 01_fetch_company.py TICKER")

print("\n7) .gitignore")
gi = ROOT / ".gitignore"
if gi.exists() and ".env" in gi.read_text(encoding="utf-8"):
    ok(".gitignore excludes .env, data/cache and output")
else:
    bad(".gitignore is missing or does not exclude .env. Fix before using git.")

print()
if problems:
    print(f"RESULT: {problems} thing(s) to fix above.")
    sys.exit(1)
print("RESULT: Setup looks good.")
