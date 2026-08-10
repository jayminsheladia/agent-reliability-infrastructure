import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.approvals import queue as approval_queue
from app.db import get_db
from app.trace.service import get_trace

app = FastAPI(title="Agent Reliability Infrastructure")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/trace/{run_id}", response_class=HTMLResponse)
def trace_view(request: Request, run_id: str, db: Session = Depends(get_db)):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid run_id: {run_id!r} is not a valid UUID")

    steps = get_trace(db, run_uuid)

    return templates.TemplateResponse(
        request, "trace.html", {"run_id": run_id, "steps": steps}
    )


@app.get("/approvals")
def list_approvals() -> list[dict]:
    return [asdict(a) for a in approval_queue.list_pending()]


@app.post("/approvals/{approval_id}/approve")
def approve(approval_id: str) -> dict:
    approval = approval_queue.resolve_approval(approval_id, "approved")
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    return asdict(approval)


@app.post("/approvals/{approval_id}/reject")
def reject(approval_id: str) -> dict:
    approval = approval_queue.resolve_approval(approval_id, "rejected")
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    return asdict(approval)


@app.get("/approvals/ui", response_class=HTMLResponse)
def approvals_ui(request: Request):
    approvals = approval_queue.list_pending()
    return templates.TemplateResponse(request, "approvals.html", {"approvals": approvals})
