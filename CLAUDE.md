# CLAUDE.md

**FOR LLM AGENTS DEVELOPING THIS PACKAGE.** This document defines strict rules for modifying the agntrick-whatsapp codebase.

---

## PURPOSE

You are an LLM agent tasked with improving, fixing, or extending the **agntrick-whatsapp** package. This document defines how you MUST approach this work.

---

## STRICT BEHAVIORAL RULES

### ALWAYS Rules

1. **ALWAYS** run `make check` after making any code changes.
2. **ALWAYS** run `make test` after making any code changes.
3. **ALWAYS** fix all linting errors before indicating completion.
4. **ALWAYS** fix all test failures before indicating completion.
5. **ALWAYS** follow existing code patterns in codebase.
6. **ALWAYS** add tests for new functionality.
7. **ALWAYS** update docstrings if you change function behavior.
8. **ALWAYS** use `uv` for package management - **NO EXCEPTIONS**.

### NEVER Rules

1. **NEVER** skip running `make check` and `make test`.
2. **NEVER** commit changes unless explicitly requested by user.
3. **NEVER** push changes without user confirmation.
4. **NEVER** introduce new dependencies without discussion.
5. **NEVER** delete existing tests without replacement.
6. **NEVER** change the public API without updating all affected code.
7. **NEVER** use synchronous code where async is expected.
8. **NEVER** raise exceptions from tools - return error strings instead.
9. **NEVER** use pip, pipenv, poetry, or any package manager other than `uv`.

---

## DEVELOPMENT WORKFLOW

### Step 1: UNDERSTAND
Before making changes:
1. Read relevant source files
2. Read related test files
3. Understand existing patterns

### Step 2: IMPLEMENT
Make your changes:
1. Follow existing code style
2. Add type hints (this project uses strict mypy)
3. Add/update docstrings for public functions
4. Keep functions focused and small

### Step 3: VERIFY
After changes:
```bash
make check    # Linting (mypy + ruff)
make test     # Run all tests
```

### Step 4: FIX
If checks or tests fail:
1. Read the error message carefully
2. Fix the issue
3. Re-run the failing command
4. Repeat until all pass

---

## UV IS MANDATORY

**This project uses `uv` exclusively.** No other package manager is allowed.

### Required Commands

```bash
# Install dependencies
uv sync

# Add a dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Run a command in the virtual environment
uv run <command>
```

---

## CODE STANDARDS

### Type Hints

This project uses strict mypy. All functions MUST have type hints:

```python
# GOOD
async def run(self, input_data: str, config: dict[str, Any] | None = None) -> str:
    ...

# BAD
async def run(self, input_data, config=None):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def process_data(data: list[str]) -> dict[str, int]:
    """Process a list of strings and return counts.

    Args:
        data: A list of strings to process.

    Returns:
        A dictionary mapping each unique string to its count.

    Raises:
        ValueError: If data is empty.
    """
```

### Error Handling

Return error messages as strings, never raise exceptions from tools:

```python
# GOOD
def invoke(self, input_str: str) -> str:
    try:
        result = do_something(input_str)
        return result
    except FileNotFoundError:
        return f"Error: File '{input_str}' not found."
```

---

## TESTING REQUIREMENTS

### Test Location

Tests are in `tests/`

### Test Naming

- Test files: `test_<module>.py`
- Test functions: `test_<function>_<scenario>()`

---

## PROJECT STRUCTURE

```
agntrick-whatsapp/
├── src/agntrick_whatsapp/
│   ├── __init__.py           # Package exports
│   ├── base.py               # Channel ABC and message types
│   ├── channel.py            # WhatsApp channel implementation
│   ├── commands.py           # Command parsing
│   ├── config.py             # Pydantic configuration models
│   ├── router.py             # WhatsAppRouterAgent
│   ├── transcriber.py        # Audio transcription
│   └── storage/
│       ├── __init__.py       # Storage exports
│       ├── database.py       # SQLite database setup
│       ├── models.py         # Data models
│       ├── scheduler.py      # Time parsing utilities
│       └── repositories/
│           ├── __init__.py
│           ├── note_repository.py
│           └── task_repository.py
├── tests/                    # Test suite
├── pyproject.toml            # Project config, dependencies
└── Makefile                  # Development commands
```

---

## COMMANDS REFERENCE

```bash
# From project root:
make check      # Run mypy + ruff (linting)
make test       # Run pytest with coverage
make format     # Auto-format with ruff
make install    # Install dependencies
make clean      # Remove caches and artifacts
make build      # Build wheel and sdist
make release    # Release new version (VERSION=x.y.z required)
```

---

## WHEN IN DOUBT

1. Read existing code for patterns
2. Run `make check` early and often
3. Ask user for clarification
4. Don't guess - verify