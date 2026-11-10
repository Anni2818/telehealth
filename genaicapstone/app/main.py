from fastapi import FastAPI

from app.routes.chat import router as chat_router
from app.routes.sessions import router as sessions_router
from app.routes.appointments import router as appointments_router
from app.routes.actions import router as actions_router
from app.routes.auth import router as auth_router
from app.routes.workflow import router as workflow_router
from app.routes.pending_actions import (
    router as pending_actions_router,
)


app = FastAPI(
    title="GenAI Capstone API",
    description="Synthetic appointment navigation backend",
    version="0.1.0",
)

app.include_router(appointments_router)
app.include_router(sessions_router)
app.include_router(actions_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(pending_actions_router)
app.include_router(workflow_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}