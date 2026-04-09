#!/usr/bin/env bash
# setup.sh — Environment setup for provenance-ra-evaluator benchmarks
set -euo pipefail

# ── Check Python version ──────────────────────────────────────────────
PYTHON=""
for candidate in python3.12 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python not found. Please install Python 3.12 or higher."
    exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

if (( PY_MAJOR < 3 )) || (( PY_MAJOR == 3 && PY_MINOR < 12 )); then
    echo "ERROR: Python 3.12+ required, but found Python $PY_VERSION."
    echo "       Install Python 3.12 or newer and try again."
    exit 1
fi

echo "Using $PYTHON (version $PY_VERSION)"

# ── Create virtual environment ────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/../venv"

if [[ -d "$VENV_DIR" ]]; then
    echo "Virtual environment already exists at $VENV_DIR"
else
    echo "Creating virtual environment at $VENV_DIR ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# ── Activate and install dependencies ─────────────────────────────────
source "$VENV_DIR/bin/activate"

echo "Upgrading pip ..."
pip install --upgrade pip --quiet

if [[ -f "$SCRIPT_DIR/../requirements.txt" ]]; then
    echo "Installing packages from requirements.txt ..."
    pip install -r "$SCRIPT_DIR/../requirements.txt" --quiet
else
    echo "No requirements.txt found — installing minimal dependencies ..."
    pip install pytest duckdb matplotlib --quiet
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate the environment:  source venv/bin/activate"
echo "  2. Generate TPC-H data:       python benchmark/generate_tpch_data.py --sf 0.01"
echo "  3. Run benchmarks:            bash benchmark/run_all_benchmarks.sh"
