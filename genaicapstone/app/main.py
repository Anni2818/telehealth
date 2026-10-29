from fastapi import FastAPI

from app.routes.sessions import router as sessions_router
from app.routes.appointments import router as appointments_router


app = FastAPI(
    title="GenAI Capstone API",
    description="Synthetic appointment navigation backend",
    version="0.1.0",
)

app.include_router(appointments_router)
app.include_router(sessions_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}