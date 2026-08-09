# Su-AI API Testing & CI/CD Setup

[![Backend CI](https://github.com/merveAiseoglu/su-ai-scada-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/merveAiseoglu/su-ai-scada-platform/actions/workflows/ci.yml)

The backend uses `pytest` for testing and `ruff` for linting. We enforce a 90% test coverage minimum on the critical rule engine module.

## Setup Instructions

### 1. Install Testing Dependencies
Ensure you are in the `backend` directory and your virtual environment is active.
```bash
pip install -r requirements-test.txt
```

### 2. Running Tests Locally
We use an in-memory SQLite database for fast local tests.
```bash
pytest --cov=app.engine --cov-fail-under=90 tests/
```

### 3. Running Linters
We use `ruff` to keep the code fast and clean.
```bash
ruff check app
ruff format app
```

### 4. Pre-commit hooks
To automatically format code before commits:
```bash
pre-commit install
```
