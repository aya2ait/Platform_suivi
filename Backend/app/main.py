from fastapi import FastAPI
from app.api.endpoints import missions # Import the missions router

# ====================================================================
# FastAPI Application
# ====================================================================

app = FastAPI(
    title="ONEE Suivi Deplacements API",
    description="API pour la gestion des missions et des déplacements des collaborateurs ONEE.",
    version="1.0.0"
)

# Include the missions router
app.include_router(missions.router)

# You can add other routers here as your application grows, e.g.:
# from app.api.endpoints import users
# app.include_router(users.router)

# You can also add root endpoints or general application logic here
@app.get("/")
async def root():
    return {"message": "Welcome to ONEE Suivi Deplacements API!"}