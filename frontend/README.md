# Metals Tracker – Frontend

React + TypeScript app built with Vite. Run these from the `frontend` folder in PowerShell:

```powershell
npm install        # install dependencies (first time only)
npm run dev        # start the dev server on http://localhost:5173
npm run build      # type-check and build for production
npm run lint       # check the code with oxlint
```

Start the backend too (see `../backend/README.md`) so the page can reach the API.

The app calls the API at `http://localhost:8000` by default. To point it elsewhere (for
example when deploying), set `VITE_API_URL` when building:

```powershell
$env:VITE_API_URL = "https://your-api.example.com"; npm run build
```
