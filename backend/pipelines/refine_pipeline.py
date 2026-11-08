import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from backend.data_fetcher import build_dataset
from backend.core.analytics_engine import AnalyticsEngine
from backend.pipelines.text_pipeline import clean_text, SemanticTransformerEncoder

class RefinePipeline:
    def __init__(self, model_name: str):
        self.model_path = os.path.join(os.getcwd(), "models", model_name)
        self.vectorizer_path = os.path.join(os.getcwd(), "models", "vectorizer.pkl")

    def execute(self, job_intent: dict) -> tuple[str, float, str]:
        """Performs Knowledge Distillation and Refinement."""
        analysis = job_intent.get("analysis", {})
        injected_path = job_intent.get("injected_file_path")
        auto_fill = job_intent.get("auto_fill_gaps", False)

        # 1. Load Teacher
        if not os.path.exists(self.model_path):
            return None, 0.0, "Original model not found"
        
        # Determine modality (defaulting to text for now)
        modality = analysis.get("modality", "text")
        action = analysis.get("action", "REFINE")
        target_classes = analysis.get("target_classes", [])
        new_labels = analysis.get("new_labels", [])
        remove_labels = analysis.get("remove_labels", [])

        # 2. Collect Data
        df_list = []
        
        # A. Load Injected Data if present
        injected_df = pd.DataFrame()
        if injected_path and os.path.exists(injected_path):
            injected_df = pd.read_csv(injected_path)
            # Duplicate human samples to give them more weight (5x)
            df_list.append(pd.concat([injected_df] * 5, ignore_index=True))

        # B. Distillation / Gap Filling
        auto_df = pd.DataFrame()
        all_classes = [c for c in target_classes if c not in remove_labels] + new_labels
        for cls in all_classes:
            human_count = 0
            if not injected_df.empty and 'label' in injected_df.columns:
                human_count = len(injected_df[injected_df['label'] == cls])
            
            # If auto_fill is on OR it's an existing class we want to preserve
            if auto_fill or cls in target_classes:
                needed = 50 - human_count
                if needed > 0:
                    df_ai = build_dataset(f"data for {cls}", [cls], modality)
                    df_list.append(df_ai.head(needed))
                    if auto_df.empty:
                        auto_df = df_ai.head(needed)
                    else:
                        auto_df = pd.concat([auto_df, df_ai.head(needed)], ignore_index=True)
        
        if not df_list and auto_df.empty:
            return None, 0.0, "No data available for training."

        # 2. THE INTELLIGENCE SHIELD (Memory Replay)
        safety_data = pd.DataFrame()
        if os.path.exists(self.model_path):
            print("🛡️ Activating Intelligence Shield: Fetching safety memories...")
            teacher = joblib.load(self.model_path)
            # Try to identify what the teacher already knows
            teacher_classes = getattr(teacher, 'classes_', None)
            if teacher_classes is not None:
                old_classes = teacher_classes.tolist()
                safety_data = build_dataset("safety memories", old_classes, modality)
        
        # 3. Merge Knowledge
        full_df = pd.concat([injected_df, auto_df, safety_data]).drop_duplicates(subset=['text'])
        
        if remove_labels:
            full_df = full_df[~full_df['label'].isin(remove_labels)]
        
        # 4. Retrain Student
        target_filename = job_intent.get("target_filename", "refined_" + os.path.basename(self.model_path))
        
        if modality == "text":
            return self._retrain_text(full_df, model_name=target_filename)
        
        return None, 0.0, f"Modality {modality} not supported in Lab yet."

    def _retrain_text(self, df: pd.DataFrame, model_name: str):
        df = df.dropna(subset=["text", "label"]).copy()
        df["text"] = df["text"].apply(clean_text)
        df = df[df["text"].str.strip() != ""]

        X_text = df["text"]
        y = df["label"]
        classes = df["label"].unique().tolist()

        # Split raw text first before vectorizing
        try:
            X_train_text, X_test_text, y_train, y_test = train_test_split(
                X_text, y, test_size=0.2, random_state=42
            )
        except Exception:
            X_train_text, X_test_text, y_train, y_test = X_text, X_text, y, y

        try:
            vectorizer_step = ("vectorizer", SemanticTransformerEncoder(model_name="all-MiniLM-L6-v2"))
        except Exception:
            vectorizer_step = ("vectorizer", TfidfVectorizer(stop_words="english", max_features=5000, lowercase=True))
        classifier = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)

        pipeline = Pipeline([
            vectorizer_step,
            ("classifier", classifier)
        ])

        pipeline.fit(X_train_text, y_train)

        # 2. Compare with Parent (Teacher)
        analytics = {}
        try:
            if os.path.exists(self.model_path):
                teacher = joblib.load(self.model_path)
                
                # Check if teacher is a Pipeline
                if isinstance(teacher, Pipeline):
                    teacher_acc = teacher.score(X_test_text, y_test)
                    student_acc = pipeline.score(X_test_text, y_test)
                    analytics = {
                        "overall": {
                            "student_accuracy": round(float(student_acc), 4),
                            "parent_accuracy": round(float(teacher_acc), 4),
                            "gain": round(float(student_acc - teacher_acc), 4)
                        },
                        "class_drift": {}
                    }
                else:
                    v_path = os.path.join("models", "vectorizer.pkl")
                    if os.path.exists(v_path):
                        t_vectorizer = joblib.load(v_path)
                        X_teacher = t_vectorizer.transform(X_test_text)
                        X_student = pipeline.named_steps["vectorizer"].transform(X_test_text)
                        analytics = AnalyticsEngine.compare_models(teacher, classifier, X_student, y_test, classes)
                    else:
                        student_acc = pipeline.score(X_test_text, y_test)
                        analytics = {"overall": {"student_accuracy": round(float(student_acc), 4), "parent_accuracy": 0, "gain": 0}, "class_drift": {}}
        except Exception as e:
            print(f"Analytics Sync Error: {e}")
            student_acc = pipeline.score(X_test_text, y_test)
            analytics = {"overall": {"student_accuracy": round(float(student_acc), 4), "parent_accuracy": 0, "gain": 0}, "class_drift": {}}

        # 3. Save
        model_path = os.path.join("models", model_name)
        joblib.dump(pipeline, model_path)
        joblib.dump(pipeline.named_steps["vectorizer"], os.path.join("models", "refined_vectorizer.pkl"))
        base_name = os.path.splitext(model_name)[0]
        joblib.dump(pipeline.named_steps["vectorizer"], os.path.join("models", f"{base_name}_vectorizer.pkl"))
        
        accuracy = analytics.get("overall", {}).get("student_accuracy", 0.0)
        
        return model_path, round(accuracy, 3), analytics
