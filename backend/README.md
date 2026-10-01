# Metals Tracker – Backend

FastAPI app. Run these from the `backend` folder in PowerShell:

```powershell
uv sync                                   # install dependencies into .venv
uv run alembic upgrade head               # create/update the database tables
uv run uvicorn app.main:app --reload      # start the API on http://localhost:8000
uv run pytest                             # run the tests
```

Interactive API docs: http://localhost:8000/docs

## Updating market data

One command brings exchange rates and spot prices up to date:

```powershell
uv run python -m app.update_data
```

Run it whenever you like (once or twice a month is plenty); each run uses about 1 of
the metals.dev free plan's 100 monthly requests. If one source fails, the other is
still updated. The commands below fetch a single source or a specific date range.

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
