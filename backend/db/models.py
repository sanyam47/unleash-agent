from sqlalchemy import Column, String, JSON
from backend.db.database import Base
import uuid

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="queued") # queued, running, completed, failed
    intent = Column(JSON, nullable=True) # {modality, task, target_classes}
    model_path = Column(String, nullable=True)
    accuracy = Column(JSON, nullable=True) # Store metrics
    message = Column(String, nullable=True)
    
    # Community & Feedback
    username = Column(String, default="Anonymous")
    feedback = Column(JSON, nullable=True) # {"rating": 5, "comment": "good"}
    
    # Lineage Fields
    parent_id = Column(String, nullable=True)
    version = Column(String, default="v1")
