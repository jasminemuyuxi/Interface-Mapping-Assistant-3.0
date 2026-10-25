
# Interface Mapping Assistant 3.0 — Coding Agent Instructions

## Project Context

This project is an internal logistics IT Interface Mapping Management PoC.

The application manages mapping relationships across Customer, CJ EDI, OMS, and WMS.

The project must remain independent from Interface Mapping Assistant 2.0.

## Communication

- Explain all development steps to the user in Chinese.
- Assume the user is a logistics IT consultant, not a professional developer.
- Use English for all code comments, docstrings, and technical documentation.
- Explain the purpose and impact of proposed changes.

## Development Workflow

- Work on only ONE development task at a time.
- Inspect relevant existing source files before proposing changes.
- Explain which files will be modified and why.
- Obtain user approval before modifying files.
- Make small, testable changes.
- After each change, provide the exact test command and expected result.
- Wait for user confirmation before proceeding to the next task.
- Never assume a change has passed testing without evidence.

## Technical Stack

- Python
- Streamlit and AG Grid
- PostgreSQL
- SQLAlchemy
- Alembic
- Psycopg
- Anthropic Claude API

## Safety Rules

- Never read, display, copy, commit, or expose secrets from .env files.
- Do not use real customer-sensitive data for testing.
- Do not modify unrelated files.
- Do not perform destructive database operations without explicit approval.
- Do not push code to GitHub without explicit approval.
- Preserve existing application functionality.
- Do not introduce cloud infrastructure without explicit approval.

## Project State

Read docs/PROJECT_STATE.md at the start of each development session.

Treat the project state as a reference, not as proof that code works.

Verify actual source files and test results before making changes.

Distinguish completed and verified work from implemented but untested work.

## Development Handover

Keep code modular and maintainable.

Prefer clear naming conventions and simple implementations.

Document important architectural decisions and testing results.
