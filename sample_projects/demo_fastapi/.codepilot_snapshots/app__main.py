"""Demo FastAPI application used to exercise CodePilot AI."""

from fastapi import FastAPI

from app.routes.items import router as items_router

app = FastAPI(title="Demo Shop")
app.include_router(items_router)
