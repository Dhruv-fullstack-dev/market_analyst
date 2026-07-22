"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Market Analyst API starting up")
    yield
    logger.info("Market Analyst API shutting down")


app = FastAPI(title="Market Analyst API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
