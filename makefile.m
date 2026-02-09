# Makefile (SERVUS)
# Usage examples:
#   make help
#   make venv
#   make install
#   make fmt
#   make lint
#   make test
#   make run
#   make dry-run
#   make adr TITLE="Offboarding execution promotion gate" STATUS=Accepted

SHELL := /bin/bash
PY ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYBIN := $(VENV)/bin/python

# Default goal
.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "SERVUS Makefile targets:"
	@echo ""
	@echo "  make venv        Create virtualenv in $(VENV)"
	@echo "  make install     Install deps from requirements.txt"
	@echo "  make upgrade     Upgrade pip/setuptools/wheel"
	@echo "  make fmt         Format code (black + isort if installed)"
	@echo "  make lint        Run lint checks (ruff/flake8 if installed)"
	@echo "  make test        Run tests (pytest if installed)"
	@echo "  make run         Run SERVUS package entrypoint"
	@echo "  make scheduler   Run scheduler loop"
	@echo "  make dry-run     Run dry-run new hire flow"
	@echo "  make adr         Create a new ADR: make adr TITLE=\"...\" [STATUS=Proposed|Accepted]"
	@echo "  make clean       Remove caches and temp files"
	@echo ""
	@echo "Notes:"
	@echo "  - Targets auto-use $(VENV) if it exists."
	@echo "  - If a tool (ruff/black/pytest) isn't installed, the target will explain what to do."

# --- Environment -------------------------------------------------------------

.PHONY: venv
venv:
	@$(PY) -m venv $(VENV)
	@$(PIP) install --upgrade pip setuptools wheel
	@echo "Created venv at $(VENV). Activate with: source $(VENV)/bin/activate"

.PHONY: upgrade
upgrade: venv
	@$(PIP) install --upgrade pip setuptools wheel

.PHONY: install
install: venv
	@if [ ! -f requirements.txt ]; then \
		echo "ERROR: requirements.txt not found"; exit 2; \
	fi
	@$(PIP) install -r requirements.txt
	@echo "Installed dependencies."

# --- Formatting / Linting / Testing -----------------------------------------

.PHONY: fmt
fmt: venv
	@set -e; \
	if $(PIP) show black >/dev/null 2>&1; then \
		$(VENV)/bin/black servus scripts; \
	else \
		echo "black not installed. Install with: $(PIP) install black"; \
	fi; \
	if $(PIP) show isort >/dev/null 2>&1; then \
		$(VENV)/bin/isort servus scripts; \
	else \
		echo "isort not installed. Install with: $(PIP) install isort"; \
	fi

.PHONY: lint
lint: venv
	@set -e; \
	if $(PIP) show ruff >/dev/null 2>&1; then \
		$(VENV)/bin/ruff check servus scripts; \
	elif $(PIP) show flake8 >/dev/null 2>&1; then \
		$(VENV)/bin/flake8 servus scripts; \
	else \
		echo "No linter installed (ruff or flake8)."; \
		echo "Install ruff with: $(PIP) install ruff"; \
		exit 2; \
	fi

.PHONY: test
test: venv
	@set -e; \
	if $(PIP) show pytest >/dev/null 2>&1; then \
		$(VENV)/bin/pytest -q; \
	else \
		echo "pytest not installed. Install with: $(PIP) install pytest"; \
		exit 2; \
	fi

# --- Running ----------------------------------------------------------------

.PHONY: run
run: venv
	@$(PYBIN) -m servus

.PHONY: scheduler
scheduler: venv
	@$(PYBIN) scripts/scheduler.py

.PHONY: dry-run
dry-run: venv
	@$(PYBIN) scripts/dry_run_new_hires.py

# --- ADR helper --------------------------------------------------------------

.PHONY: adr
adr:
	@if [ -z "$(TITLE)" ]; then \
		echo "Usage: make adr TITLE=\"My ADR Title\" [STATUS=Proposed|Accepted|Deprecated|Superseded]"; \
		exit 2; \
	fi
	@$(PY) scripts/new_adr.py --title "$(TITLE)" --status "$(or $(STATUS),Proposed)"

# --- Cleanup -----------------------------------------------------------------

.PHONY: clean
clean:
	@rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache
	@find servus scripts -name "__pycache__" -type d -prune -exec rm -rf {} +
	@find servus scripts -name "*.pyc" -type f -delete
	@echo "Cleaned caches."