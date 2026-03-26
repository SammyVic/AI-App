# House Price Prediction MLOps Pipeline 🏠
---
## Slide 1: Introduction
**Goal**: Build a Production-Ready Machine Learning pipeline to predict house prices using tabular data.

**Key Tools & Technologies**:
- **Data & Training**: `pandas`, `scikit-learn`
- **Experiment Tracking & Registry**: `MLflow`
- **Data Versioning**: `DVC`, `Git`
- **Deployment**: `FastAPI`, `uvicorn`
- **User Interface**: `Streamlit`
- **Orchestration**: `n8n`, `Node.js`

---
## Slide 2: Workflow & Architecture
Our complete workflow ensures reproducibility, scalability, and ease of monitoring.

**Pipeline Flow**:
`Data → Versioning → Training → Experiment Tracking → Model Registry → Deployment → Monitoring`

**Why MLOps?**
- Eliminates the "it works on my machine" problem.
- Automatically tracks hyperparameters (e.g., Random Forest `max_depth`).
- Triggers retraining when new data arrives automatically via n8n.

---
## Slide 3: Data Versioning (DVC)
### Theory
Just like Git tracks code, DVC (Data Version Control) tracks large datasets. We save the `.dvc` mapping files in Git, while the actual CSVs are stored in external storage or locally ignored by git.

### Code Highlights
```bash
# Initialize DVC
dvc init
# Add dataset to DVC tracking
dvc add data/dataset.csv
# Commit the DVC tracking file to Git
git add data/dataset.csv.dvc data/.gitignore
git commit -m "Add raw dataset"
```

---
## Slide 4: Training & Experiment Tracking (MLflow)
### Theory
Experiment Tracking logs all models, their metrics (RMSE, MAE), and the parameters used. This way, the best model can be deployed easily.

### Python Code
```python
import mlflow
import mlflow.sklearn

with mlflow.start_run():
    rf = RandomForestRegressor(n_estimators=100)
    rf.fit(X_train, y_train)
    
    mlflow.log_metric("rmse", rmse_val)
    mlflow.sklearn.log_model(rf, "model")
```

---
## Slide 5: Model Deployment (FastAPI)
### Theory
FastAPI wraps our Python code in a web server, allowing other apps to request predictions over the network via HTTP POST methods.

### Key Points
- Loaded on Startup: `model = mlflow.sklearn.load_model(...)`
- Validation: Uses `Pydantic` to ensure input data types are correct (e.g. `SizeSqft: float`).

---
## Slide 6: Visualizing with Streamlit
### Theory
Streamlit provides a beautiful dashboard for users to interact with our API. It acts as the bridge during the monitoring and usage phase.

### Expected Output
Users input features (Bedrooms, Age, Size, Distance) and click "Predict Price". The API responds with the estimated value (e.g., `$350,000`).

---
## Slide 7: Automation with n8n
### Theory
n8n orchestrates our workflow by connecting steps together visually. We run commands from a scheduler to fetch data, track it, and train the model automatically!
