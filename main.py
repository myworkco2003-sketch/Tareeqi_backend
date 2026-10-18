from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as admin_routes_router
from app.api.tiles import router as tiles_router
from app.api.sync import router as sync_router

app = FastAPI(title="TareeqI Backend")
app.mount(
    "/profiles2",
    StaticFiles(directory=r"D:\BrouterWeb\profiles2"),
    name="profiles2",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_routes_router)
app.include_router(tiles_router)
app.include_router(sync_router)