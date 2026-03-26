"""
Training Module integrated with MLflow

Theory:
This script performs data loading, preprocessing, model training, and evaluation.
We use MLflow for Experiment Tracking. Experiment Tracking is the process of saving all experiment-related 
information (parameters, metrics, models, etc.) so that you can reproduce them and compare different runs.

Advantage:
- Reproducibility: Knowing exactly what data and parameters produced a model.
- Model Registry: MLflow allows us to store the resulting model artifacts to easily load them later in our API.

Expected Output:
When you run this script, it will train a model, output the evaluation metrics (RMSE, MAE, R2) to the console, 
and create/update an MLflow tracking database (`mlflow.db`) and an `mlruns` directory containing the model artifacts.
"""

import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import os

# Set MLflow tracking URI to a local directory Database
# We use SQLite to make it easy to query and avoid heavy setup
mlflow.set_tracking_uri("sqlite:///mlflow.db")
# Set the experiment name
mlflow.set_experiment("House_Price_Prediction")

def eval_metrics(actual, pred):
    rmse = np.sqrt(mean_squared_error(actual, pred))
    mae = mean_absolute_error(actual, pred)
    r2 = r2_score(actual, pred)
    return rmse, mae, r2

def train_model(data_path='data/dataset.csv', n_estimators=100, max_depth=None):
    print("Loading data...")
    try:
        data = pd.read_csv(data_path)
    except Exception as e:
        print(f"Error loading data: {e}. Please run data_generator.py first.")
        return

    # Split data into features and target
    X = data.drop('Price', axis=1)
    y = data['Price']

    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Start an MLflow run
    with mlflow.start_run():
        print("Training model...")
        rf = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        rf.fit(X_train, y_train)

        # Make predictions
        predictions = rf.predict(X_test)

        # Evaluate model
        (rmse, mae, r2) = eval_metrics(y_test, predictions)

        print(f"RandomForest model (n_estimators={n_estimators}, max_depth={max_depth}):")
        print(f"  RMSE: {rmse}")
        print(f"  MAE: {mae}")
        print(f"  R2: {r2}")

        # Log parameters
        mlflow.log_param("n_estimators", n_estimators)
        if max_depth is not None:
            mlflow.log_param("max_depth", max_depth)

        # Log metrics
        mlflow.log_metric("rmse", rmse)
        mlflow.log_metric("mae", mae)
        mlflow.log_metric("r2", r2)

        # Log the model specifically so we can load it later
        mlflow.sklearn.log_model(rf, "model")
        
        print("Model training complete and logged to MLflow.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--max-depth", type=int, default=None)
    args = parser.parse_args()
    
    # Ensure current working directory is the project root to find data/dataset.csv
    train_model(n_estimators=args.n_estimators, max_depth=args.max_depth)
