from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.routers import exchange_rates, portfolio, prices, purchases

app = FastAPI(title="Metals Tracker API")

# Allow the frontend to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple endpoint to confirm the API is running."""
    return {"status": "ok"}


@app.get("/settings")
def get_settings() -> dict[str, str]:
    """Settings the frontend needs: demo_mode is "off", "readonly" or "sandbox"."""
    return {"demo_mode": config.DEMO_MODE}


app.include_router(purchases.router)
app.include_router(prices.router)
app.include_router(exchange_rates.router)
app.include_router(portfolio.router)
