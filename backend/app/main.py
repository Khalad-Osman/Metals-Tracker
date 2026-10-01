from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import exchange_rates, portfolio, prices, purchases

app = FastAPI(title="Metals Tracker API")

# Allow the Vite dev server (React frontend) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple endpoint to confirm the API is running."""
    return {"status": "ok"}


app.include_router(purchases.router)
app.include_router(prices.router)
app.include_router(exchange_rates.router)
app.include_router(portfolio.router)
