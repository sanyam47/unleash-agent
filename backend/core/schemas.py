from pydantic import BaseModel
from typing import List, Optional

class TrainingRequest(BaseModel):
    task: str  # User's prompt, e.g. "I want to train a text classifier for legal documents"
    username: Optional[str] = "Anonymous"

class FeedbackRequest(BaseModel):
    rating: int
    comment: Optional[str] = ""

class IntentAnalysis(BaseModel):
    modality: str  # text, image, audio, numeric
    task: str      # classification, regression
    target_classes: Optional[List[str]] = None # Only for classification

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    intent: Optional[dict] = None
    model_path: Optional[str] = None
    message: Optional[str] = None

class LabRequest(BaseModel):
    model_name: str
    instruction: str

class LabAnalysis(BaseModel):
    action: str  # REFINE, ADD_CLASS, REMOVE_CLASS, TWEAK_PARAMS
    modality: str
    target_classes: List[str]
    new_labels: Optional[List[str]] = []
    remove_labels: Optional[List[str]] = []
    reasoning: Optional[str] = "Interpreted from instruction"
    message: str

class LabChatRequest(BaseModel):
    model_name: str
    feedback: str
    previous_analysis: LabAnalysis
    history: Optional[List[dict]] = []

class LabExecutionRequest(BaseModel):
    model_name: str
    instruction: str
    analysis: LabAnalysis
    injected_file_path: Optional[str] = None
    auto_fill_gaps: Optional[bool] = False

class LabPredictRequest(BaseModel):
    model_name: str
    text: str
