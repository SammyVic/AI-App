"""
Streamlit User Interface

Theory:
Streamlit is an open-source app framework for Machine Learning and Data Science teams.
It provides a quick way to build interactive web applications for our models without needing 
extensive frontend development experience (HTML/CSS/JS).

Advantage:
- Rapid prototyping of user interfaces.
- End-users can easily interact with the model by inserting house features and visually seeing the outcome.

Expected Output:
When you run `streamlit run app/ui.py`, a browser window will open automatically displaying the user interface.
You can enter mock sizes, bedrooms, etc., and see the corresponding price prediction retrieved from the FastAPI backend.
"""

import streamlit as st
import requests

# FastAPI endpoint URL
API_URL = "http://localhost:8000/predict"

st.set_page_config(page_title="House Price Predictor", page_icon="🏠", layout="centered")

st.title("🏠 House Price Prediction System")
st.markdown("""
This application predicts the price of a house based on its features. 
It sends the input data to a **FastAPI backend** which hosts our trained and deployed **RandomForest model**.
""")

# Input section
st.header("House Features")

col1, col2 = st.columns(2)

with col1:
    size_sqft = st.number_input("Size (Square Feet)", min_value=100.0, max_value=10000.0, value=1500.0, step=50.0)
    bedrooms = st.number_input("Number of Bedrooms", min_value=1, max_value=10, value=3, step=1)

with col2:
    age_years = st.number_input("Age of House (Years)", min_value=0, max_value=150, value=10, step=1)
    distance_to_center = st.number_input("Distance to City Center (Miles)", min_value=0.0, max_value=100.0, value=10.0, step=1.0)

if st.button("Predict Price", type="primary"):
    payload = {
        "SizeSqft": size_sqft,
        "Bedrooms": bedrooms,
        "AgeYears": age_years,
        "DistanceToCenter": distance_to_center
    }
    
    with st.spinner("Predicting..."):
        try:
            response = requests.post(API_URL, json=payload)
            if response.status_code == 200:
                result = response.json()
                predicted_price = result["predicted_price"]
                st.success(f"### Predicted Price: **${predicted_price:,.2f}**")
                st.balloons()
            else:
                st.error(f"Error from API: {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("⚠️ Failed to connect to the backend API. Please make sure the FastAPI server is running (`uvicorn api.app:app --reload`).")

st.markdown("---")
st.markdown("### Workflow Step: Monitoring & UI")
st.markdown("""
- **Data Source**: User Input via UI
- **Process**: Makes HTTP POST request to API Route (`/predict`)
- **Action**: Model Predicts on new data
""")
