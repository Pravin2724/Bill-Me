"""
setup_templates.py
──────────────────
Run this ONCE before starting the app to verify the templates directory
is correctly set up and all dependencies are installed.

Usage:
    python setup_templates.py
Then start the app:
    python app.py
"""

import os
import sys

# ── Check template file exists ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
INDEX_FILE = os.path.join(TEMPLATES_DIR, "index.html")

print("=" * 55)
print("  Bill Me — Setup Checker")
print("=" * 55)

# Templates
if os.path.isdir(TEMPLATES_DIR):
    print(f"[✓] templates/ directory found at: {TEMPLATES_DIR}")
else:
    print(f"[✗] templates/ directory NOT found — creating it...")
    os.makedirs(TEMPLATES_DIR)
    print(f"[✓] Created: {TEMPLATES_DIR}")

if os.path.isfile(INDEX_FILE):
    print(f"[✓] index.html found")
else:
    print(f"[✗] index.html NOT found at {INDEX_FILE}")
    print("    Make sure templates/index.html exists before starting the app.")

# ── Check Python packages ───────────────────────────────────────────────────
print("\n── Checking dependencies ──")
packages = {
    "flask": "Flask",
    "pymongo": "PyMongo",
    "reportlab": "ReportLab",
}

missing = []
for module, display in packages.items():
    try:
        __import__(module)
        print(f"[✓] {display}")
    except ImportError:
        print(f"[✗] {display} — NOT installed")
        missing.append(module)

if missing:
    print(f"\n[!] Missing packages: {', '.join(missing)}")
    print("    Run:  pip install " + " ".join(missing))
    sys.exit(1)

# ── Check MongoDB ────────────────────────────────────────────────────────────
print("\n── Checking MongoDB connection ──")
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure
    c = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    c.admin.command("ping")
    print("[✓] MongoDB is running on localhost:27017")
    c.close()
except Exception as e:
    print(f"[!] MongoDB not reachable: {e}")
    print("    Make sure MongoDB is running:  sudo systemctl start mongod")

# ── Done ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("  All checks done.")
print("  Start the server with:  python app.py")
print("  Then open:  http://127.0.0.1:5000")
print("=" * 55)
