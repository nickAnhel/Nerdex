from fastapi import FastAPI

from src.admin.admin import create_admin
from src.config import settings
from src.setup_app import setup_app


app = FastAPI(
    title=settings.project.title,
    version=settings.project.version,
    description=settings.project.description,
    debug=settings.project.debug,
    openapi_url="/openapi.json",
    docs_url="/docs",
)

admin = create_admin(app)

setup_app(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", reload=True)
