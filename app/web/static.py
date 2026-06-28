from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


STATIC_DIR = Path(__file__).parent / "static"


def mount_static(app: FastAPI) -> None:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
