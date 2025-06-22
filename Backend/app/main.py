from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import missions

app = FastAPI(
    title="ONEE Suivi Deplacements API",
    description="API pour la gestion des missions et des déplacements des collaborateurs ONEE.",
    version="1.0.0"
)

# ✅ Ajoute ce bloc IMPORTANT :
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # ton frontend React (vite.js)
    allow_credentials=True,
    allow_methods=["*"],  # autorise toutes les méthodes: GET, POST, etc.
    allow_headers=["*"],  # autorise tous les headers comme Content-Type, Authorization
)

# Ensuite tu peux inclure ton routeur :
app.include_router(missions.router)

@app.get("/")
async def root():
    return {"message": "Welcome to ONEE Suivi Deplacements API!"}
