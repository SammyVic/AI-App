# End-to-End MLOps: House Price Prediction

A production-ready implementation of an MLOps pipeline covering data generation, versioning, tracking, serving, UI, and orchestration.

## 🌟 Architecture & Workflow
Our workflow perfectly aligns with modern ML deployment standards:
**Data → Versioning → Training → Experiment Tracking → Model Registry → Deployment → Monitoring**

For visual diagrams, see `docs/architecture.md`.

## 🛠 Prerequisites
Ensure you have Python 3.9+ and pip installed. Node.js is required if you wish to run n8n locally.

## 🚀 Step-by-Step Beginner Guide

### Step 1: Environment Setup
1. Open your terminal in this repository.
2. Install pip requirements:
   ```bash
   pip install -r requirements.txt
   ```
   **Theory**: This installs all libraries required (FastAPI for web servers, MLflow for tracking, Streamlit for UI, etc).

### Step 2: Initialize Git and DVC
   ```bash
   git init
   dvc init
   git commit -m "Initialize Git and DVC"
   ```
   **Advantage**: DVC keeps track of our large csv generated files without bloating GitHub repositories.

### Step 3: Data Generation
   ```bash
   python src/data_generator.py
   ```
   **Expected Output**: A `data/dataset.csv` file containing 1000 rows of synthetic housing data.

### Step 4: Add Data to Versioning
   ```bash
   dvc add data/dataset.csv
   git add data/dataset.csv.dvc data/.gitignore
   git commit -m "Track dataset"
   ```

### Step 5: Training and Experiment Tracking (MLflow)
   ```bash
   python src/train.py
   ```
   **Expected Output**: The model will train. MLflow will create `mlflow.db` and an `mlruns` directory saving the metrics and the `.pkl` model.
   **Theory**: Tracking ensures that we can look back and find exactly which parameters generated our best accuracy.

### Step 6: Serve the Model using FastAPI
   ```bash
   uvicorn api.app:app --reload
   ```
   **Expected Output**: A web server starts on `http://127.0.0.1:8000`. You can visit `http://127.0.0.1:8000/docs` to see the API swagger documentation and test the `/predict` route.
   Keep this terminal open!

### Step 7: Launch the Streamlit Interface
   In a **new terminal tab**:
   ```bash
   streamlit run app/ui.py
   ```
   **Expected Output**: Your web browser opens to a sleek frontend application where you can drag sliders to configure a house and dynamically get its price via the FastAPI server running in Step 6.

### Step 8: Automation using n8n (Optional Orchestration)
   You can install n8n using Node.js:
   ```bash
   npm install -g n8n
   n8n
   ```
   Navigate to `localhost:5678`. Import the JSON available at `n8n/workflow.json` to see how the entire training and deployment process can be scheduled and automated in a drag-and-drop workflow.
