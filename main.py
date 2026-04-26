from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from routers.users import router as users_router
from routers.posts import router as posts_router
from routers.auth import router as auth_router
from routers.notifications import router as notify_router
from routers.chats import router as chats_router
import logging
from core.exceptions import AppError

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("app.log", mode="a", encoding="utf-8")
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(formatter)

logger.handlers.clear()
logger.addHandler(console_handler)
logger.addHandler(file_handler)

app = FastAPI()

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.info(f"App logic error: {exc.detail} at {request.url.path}")

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        logger.error(f"HTTP Server Error: {exc.status_code} at {request.url.path}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Critical error at {request.url.path}: {exc}")

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(users_router)
app.include_router(posts_router)
app.include_router(auth_router)
app.include_router(notify_router)
app.include_router(chats_router)
