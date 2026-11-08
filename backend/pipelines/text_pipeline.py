import os
import re
import html
import joblib
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from backend.pipelines.base import ModelPipeline

# Lazy cache for transformer models to avoid reloading from disk on every call
_SENTENCE_MODEL_CACHE = {}

def get_sentence_transformer(model_name: str = "all-MiniLM-L6-v2"):
    if model_name not in _SENTENCE_MODEL_CACHE:
        from sentence_transformers import SentenceTransformer
        _SENTENCE_MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _SENTENCE_MODEL_CACHE[model_name]


def clean_text(text: str) -> str:
    """Preprocesses and normalizes raw text input."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    # Unescape HTML entities
    text = html.unescape(text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    # Normalize whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


class SemanticTransformerEncoder(BaseEstimator, TransformerMixin):
    """
    State-of-the-Art Sentence Transformer encoder (all-MiniLM-L6-v2).
    Generates 384-dimensional dense semantic embeddings for text,
    capturing deep context, nuances, and semantic meanings.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        model = get_sentence_transformer(self.model_name)
        texts = [clean_text(str(x)) for x in X]
        return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)


class TextClassificationPipeline(ModelPipeline):
    def train(self, filepath: str, intent: dict) -> tuple[str, dict, str]:
        if not filepath.endswith(".csv"):
            return None, 0.0, "Only CSV supported"

        try:
            data = pd.read_csv(filepath)
        except Exception as e:
            return None, 0.0, f"CSV read error: {e}"

        if "text" not in data.columns or "label" not in data.columns:
            return None, 0.0, "CSV must contain 'text' and 'label' columns"

        if data.empty:
            return None, 0.0, "Dataset is empty"

        # Preprocessing: drop missing, string conversion, clean text
        data = data.dropna(subset=["text", "label"]).copy()
        data["text"] = data["text"].apply(clean_text)
        data = data[data["text"].str.strip() != ""]

        if data.empty:
            return None, 0.0, "Dataset contains no valid text after cleaning"

        X_text = data["text"]
        y = data["label"]

        if len(set(y)) < 2:
            return None, 0.0, "Need at least 2 different labels"

        # Check stratification requirements
        class_counts = y.value_counts()
        test_size_val = 0.2
        n_test = int(len(y) * test_size_val)
        n_classes = len(class_counts)
        can_stratify = (len(y) >= 10) and (class_counts >= 2).all() and (n_test >= n_classes)

        # Split raw text and labels FIRST before any feature extraction
        X_train, X_test, y_train, y_test = train_test_split(
            X_text, y, test_size=test_size_val, random_state=42, 
            stratify=y if can_stratify else None
        )

        # Use SOTA SentenceTransformer encoder if available, with graceful fallback to TF-IDF
        try:
            encoder = SemanticTransformerEncoder(model_name="all-MiniLM-L6-v2")
            # Quick sanity test
            _ = get_sentence_transformer("all-MiniLM-L6-v2")
            vectorizer_step = ("vectorizer", encoder)
            encoder_type = "Transformer (all-MiniLM-L6-v2)"
        except Exception as ex:
            vectorizer_step = ("vectorizer", TfidfVectorizer(
                stop_words="english",
                max_features=5000,
                ngram_range=(1, 2),
                lowercase=True
            ))
            encoder_type = "TF-IDF (Fallback)"

        classifier = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42
        )

        # Unified Scikit-Learn Pipeline: binds preprocessor + estimator together
        pipeline = Pipeline([
            vectorizer_step,
            ("classifier", classifier)
        ])

        pipeline.fit(X_train, y_train)

        # Comprehensive evaluation metrics
        y_pred = pipeline.predict(X_test)
        accuracy = float(accuracy_score(y_test, y_pred))
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_test, y_pred, average="weighted", zero_division=0
        )

        metrics = {
            "accuracy": round(accuracy, 4),
            "f1_score": round(float(f1), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "encoder": encoder_type,
            "samples_train": len(X_train),
            "samples_test": len(X_test),
            "classes": [str(c) for c in pipeline.classes_]
        }

        os.makedirs("models", exist_ok=True)
        model_path = "models/model.pkl"
        vectorizer_path = "models/vectorizer.pkl"

        # Save unified pipeline
        joblib.dump(pipeline, model_path)
        # Also save vectorizer/encoder standalone for backward compatibility
        joblib.dump(pipeline.named_steps["vectorizer"], vectorizer_path)
        joblib.dump(pipeline.named_steps["vectorizer"], "models/model_vectorizer.pkl")

        return model_path, metrics, f"Training successful using {encoder_type} (Accuracy: {round(accuracy, 3)})"
