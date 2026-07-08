"""
Trains a Random Forest model to predict job effort (actual hours).

Features used:
    - product type (encoded)
    - job type (encoded)
    - estimated hours
    - average contract price for that product/job type
    - sales count (how common is this type of work)

Target:
    - actual hours (act_hrs)

Run:
    python predictor/train.py
"""

import sys
import sqlite3
import pickle
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score, LeaveOneOut
from sklearn.metrics import mean_absolute_error, r2_score
from app.config import settings
from app.logger import get_logger

logger = get_logger("train")

DB_PATH    = settings.DB_PATH
MODEL_PATH = "data/predictor_model.pkl"
META_PATH  = "data/predictor_meta.pkl"


def load_training_data(db_path: str = DB_PATH) -> pd.DataFrame:
    """
    Loads job_features table from SQLite.
    This is our training dataset — 100 rows.
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM job_features", conn)
    conn.close()

    # Remove rows with missing or zero hours
    df = df[(df["est_hrs"] > 0) & (df["act_hrs"] > 0)]
    df = df.dropna(subset=["prod_type", "job_type"])

    # Remove the '?' placeholder prod types
    df = df[df["prod_type"] != "?"]

    logger.info(f"Training data: {len(df)} clean rows")
    return df


def engineer_features(df: pd.DataFrame) -> tuple:
    """
    Converts raw data into ML-ready features.

    Returns:
        X           - feature matrix (numpy)
        y           - target vector (actual hours)
        encoders    - dict of LabelEncoders for prod_type and job_type
        feature_names - list of feature names
    """

    # ── ENCODE CATEGORICAL FEATURES ───────────────────────────────────────
    le_prod = LabelEncoder()
    le_job  = LabelEncoder()

    df["prod_type_enc"] = le_prod.fit_transform(df["prod_type"])
    df["job_type_enc"]  = le_job.fit_transform(df["job_type"])

    # ── PRODUCT-LEVEL STATISTICS ───────────────────────────────────────────
    # Average actual hours per product type — powerful predictor
    prod_stats = df.groupby("prod_type")["act_hrs"].agg(
        prod_avg_act_hrs="mean",
        prod_std_act_hrs="std",
        prod_count="count",
    ).reset_index()
    prod_stats["prod_std_act_hrs"] = prod_stats["prod_std_act_hrs"].fillna(0)
    df = df.merge(prod_stats, on="prod_type", how="left")

    # Average overrun % per product type
    prod_overrun = df.groupby("prod_type")["overrun_pct"].mean().reset_index()
    prod_overrun.columns = ["prod_type", "prod_avg_overrun_pct"]
    df = df.merge(prod_overrun, on="prod_type", how="left")

    # ── JOB TYPE STATISTICS ────────────────────────────────────────────────
    job_stats = df.groupby("job_type")["act_hrs"].agg(
        job_avg_act_hrs="mean",
    ).reset_index()
    df = df.merge(job_stats, on="job_type", how="left")

    # ── FEATURE MATRIX ─────────────────────────────────────────────────────
    feature_names = [
        "prod_type_enc",       # which product category
        "job_type_enc",        # which job type
        "est_hrs",             # the original estimate
        "avg_price",           # average contract price for this combo
        "sales_count",         # how many times this type appears in sales
        "prod_avg_act_hrs",    # historical average actual hours for this product
        "prod_std_act_hrs",    # variability of hours for this product
        "prod_count",          # how many training examples for this product
        "prod_avg_overrun_pct",# how much this product type typically overruns
        "job_avg_act_hrs",     # historical average actual hours for this job type
    ]

    X = df[feature_names].fillna(0).values
    y = df["act_hrs"].values

    encoders = {
        "prod_type": le_prod,
        "job_type":  le_job,
    }

    return X, y, encoders, feature_names, df


def train_model(X, y):
    """
    Trains a Random Forest model with Leave-One-Out cross validation.
    With only 100 samples, LOO gives the most honest evaluation.

    Returns:
        model       - trained RandomForestRegressor
        cv_scores   - cross validation MAE scores
    """
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=2,
        min_samples_split=4,
        max_features="sqrt",
        random_state=42,
        n_jobs=-1,
    )

    # Leave-One-Out cross validation
    logger.info("Running Leave-One-Out cross validation...")
    loo = LeaveOneOut()
    cv_scores = cross_val_score(
        model, X, y,
        cv=loo,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
    )

    mae_scores = -cv_scores
    logger.info(f"LOO CV MAE: {mae_scores.mean():.2f} ± {mae_scores.std():.2f} hrs")

    # Train on all data
    model.fit(X, y)
    train_preds = model.predict(X)
    train_mae = mean_absolute_error(y, train_preds)
    train_r2  = r2_score(y, train_preds)

    logger.info(f"Train MAE: {train_mae:.2f} hrs")
    logger.info(f"Train R²:  {train_r2:.3f}")

    return model, mae_scores


def save_model(model, encoders, feature_names, df, cv_mae):
    """Saves model and metadata to disk."""

    # Build product type stats for fast lookup at prediction time
    prod_stats = df.groupby("prod_type").agg(
        avg_act_hrs=("act_hrs",     "mean"),
        std_act_hrs=("act_hrs",     "std"),
        avg_est_hrs=("est_hrs",     "mean"),
        avg_overrun=("overrun_pct", "mean"),
        count=("act_hrs",           "count"),
        overrun_rate=("overrun",    "mean"),
    ).round(2).to_dict(orient="index")

    job_stats = df.groupby("job_type").agg(
        avg_act_hrs=("act_hrs", "mean"),
    ).round(2).to_dict(orient="index")

    meta = {
        "encoders":      encoders,
        "feature_names": feature_names,
        "prod_stats":    prod_stats,
        "job_stats":     job_stats,
        "cv_mae":        round(cv_mae, 2),
        "training_rows": len(df),
        "product_types": list(encoders["prod_type"].classes_),
        "job_types":     list(encoders["job_type"].classes_),
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    with open(META_PATH, "wb") as f:
        pickle.dump(meta, f)

    logger.info(f"✅ Model saved to {MODEL_PATH}")
    logger.info(f"✅ Meta  saved to {META_PATH}")
    return meta


def main():
    print("\n" + "="*60)
    print("  TRAINING PREDICTION MODEL")
    print("="*60 + "\n")

    # Load data
    df = load_training_data()
    print(f"Training rows   : {len(df)}")
    print(f"Product types   : {df['prod_type'].nunique()}")
    print(f"Job types       : {df['job_type'].nunique()}")
    print(f"Act hrs range   : {df['act_hrs'].min():.1f} – {df['act_hrs'].max():.1f}")
    print()

    # Engineer features
    X, y, encoders, feature_names, df_enriched = engineer_features(df)
    print(f"Feature matrix  : {X.shape}")
    print(f"Features        : {feature_names}")
    print()

    # Train
    model, cv_scores = train_model(X, y)

    # Feature importance
    importances = sorted(
        zip(feature_names, model.feature_importances_),
        key=lambda x: x[1], reverse=True,
    )
    print("\nFeature Importances:")
    for name, imp in importances:
        bar = "█" * int(imp * 40)
        print(f"  {name:<28} {imp:.3f}  {bar}")

    # Save
    meta = save_model(model, encoders, feature_names, df_enriched, cv_scores.mean())

    print("\n" + "="*60)
    print("  MODEL TRAINING COMPLETE")
    print("="*60)
    print(f"  CV MAE          : ±{meta['cv_mae']} hrs")
    print(f"  Product types   : {len(meta['product_types'])}")
    print(f"  Job types       : {len(meta['job_types'])}")
    print(f"  Model path      : {MODEL_PATH}")
    print("="*60)
    print("\n✅ Model ready for predictions")


if __name__ == "__main__":
    main()