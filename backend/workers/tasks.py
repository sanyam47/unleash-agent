from celery import shared_task
from sqlalchemy.orm import Session
from backend.workers.celery_app import celery_app
from backend.db.database import SessionLocal
from backend.db.models import Job
from backend.data_fetcher import build_dataset
from backend.pipelines.text_pipeline import TextClassificationPipeline
from backend.pipelines.image_pipeline import ImageClassificationPipeline
from backend.pipelines.audio_pipeline import AudioClassificationPipeline
from backend.pipelines.regression_pipeline import NumericRegressionPipeline
import os

def _normalize_target_classes(target_classes):
    if isinstance(target_classes, list):
        cleaned = [str(c).strip() for c in target_classes if str(c).strip()]
        if cleaned:
            return cleaned
    return ["class_a", "class_b"]

def get_pipeline(modality: str, task: str = "classification"):
    if task == "regression":
        return NumericRegressionPipeline()
        
    if modality == "image":
        return ImageClassificationPipeline()
    elif modality == "audio":
        return AudioClassificationPipeline()
    return TextClassificationPipeline()

@celery_app.task
def run_auto_train_pipeline(job_id: str):
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        db.close()
        return
        
    job.status = "running"
    db.commit()
    
    try:
        intent = job.intent or {}
        modality = intent.get("modality", "text")
        task_type = intent.get("task", "classification")
        user_prompt = intent.get("user_prompt") or task_type
        target_classes = _normalize_target_classes(intent.get("target_classes"))
        
        # 1. Fetch data (Auto mode always uses internet)
        df = build_dataset(user_prompt, target_classes, modality)
        if df.empty:
            raise ValueError("No data fetched from internet")
            
        # 2. Save temp csv
        os.makedirs("uploads", exist_ok=True)
        temp_path = os.path.join("uploads", f"auto_{job_id}.csv")
        df.to_csv(temp_path, index=False)
        
        # 3. Train model
        pipeline = get_pipeline(modality, task_type)
        model_path, accuracy, message = pipeline.train(temp_path, intent)
        
        if model_path is None:
            raise ValueError(f"Training failed: {message}")
            
        if isinstance(accuracy, dict):
            job.accuracy = accuracy
            acc_val = accuracy.get("accuracy", accuracy.get("r2_score", 0.0))
        else:
            job.accuracy = {"accuracy": float(accuracy)}
            acc_val = accuracy
            
        job.status = "completed"
        job.model_path = model_path
        job.message = f"Auto-training ({modality}) completed. Score: {acc_val}"
        db.commit()
    except Exception as e:
        job.status = "failed"
        job.message = str(e)
        db.commit()
    finally:
        db.close()

@celery_app.task
def run_manual_train_pipeline(job_id: str, filepath: str):
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        db.close()
        return
        
    job.status = "running"
    db.commit()
    
    try:
        intent = job.intent or {}
        modality = intent.get("modality", "text")
        task_type = intent.get("task", "classification")
        
        pipeline = get_pipeline(modality, task_type)
        model_path, accuracy, message = pipeline.train(filepath, intent)
        
        if model_path is None:
            raise ValueError(f"Training failed: {message}")
            
        if isinstance(accuracy, dict):
            job.accuracy = accuracy
            acc_val = accuracy.get("accuracy", accuracy.get("r2_score", 0.0))
        else:
            job.accuracy = {"accuracy": float(accuracy)}
            acc_val = accuracy

        job.status = "completed"
        job.model_path = model_path
        job.message = f"Manual training ({modality}) completed. Score: {acc_val}"
        db.commit()
    except Exception as e:
        job.status = "failed"
        job.message = str(e)
        db.commit()
    finally:
        db.close()
@celery_app.task
def run_refine_pipeline(job_id: str):
    db: Session = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        db.close()
        return

    job.status = "running"
    db.commit()

    try:
        from backend.pipelines.refine_pipeline import RefinePipeline
        data = job.intent
        model_name = data.get("model_name")
        analysis = data.get("analysis")
        
        refiner = RefinePipeline(model_name)
        model_path, accuracy, report = refiner.execute(data)
        
        if model_path:
            job.status = "completed"
            job.model_path = os.path.basename(model_path)
            job.accuracy = report # Store full analytics JSON
            job.message = "Refinement complete. Comparison report generated."
        else:
            job.status = "failed"
            job.message = message
            
    except Exception as e:
        job.status = "failed"
        job.message = str(e)
    
    db.commit()
    db.close()


# Plain (non-Celery) version for direct background execution without a worker process.
# Used by FastAPI BackgroundTasks on Render and locally so the offline fallback
# code is always picked up without restarting a Celery worker.
def run_refine_pipeline_local(job_id: str):
    """Identical logic to run_refine_pipeline but runs in the FastAPI process."""
    db: Session = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        db.close()
        return

    job.status = "running"
    db.commit()

    try:
        from backend.pipelines.refine_pipeline import RefinePipeline
        data = job.intent
        model_name = data.get("model_name")

        refiner = RefinePipeline(model_name)
        model_path, accuracy, report = refiner.execute(data)

        if model_path:
            job.status = "completed"
            job.model_path = os.path.basename(model_path)
            job.accuracy = report
            job.message = "Refinement complete. Comparison report generated."
        else:
            job.status = "failed"
            job.message = "Pipeline returned no model path."

    except Exception as e:
        job.status = "failed"
        job.message = str(e)

    db.commit()
    db.close()
