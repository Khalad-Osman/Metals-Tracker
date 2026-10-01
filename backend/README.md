# Metals Tracker – Backend

FastAPI app. Run these from the `backend` folder in PowerShell:

```powershell
uv sync                                   # install dependencies into .venv
uv run uvicorn app.main:app --reload      # start the API on http://localhost:8000
uv run pytest                             # run the tests
```

Interactive API docs: http://localhost:8000/docs
