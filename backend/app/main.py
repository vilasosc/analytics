from fastapi import FastAPI
from app.core.config import settings
from app.core.database import create_db_and_tables # Depends on database.py
# Import all model modules that define tables inheriting from Base
# so that create_db_and_tables knows about them.
import app.models.user
import app.models.datasource
import app.models.metadata # Ensure metadata models are loaded
from app.routers import auth as auth_router
from app.routers import datasource_router
from app.routers import metadata as metadata_router # Import the new router

app = FastAPI(title=settings.APP_NAME)

@app.on_event("startup")
def on_startup():
    # No need to pass Base explicitly, it's used by create_all within the function
    create_db_and_tables()

@app.get("/health", summary="Health Check", tags=["Health"])
async def health_check():
    return {"status": "healthy"}

app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
app.include_router(datasource_router.router, prefix=f"{settings.API_V1_STR}/datasources", tags=["Data Sources"])
app.include_router(metadata_router.router, prefix=f"{settings.API_V1_STR}/metadata", tags=["Metadata"])


# Placeholder for other API routers (will be added in later steps)
# from app.routers import user_router # Example
# app.include_router(user_router, prefix=settings.API_V1_STR, tags=["users"]) # Example
