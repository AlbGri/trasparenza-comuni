"""
Trasparenza Comuni - Entry point dell'applicazione
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Carica variabili d'ambiente
load_dotenv()

# Inizializza FastAPI
app = FastAPI(
    title="Trasparenza Comuni API",
    description="API per il monitor civico digitale dei comuni italiani",
    version="0.1.0"
)

# Configura CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "message": "Benvenuto in Trasparenza Comuni API",
        "version": "0.1.0",
        "status": "active"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )