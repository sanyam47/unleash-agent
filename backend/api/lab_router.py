from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
import joblib
from backend.db.database import get_db
from backend.db.models import Job
from backend.core.schemas import LabRequest, LabAnalysis, JobResponse, LabChatRequest, LabExecutionRequest, LabPredictRequest
from backend.core.config import settings
from backend.core.data_validator import DataValidator
import json
from backend.core.paths import MODELS_DIR, LAB_SESSIONS_DIR
from backend.core.gemini_client import analyze_lab_instruction_gemini, refine_lab_chat_gemini, gemini_available
from backend.pipelines.image_pipeline import extract_image_features

router = APIRouter(prefix="/lab", tags=["Model Lab"])
validator = DataValidator()

@router.post("/inject")
async def inject_custom_data(
    file: UploadFile = File(...),
    target_classes: str = Form(...), # Sent as a JSON string list
    goal_description: str = Form("") 
):
    """Uploads and validates custom knowledge for the current lab session."""
    classes = json.loads(target_classes)
    
    # Save temp file
    file_path = os.path.join(LAB_SESSIONS_DIR, f"inject_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Validate
    results = validator.validate_csv(file_path, classes, goal_description)
    results["file_path"] = file_path
    
    return results

@router.post("/upload")
async def upload_external_model(file: UploadFile = File(...)):
    """Uploads an external .pkl model to the models directory."""
    if not file.filename.endswith(".pkl"):
        raise HTTPException(status_code=400, detail="Only .pkl files allowed")
    
    target_path = os.path.join(MODELS_DIR, file.filename)
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"message": f"Model {file.filename} uploaded successfully", "filename": file.filename}

@router.get("/models")
def list_models():
    """Lists all available .pkl models in the models directory."""
    print(f"DEBUG: Scanning MODELS_DIR: {MODELS_DIR}")
    if not os.path.exists(MODELS_DIR):
        print("DEBUG: MODELS_DIR does not exist!")
        return ["DEBUG_ERROR_FOLDER_MISSING.pkl"]
    
    files = [f for f in os.listdir(MODELS_DIR) if f.endswith(".pkl")]
    print(f"DEBUG: Found files: {files}")
    
    # Force-inject a dummy to see if it reaches the UI
    if not files:
        return ["DEBUG_NO_FILES_FOUND.pkl"]
        
    return files

@router.get("/lineage/{model_name}")
def get_model_lineage(model_name: str, db: Session = Depends(get_db)):
    """Returns the history/lineage of a specific model lineage."""
    base_name = model_name.split("_v")[0].replace(".pkl", "")
    history = db.query(Job).filter(Job.model_path.like(f"%{base_name}%")).order_by(Job.version).all()
    
    return [
        {
            "id": h.id,
            "version": h.version,
            "accuracy": h.accuracy,
            "instruction": h.intent.get("instruction"),
            "model_path": h.model_path,
            "parent_id": h.parent_id
        } for h in history if h.status == "completed"
    ]

@router.get("/download_report/{job_id}")
def download_audit_report(job_id: str, db: Session = Depends(get_db)):
    """Downloads the performance audit report as a human-readable text file."""
    from backend.core.analytics_engine import AnalyticsEngine
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.accuracy:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Generate human-readable text report
    instruction = job.intent.get("instruction", "Unknown Manipulation")
    report_text = AnalyticsEngine.generate_text_report(job.accuracy, instruction)
    
    file_path = os.path.join(LAB_SESSIONS_DIR, f"Audit_Report_{job_id}.txt")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_text)
        
    return FileResponse(file_path, filename=f"Model_Audit_Report_{job_id}.txt", media_type="text/plain")

@router.post("/analyze", response_model=LabAnalysis)
def analyze_lab_instruction(req: LabRequest):
    """Uses LLM to interpret how to manipulate the model."""
    # 1. Try to inspect the model's metadata
    model_path = os.path.join(MODELS_DIR, req.model_name)
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        model = joblib.load(model_path)
        current_classes = getattr(model, "classes_", [])
        if hasattr(current_classes, "tolist"):
            current_classes = current_classes.tolist()
    except:
        current_classes = []

    # 2. Ask GPT to plan the modification
    prompt = f"""
    The user has an existing machine learning model ({req.model_name}) with these classes: {current_classes}.
    Instruction: "{req.instruction}"
    
    Identify the action: REFINE (more data), ADD_CLASS, REMOVE_CLASS, or TWEAK_PARAMS.
    List the new labels to add and labels to remove.
    """
    
    try:
        if gemini_available():
            result = analyze_lab_instruction_gemini(req.model_name, current_classes, req.instruction)
            return LabAnalysis(**result)
        raise RuntimeError("Gemini not available")
    except Exception as e:
        # Fallback smarter keyword & set-logic
        text = req.instruction.lower()
        
        # 1. Robust exclusion set to prevent common words from becoming labels
        exclude = {
            'this', 'model', 'differentiate', 'between', 'picture', 'of', 'and', 'make', 'it', 'to', 'the',
            'for', 'class', 'category', 'detection', 'recognize', 'tell', 'apart', 'from', 'with', 'picture',
            'image', 'dataset', 'training', 'accuracy', 'better', 'improvement', 'refine', 'add', 'remove',
            'delete', 'stop', 'detecting', 'recognizing'
        }
        
        import re
        all_words = re.findall(r'\b\w+\b', text)
        
        # 2. Extract unique potential labels only
        potential_labels = []
        seen = set()
        for w in all_words:
            if w not in exclude and len(w) > 2 and w not in seen:
                potential_labels.append(w)
                seen.add(w)
        
        # 3. Logic: Compare against ACTUAL classes found in the file
        action = "REFINE"
        to_add = []
        to_remove = []
        
        if potential_labels:
            # Detect what to remove (in model but NOT in new prompt)
            for old_cls in current_classes:
                if str(old_cls).lower() not in potential_labels:
                    to_remove.append(old_cls)
            
            # Detect what to add (in prompt but NOT in model)
            current_classes_lower = [str(c).lower() for c in current_classes]
            for new_p in potential_labels:
                if new_p not in current_classes_lower:
                    to_add.append(new_p)
            
            if to_add: action = "ADD_CLASS"
            elif to_remove: action = "REMOVE_CLASS"

        return LabAnalysis(
            action=action,
            modality="text", 
            target_classes=current_classes,
            new_labels=to_add,
            remove_labels=to_remove,
            message="Cleaned Offline interpretation (Set-logic comparison)."
        )

@router.post("/chat", response_model=LabAnalysis)
def refine_lab_instruction(req: LabChatRequest):
    """Refines the current edit plan based on user chat feedback."""
    prompt = f"""
    The user is perfecting an AI Model Edit Plan.
    Previous Plan: {req.previous_analysis.model_dump()}
    User Feedback: "{req.feedback}"
    
    Update the plan based on the feedback. Be conservative. 
    If the user says "Keep X" or "Don't remove X", move X from remove_labels to target_classes.
    """
    
    try:
        if gemini_available():
            result = refine_lab_chat_gemini(req.previous_analysis.model_dump(), req.feedback)
            return LabAnalysis(**result)
        raise RuntimeError("Gemini not available")
    except Exception as e:
        # Smart Offline Fallback for Chat
        analysis = req.previous_analysis.model_dump()
        text = req.feedback.lower()
        
        # Simple Logic: "Keep X" or "Don't remove X"
        if "keep" in text or "don't remove" in text or "dont remove" in text:
            for cls in analysis["remove_labels"][:]:
                if cls.lower() in text:
                    analysis["remove_labels"].remove(cls)
                    if cls not in analysis["target_classes"]:
                        analysis["target_classes"].append(cls)
            analysis["message"] = "Refined offline: Preserved requested classes."
        
        # Simple Logic: "Actually add X"
        if "add" in text:
            # Try to find what else to add
            import re
            words = re.findall(r'\b\w+\b', text)
            for w in words:
                if len(w) > 3 and w not in ["actually", "please", "can", "you", "add"]:
                    if w not in analysis["new_labels"]:
                        analysis["new_labels"].append(w)
            analysis["message"] = "Refined offline: Added requested classes."
            analysis["action"] = "ADD_CLASS"

        return LabAnalysis(**analysis)


from fastapi import File, Form, UploadFile
import io
from PIL import Image
import numpy as np
from sklearn.pipeline import Pipeline
from backend.pipelines.text_pipeline import clean_text
from backend.pipelines.audio_pipeline import extract_audio_features

@router.post("/predict")
async def live_prediction(
    model_name: str = Form(...),
    text: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """Instantly predicts using a specific model."""
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name required")
    
    full_path = os.path.join(MODELS_DIR, model_name)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Model file missing")
        
    try:
        model = joblib.load(full_path)
        
        X = None
        
        if text:
            cleaned_text = clean_text(text)
            
            # If model is a unified Pipeline with its own preprocessor
            if isinstance(model, Pipeline):
                try:
                    prediction = model.predict([cleaned_text])[0]
                    probs = {}
                    if hasattr(model, "predict_proba"):
                        p_vals = model.predict_proba([cleaned_text])[0]
                        classes = getattr(model, "classes_", [])
                        for i, cls in enumerate(classes):
                            probs[str(cls)] = float(p_vals[i])
                    return {
                        "prediction": str(prediction),
                        "confidence": probs.get(str(prediction), 1.0),
                        "all_probs": probs
                    }
                except Exception:
                    # If direct pipeline prediction on raw text fails, fall back to vectorizer candidates
                    pass
            
            # Legacy raw model: Try all available vectorizers to find one whose feature count matches
            # Priority: model-specific > refined > original
            base_name = os.path.splitext(model_name)[0]
            vectorizer_candidates = [
                os.path.join(MODELS_DIR, f"{base_name}_vectorizer.pkl"),
                os.path.join(MODELS_DIR, "refined_vectorizer.pkl"),
                os.path.join(MODELS_DIR, "vectorizer.pkl"),
            ]
            last_error = None
            for v_path in vectorizer_candidates:
                if not os.path.exists(v_path):
                    continue
                try:
                    vectorizer = joblib.load(v_path)
                    X = vectorizer.transform([cleaned_text])
                    # Quick sanity check: try predict to see if features match
                    model.predict(X)
                    last_error = None
                    break  # Success!
                except ValueError as ve:
                    last_error = ve
                    X = None  # Reset and try next vectorizer
                    continue
            
            if X is None and last_error:
                raise last_error
            elif X is None:
                raise HTTPException(status_code=404, detail="No vectorizer found for this model")
                
        elif file:
            contents = await file.read()
            filename = (file.filename or "").lower()
            audio_exts = [".wav", ".mp3", ".ogg", ".flac", ".m4a"]
            
            if any(filename.endswith(ext) for ext in audio_exts) or (file.content_type and "audio" in file.content_type):
                features = extract_audio_features(io.BytesIO(contents))
                X = features.reshape(1, -1)

                # Backward compatibility with legacy 26-dim audio models
                expected_dim = None
                if hasattr(model, "n_features_in_"):
                    expected_dim = model.n_features_in_
                elif isinstance(model, Pipeline) and hasattr(model.named_steps.get("scaler"), "n_features_in_"):
                    expected_dim = model.named_steps["scaler"].n_features_in_
                
                if expected_dim == 26:
                    X = features[:26].reshape(1, -1)

                if not isinstance(model, Pipeline):
                    scaler_path = os.path.join(MODELS_DIR, "audio_scaler.pkl")
                    if os.path.exists(scaler_path):
                        scaler = joblib.load(scaler_path)
                        X = scaler.transform(X)
            else:
                features = extract_image_features(io.BytesIO(contents))
                X = features.reshape(1, -1)
                
                # Check if this model expects legacy 4096-dim flat pixels
                expected_dim = None
                if hasattr(model, "n_features_in_"):
                    expected_dim = model.n_features_in_
                elif isinstance(model, Pipeline) and hasattr(model.named_steps.get("scaler"), "n_features_in_"):
                    expected_dim = model.named_steps["scaler"].n_features_in_
                
                if expected_dim == 4096:
                    img = Image.open(io.BytesIO(contents)).convert('L').resize((64, 64))
                    img_array = np.array(img, dtype=np.float32).flatten()
                    X = np.array([img_array])

                if not isinstance(model, Pipeline):
                    scaler_path = os.path.join(MODELS_DIR, "image_scaler.pkl")
                    if os.path.exists(scaler_path):
                        scaler = joblib.load(scaler_path)
                        X = scaler.transform(X)
        else:
             raise HTTPException(status_code=400, detail="Must provide text or file based on model modality")
        
        prediction = model.predict(X)[0]
        
        probs = {}
        if hasattr(model, "predict_proba"):
            p_vals = model.predict_proba(X)[0]
            classes = getattr(model, "classes_", [])
            for i, cls in enumerate(classes):
                probs[str(cls)] = float(p_vals[i])
                
        return {
            "prediction": str(prediction),
            "confidence": probs.get(str(prediction), 1.0),
            "all_probs": probs
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.post("/execute", response_model=JobResponse)
def execute_lab_action(req: LabExecutionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Triggers the background task to perform the model manipulation."""
    from backend.workers.tasks import run_refine_pipeline_local
    
    # 1. Calculate Versioning
    base_name = req.model_name.split("_v")[0].replace(".pkl", "")
    existing_versions = db.query(Job).filter(Job.model_path.like(f"%{base_name}%")).count()
    next_version = f"v{existing_versions + 1}"
    
    # 2. Create versioned filename
    versioned_filename = f"{base_name}_{next_version}.pkl"

    # 3. Create a job record
    job = Job(
        status="queued",
        parent_id=req.model_name, # Track which model we are refining
        version=next_version,
        intent={
            "action": "lab_manipulation",
            "model_name": req.model_name,
            "target_filename": versioned_filename,
            "instruction": req.instruction,
            "analysis": req.analysis.model_dump(),
            "injected_file_path": req.injected_file_path,
            "auto_fill_gaps": req.auto_fill_gaps
        }
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    run_refine_pipeline_local(job.id)
    
    return JobResponse(
        job_id=job.id,
        status="queued",
        message=f"Lab manipulation for {req.model_name} started."
    )
