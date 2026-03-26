"""
Data Generation Module

Theory:
To train a machine learning model, we first need data. In a real-world scenario, this data is 
often collected from various sources (databases, APIs, logs).
For this project, we are generating synthetic tabular data that mimics house features and their corresponding prices.
This step ensures we have a predictable and reproducible dataset to demonstrate the MLOps workflow.

Advantage:
Generating synthetic data allows us to quickly bootstrap the project without worrying about data privacy or complex data fetching logic.
"""

import pandas as pd
import numpy as np
import os

def generate_data(num_samples=1000, output_path='data/dataset.csv'):
    """
    Generates synthetic house price data.
    """
    np.random.seed(42)
    
    # Generate features
    size_sqft = np.random.normal(1500, 500, num_samples)
    bedrooms = np.random.randint(1, 6, num_samples)
    age_years = np.random.randint(0, 50, num_samples)
    distance_to_center = np.random.normal(10, 5, num_samples)
    
    # Generate target variable (price) with some noise
    # Base price + size factor + bedroom factor - age factor - distance factor + noise
    price = (50000 + 
             (size_sqft * 150) + 
             (bedrooms * 20000) - 
             (age_years * 1000) - 
             (distance_to_center * 2000) + 
             np.random.normal(0, 20000, num_samples))
             
    # Create DataFrame
    df = pd.DataFrame({
        'SizeSqft': size_sqft,
        'Bedrooms': bedrooms,
        'AgeYears': age_years,
        'DistanceToCenter': distance_to_center,
        'Price': price
    })
    
    # Ensure no negative prices or features
    df = df[df['Price'] > 0]
    df = df[df['SizeSqft'] > 0]
    df = df[df['DistanceToCenter'] > 0]
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"Dataset generated successfully at {output_path} with {len(df)} records.")

if __name__ == "__main__":
    generate_data()
