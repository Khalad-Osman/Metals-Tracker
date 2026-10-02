# Metals Tracker – Backend

FastAPI app. Run these from the `backend` folder in PowerShell:

```powershell
uv sync                                   # install dependencies into .venv
uv run alembic upgrade head               # create/update the database tables
uv run uvicorn app.main:app --reload      # start the API on http://localhost:8000
uv run pytest                             # run the tests
```

Interactive API docs: http://localhost:8000/docs

## Database

The app uses whatever `DATABASE_URL` is set to in `backend/.env`. Without it, it falls
back to a SQLite file (`backend/metals.db`), which is handy for a quick start.

### PostgreSQL (recommended, and what deployment uses)

PostgreSQL runs in Docker. From the project folder (one level up from `backend`):

```powershell
copy .env.example .env      # then set POSTGRES_PASSWORD in .env
docker compose up -d        # start PostgreSQL 17 on 127.0.0.1:5432
```

Then add this line to `backend/.env`, using the same password, and create the tables:

```
DATABASE_URL=postgresql+psycopg://metals:<password>@127.0.0.1:5432/metals
```

```powershell
uv run alembic upgrade head
```

Docker Desktop must be running whenever the app or the weekly update runs. The database
container starts again automatically with Docker; to start Docker itself when you sign
in, turn on "Start Docker Desktop when you sign in" in its settings.

To copy existing data from SQLite into an empty PostgreSQL database (after creating its tables):

```powershell
uv run python -m app.copy_database --source sqlite:///metals.db
```

### Running the tests against PostgreSQL

Tests use an in-memory SQLite database by default. To run them against PostgreSQL, point
`TEST_DATABASE_URL` at an empty database used only for tests (never the real one):

```powershell
docker compose exec db psql -U metals -c "CREATE DATABASE metals_test;"   # once
$env:TEST_DATABASE_URL = "postgresql+psycopg://metals:<password>@127.0.0.1:5432/metals_test"
uv run pytest
```

## Updating market data

One command brings exchange rates and spot prices up to date:

```powershell
uv run python -m app.update_data
```

Run it whenever you like (once or twice a month is plenty); each run uses about 1 of
the metals.dev free plan's 100 monthly requests. If one source fails, the other is
still updated. The commands below fetch a single source or a specific date range.

### Automatic weekly updates (Windows)

A scheduled task can run the update every Monday at 9:00 AM (or as soon as the computer
is next on). Set it up once, from the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\register_update_task.ps1
```

Each run's output is appended to `backend\logs\update_data.log`. To change the day or
time, edit the trigger in `register_update_task.ps1` and run it again. To remove the task:

```powershell
Unregister-ScheduledTask -TaskName "Metals Tracker - update data" -Confirm:$false
```

## Spot prices

Daily prices come from metals.dev. Copy `.env.example` to `.env` and add your
`METALS_DEV_API_KEY`, then:

```powershell
uv run python -m app.fetch_prices                       # download any missing days up to today
uv run python -m app.fetch_prices --start 2026-07-10    # download from a given date
```

Each request returns all four metals for up to 30 days, so a monthly run uses about
1 of the free plan's 100 requests a month.

## Exchange rates

Daily USD to CAD rates come from the Bank of Canada (free, no API key needed):

```powershell
uv run python -m app.fetch_rates                        # download any missing days up to today
uv run python -m app.fetch_rates --start 2026-07-10     # download from a given date
```

Rates are only published on Canadian business days, so weekends and holidays have none.

## Changing the database (Alembic migrations)

After changing a model in `app/models.py`:

```powershell
uv run alembic revision --autogenerate -m "describe the change"   # write a migration
uv run alembic upgrade head                                       # apply it
```

Read the new file in `migrations/versions/` before applying it, and commit it with the model change.
Other useful commands: `uv run alembic current` (which migration the database is on),
`uv run alembic downgrade -1` (undo the last migration).
