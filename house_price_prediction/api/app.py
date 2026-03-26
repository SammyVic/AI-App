"""
Model Deployment API (FastAPI)

Theory:
FastAPI is a modern, fast web framework for building APIs with Python.
Once a model is trained, it needs to be served so that other applications (like our Streamlit UI or n8n workflow)
can send it data and receive predictions. We wrap our MLflow model inside a FastAPI application.

Advantage:
- High performance and easy to write.
- Automatic interactive API documentation (Swagger UI).
- Standardized access to our machine learning model.

Expected Output:
When you run this script using Uvicorn (`uvicorn api.app:app --reload`), it will start a local server.
You can visit `http://127.0.0.1:8000/docs` to see the automatically generated interactive API documentation and test the `/predict` endpoint.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mlflow.sklearn
import pandas as pd
import os

app = FastAPI(
    title="House Price Prediction API",
    description="API for predicting house prices using a trained RandomForest model.",
    version="1.0.0"
)

# Define the input data schema
class HouseFeatures(BaseModel):
    SizeSqft: float
    Bedrooms: int
    AgeYears: int
    DistanceToCenter: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "SizeSqft": 2000.0,
                "Bedrooms": 3,
                "AgeYears": 10,
                "DistanceToCenter": 5.0
            }
        }
    }

# Global variable to hold the model
model = None

@app.on_event("startup")
def load_model():
    """
    On application startup, this function searches MLflow for the best model and loads it into memory.
    """
    global model
    try:
        # Connect to the local mlflow db and fetch the best run.
        mlflow.set_tracking_uri("sqlite:///mlflow.db")
        client = mlflow.tracking.MlflowClient()
        experiment = client.get_experiment_by_name("House_Price_Prediction")
        
        if experiment:
            # Query runs ordered by lowest RMSE
            runs = client.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=["metrics.rmse ASC"],
                max_results=1
            )
            if runs:
                best_run = runs[0]
                model_uri = f"runs:/{best_run.info.run_id}/model"
                print(f"Loading best model from run: {best_run.info.run_id}")
                model = mlflow.sklearn.load_model(model_uri)
            else:
                print("No runs found in the experiment.")
        else:
            print("Experiment not found. Please train the model first.")
            
    except Exception as e:
        print(f"Failed to load model on startup: {e}")

@app.get("/")
def read_root():
    return {"message": "Welcome to the House Price Prediction API. Go to /docs for Swagger UI."}

@app.post("/predict")
def predict_price(features: HouseFeatures):
    """
    Endpoint that accepts house features and returns a predicted price.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded. Please train a model first.")
        
    try:
        # Convert input dictionary to a pandas DataFrame (which the model expects)
        input_data = pd.DataFrame([features.dict()])
        
        # Make prediction
        prediction = model.predict(input_data)
        
        return {
            "predicted_price": float(prediction[0])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
