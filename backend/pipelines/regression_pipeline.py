import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from backend.pipelines.base import ModelPipeline
import xgboost as xgb


class NumericRegressionPipeline(ModelPipeline):
    def train(self, filepath: str, intent: dict) -> tuple[str, dict, str]:
        """
        Tabular Regression Pipeline:
        Supports mixed numerical and categorical features, handles missing values,
        encodes categorical variables without data leakage, and trains a RandomForestRegressor.
        """
        if not filepath.endswith(".csv"):
            return None, 0.0, "Only CSV supported for regression"

        try:
            data = pd.read_csv(filepath)
        except Exception as e:
            return None, 0.0, f"CSV read error: {e}"

        if data.empty or len(data) < 10:
            return None, 0.0, "Dataset must contain at least 10 samples"

        # 1. Target Column Identification
        intent_target = intent.get("target_column")
        if intent_target and intent_target in data.columns:
            target_col = intent_target
        else:
            # Check common target name aliases
            target_candidates = ["target", "price", "label", "output", "value", "y"]
            found_candidate = None
            for c in data.columns:
                if c.lower() in target_candidates:
                    found_candidate = c
                    break
            target_col = found_candidate if found_candidate else data.columns[-1]

        # 2. Clean Target Column
        data[target_col] = pd.to_numeric(data[target_col], errors="coerce")
        data = data.dropna(subset=[target_col])
        if len(data) < 10:
            return None, 0.0, f"Target column '{target_col}' has fewer than 10 valid numeric values"

        X = data.drop(columns=[target_col])
        y = data[target_col]

        # 3. Identify Feature Types
        num_cols = X.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = X.select_dtypes(exclude=[np.number]).columns.tolist()

        # Remove single-value or all-unique string columns (e.g. IDs or UUIDs)
        cat_cols = [c for c in cat_cols if 1 < X[c].nunique() < (len(X) * 0.9)]

        if not num_cols and not cat_cols:
            return None, 0.0, "No valid feature columns found for regression"

        # 4. Build Preprocessing Transformers
        transformers = []
        if num_cols:
            num_transformer = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler())
            ])
            transformers.append(("num", num_transformer, num_cols))

        if cat_cols:
            cat_transformer = Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
            ])
            transformers.append(("cat", cat_transformer, cat_cols))

        preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")

        # 5. Train/Test Split FIRST (prevents imputation & scaling data leakage)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # 6. Unified Pipeline with State-of-the-Art XGBoost Regressor
        try:
            regressor = xgb.XGBRegressor(
                n_estimators=150,
                learning_rate=0.05,
                max_depth=5,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1
            )
        except Exception:
            regressor = RandomForestRegressor(n_estimators=100, random_state=42)

        pipeline = Pipeline([
            ("preprocessor", preprocessor),
            ("regressor", regressor)
        ])

        pipeline.fit(X_train, y_train)

        # 7. Evaluate
        y_pred = pipeline.predict(X_test)
        r2 = float(r2_score(y_test, y_pred))
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

        # Also compute MAPE if no zero targets
        mape = None
        if not (y_test == 0).any():
            mape = float(np.mean(np.abs((y_test - y_pred) / y_test)) * 100)

        metrics = {
            "r2_score": round(r2, 4),
            "accuracy": round(max(0.0, r2), 4),  # for UI display compatibility
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "mape": round(mape, 2) if mape is not None else None,
            "samples_train": len(X_train),
            "samples_test": len(X_test),
            "target_column": target_col,
            "numeric_features": num_cols,
            "categorical_features": cat_cols
        }

        os.makedirs("models", exist_ok=True)
        model_path = "models/regression_model.pkl"
        scaler_path = "models/regression_scaler.pkl"

        joblib.dump(pipeline, model_path)
        # Save preprocessor as regression_scaler.pkl for backwards compatibility
        joblib.dump(pipeline.named_steps["preprocessor"], scaler_path)

        return model_path, metrics, f"Regression training successful (R2: {round(r2, 3)})"
