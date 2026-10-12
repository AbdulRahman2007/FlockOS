# POUKTRY

POUKTRY is a multi-tenant poultry farm management platform for farms in Pakistan, connecting flock operations, daily records, calculations, dashboards, and reports.

## Local development

Prerequisites: Python 3.12, Node.js 22 with npm, and Docker Desktop with Compose. Run these commands from the repository root in PowerShell.

~~~powershell
Copy-Item .env.example .env
docker compose up -d --wait postgres
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
~~~

Start the API in one terminal:

~~~powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
~~~

Start the frontend in a second terminal:

~~~powershell
npm.cmd ci --prefix frontend
npm.cmd run dev --prefix frontend
~~~

Open http://localhost:5173. API liveness is at http://localhost:8000/health; readiness checks PostgreSQL at http://localhost:8000/ready. OpenAPI documentation is at http://localhost:8000/docs.

The .env.example file contains local-only placeholder credentials. Replace them in your ignored .env before using a shared machine, never put production secrets or real farm data in this development setup, and do not commit .env.

## Quality checks

~~~powershell
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
Push-Location backend
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest
Pop-Location
npm.cmd ci --prefix frontend
npm.cmd run lint --prefix frontend
npm.cmd run format:check --prefix frontend
npm.cmd run typecheck --prefix frontend
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
~~~

For browser tests, install Playwright's Chromium headless shell once with npm.cmd exec --prefix frontend -- playwright install --only-shell chromium, then run npm.cmd run e2e --prefix frontend.

## Current foundation

This phase establishes configuration, health/readiness, migration tooling, CI, test harnesses, localization scaffolding, and a responsive route-split app shell. The first Alembic migration is an intentionally empty schema baseline; business tables and workflows follow their approved vertical slices.
