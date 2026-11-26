from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from backend.core.schemas import TrainingRequest, JobResponse, JobStatusResponse
from backend.core.router import interpret_intent
from backend.db.database import engine, Base, get_db
from backend.db.models import Job
from backend.workers.tasks import run_auto_train_pipeline, run_manual_train_pipeline
from backend.api import lab_router, llm_studio_router, chat_router, skills_router, voice_router, memory_router, daemon_router
from backend.core.paths import FRONTEND_DIR
import os
import shutil
from uuid import uuid4

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Unleash-Agent API")

_raw_cors = os.getenv(
    "UNLEASH_CORS_ORIGINS",
    "http://127.0.0.1:8001,http://localhost:8001,http://127.0.0.1:8000,http://localhost:8000"
)
_allowed_origins = [o.strip() for o in _raw_cors.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def optional_api_token_auth(request: Request, call_next):
    """Enforces Bearer / X-API-Key authentication on /api/* when UNLEASH_API_TOKEN is configured."""
    expected_token = os.getenv("UNLEASH_API_TOKEN", "").strip()
    if expected_token and request.url.path.startswith("/api/"):
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")
        bearer = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
        if bearer != expected_token and api_key != expected_token:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized: invalid or missing API token."})
    return await call_next(request)

app.include_router(lab_router.router)
app.include_router(llm_studio_router.router, prefix="/api")
app.include_router(chat_router.router, prefix="/api/chat")
app.include_router(skills_router.router)
app.include_router(voice_router.router, prefix="/api/voice")
app.include_router(memory_router.router, prefix="/api/memory")
app.include_router(daemon_router.router)


@app.get("/api/system/telemetry")
def get_system_telemetry_top_level():
    """Returns verified real-time workstation hardware telemetry in < 1ms."""
    from backend.core.workstation_sensors import get_full_workstation_telemetry
    return get_full_workstation_telemetry()


@app.on_event("startup")
def startup_event():
    """Background startup warm-up: launches Docker & Ollama supervisors, and starts proactive watchdog."""
    import threading
    from backend.core.sandbox import ensure_docker_daemon_async
    threading.Thread(target=ensure_docker_daemon_async, daemon=True).start()

    from backend.api.chat_router import ensure_ollama_daemon
    threading.Thread(target=ensure_ollama_daemon, daemon=True).start()

    from backend.core.task_daemon import start_proactive_watchdog_loop
    start_proactive_watchdog_loop(interval_sec=120)

    try:
        from backend.core.memory_pilot import prewarm_local_embedder
        threading.Thread(target=prewarm_local_embedder, daemon=True, name="MemoryEmbedderWarmup").start()
    except Exception:
        pass

    try:
        from backend.core.voice_pilot import load_voice_config
        v_cfg = load_voice_config()
        if v_cfg.get("wake_word_enabled", False):
            from backend.core.wake_word_listener import start_native_wake_word_daemon
            start_native_wake_word_daemon(in_background=True)
    except Exception as e:
        print(f"[Startup Warning] Native Wake-Word Daemon startup notice: {e}")


@app.get("/debug/gemini")
def debug_gemini():
    from backend.core.gemini_client import _call_gemini, gemini_available
    from backend.core.config import settings
    try:
        if not gemini_available():
            return {"status": "error", "message": "gemini_available() is False. API Key missing?", "key_starts_with": str(settings.GEMINI_API_KEY)[:5]}
        
        # Test a raw call
        res = _call_gemini("Say 'hello world'")
        return {"status": "success", "response": res}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}


def _use_local_background_fallback() -> bool:
    # Always use FastAPI background tasks locally so that --reload picks up code changes
    # without needing to restart the Celery worker.
    return True

@app.post("/interpret")
def interpret(req: TrainingRequest):
    intent = interpret_intent(req.task)
    return intent

@app.post("/auto-train", response_model=JobResponse)
def auto_train(req: TrainingRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    intent = interpret_intent(req.task)
    intent_payload = intent.model_dump()
    intent_payload["user_prompt"] = req.task
    job = Job(intent=intent_payload, username=req.username)
    db.add(job)
    db.commit()
    db.refresh(job)
    if _use_local_background_fallback():
        background_tasks.add_task(run_auto_train_pipeline.run, job.id)
    else:
        run_auto_train_pipeline.delay(job.id)
    return JobResponse(job_id=job.id, status=job.status, message="Job queued successfully")

@app.post("/train/manual", response_model=JobResponse)
async def train_manual(
    background_tasks: BackgroundTasks,
    task: str = Form(...),
    username: str = Form("Anonymous"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    intent = interpret_intent(task)
    intent_payload = intent.model_dump()
    intent_payload["user_prompt"] = task
    os.makedirs("uploads", exist_ok=True)
    dfs = []
    import pandas as pd
    for file in files:
        temp_path = os.path.join("uploads", f"part_{uuid4().hex}_{file.filename}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            dfs.append(pd.read_csv(temp_path))
        except: continue
            
    if not dfs: raise HTTPException(status_code=400, detail="No valid CSV files uploaded")
    merged_df = pd.concat(dfs, ignore_index=True)
    final_path = os.path.join("uploads", f"manual_merged_{uuid4().hex}.csv")
    merged_df.to_csv(final_path, index=False)
    job = Job(intent=intent_payload, username=username)
    db.add(job)
    db.commit()
    db.refresh(job)
    if _use_local_background_fallback():
        background_tasks.add_task(run_manual_train_pipeline.run, job.id, final_path)
    else:
        run_manual_train_pipeline.delay(job.id, final_path)
    return JobResponse(job_id=job.id, status=job.status, message="Manual training queued")

@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(job_id=job.id, status=job.status, intent=job.intent, model_path=job.model_path, message=job.message)

@app.get("/community-models")
def get_community_models(db: Session = Depends(get_db)):
    # Fetch latest 10 completed jobs
    jobs = db.query(Job).filter(Job.status == "completed").order_by(Job.id.desc()).limit(10).all()
    
    result = []
    for j in jobs:
        task_type = j.intent.get("task", "Unknown Task") if j.intent else "Unknown Task"
        modality = j.intent.get("modality", "text") if j.intent else "text"
        acc = j.accuracy.get("accuracy", 0.0) if j.accuracy and isinstance(j.accuracy, dict) else 0.0
        
        rating = None
        if j.feedback and isinstance(j.feedback, dict):
            rating = j.feedback.get("rating")
            
        result.append({
            "job_id": j.id,
            "username": j.username or "Anonymous",
            "task_type": task_type,
            "modality": modality,
            "accuracy": acc,
            "rating": rating
        })
    return result

from backend.core.schemas import FeedbackRequest

@app.post("/jobs/{job_id}/feedback")
def submit_feedback(job_id: str, req: FeedbackRequest, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.feedback = {"rating": req.rating, "comment": req.comment}
    db.commit()
    return {"status": "success", "message": "Feedback saved"}

@app.get("/download_model")
def download_model(job_id: str = None, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    if job_id:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.model_path and os.path.exists(job.model_path):
            return FileResponse(job.model_path, filename=os.path.basename(job.model_path))
    model_path = os.path.join("models", "model.pkl")
    if os.path.exists(model_path):
        return FileResponse(model_path, filename="model.pkl")
    raise HTTPException(status_code=404, detail="No trained models found")

# Serve frontend assets from project-relative path (works locally and on cloud hosts)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def read_index():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


def run_studio_cli():
    """CLI entrypoint for `unleash-studio` (pip install -e .)."""
    import uvicorn
    port = int(os.getenv("UNLEASH_PORT", "8001"))
    host = os.getenv("UNLEASH_HOST", "127.0.0.1")
    uvicorn.run("backend.api.main:app", host=host, port=port, reload=False)
