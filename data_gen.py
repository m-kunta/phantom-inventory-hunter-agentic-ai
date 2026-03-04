"""
================================================================================
  Phantom Inventory Hunter — Synthetic Data Engine
================================================================================
  Author:      Mohith Kunta
  GitHub:      https://github.com/m-kunta
  Description: Generates 30 days of synthetic retail inventory data for
               50 SKUs across 'Health & Beauty' and 'Grocery' categories,
               and persists it to a local SQLite database.
  Usage:       python data_gen.py
================================================================================
"""

import pandas as pd
import numpy as np
import sqlite3
import random
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# DATA GENERATION — Synthetic Retail SKU Dataset
# Author: Mohith Kunta | https://github.com/m-kunta
# ─────────────────────────────────────────────────────────────────────────────
def generate_synthetic_data(db_path='phantom_inventory.db', seed: int = 42):
    """
    Generate 30 days of retail data for 50 SKUs and persist to SQLite.

    Args:
        db_path: Path to the SQLite database file.
        seed:    Random seed for reproducible data generation (default: 42).
                 Change this value to generate a different dataset.
    """
    # Seed the RNG for reproducibility — same seed always produces the same dataset.
    random.seed(seed)

    # Define categories
    categories = ['Health & Beauty', 'Grocery']

    # Generate 50 SKUs
    skus = []

    # Base date is today
    today = datetime.now()
    
    for i in range(1, 51):
        category = random.choice(categories)
        if category == 'Health & Beauty':
            product_name = f"H&B Product {i:02d}"
        else:
            product_name = f"Grocery Product {i:02d}"
            
        # Daily sales units (average velocity)
        # e.g., 0.5 means 1 sale every 2 days
        daily_sales = round(random.uniform(0.1, 5.0), 2)
        
        # Current On Hand Quantity
        on_hand = random.randint(0, 100)
        
        # Calculate recency of last sale (Days Since Last Sale)
        # We want to artificially construct scenarios:
        # Scenario 1 (Normal): Days Since Last Sale roughly aligns with expected frequency
        # Scenario 2 (Phantom/Anomaly): High Days Since Last Sale despite having stock
        
        expected_frequency = 1.0 / daily_sales if daily_sales > 0 else 999
        
        is_phantom_candidate = random.random() < 0.25 # 25% chance to be an anomaly
        
        if is_phantom_candidate and on_hand > 0:
            # Force anomalous recency (Phantom Inventory!)
            min_days = int(expected_frequency * 4)
            days_since_last_sale = random.randint(min_days, max(30, min_days + 15))
        else:
            # Normal recency
            days_since_last_sale = random.randint(0, int(expected_frequency * 2) + 1)
            
        last_sale_date = (today - timedelta(days=days_since_last_sale)).strftime('%Y-%m-%d')
        
        skus.append({
            'SKU_ID': f"SKU{i:03d}",
            'Product_Name': product_name,
            'Category': category,
            'On_Hand_Qty': on_hand,
            'Daily_Sales_Units': daily_sales,
            'Last_Sale_Date': last_sale_date
        })
        
    # Convert to DataFrame
    df = pd.DataFrame(skus)

    # Persist to SQLite using a context manager so the connection is safely
    # closed even if an exception occurs during the write.
    with sqlite3.connect(db_path) as conn:
        df.to_sql('inventory', conn, if_exists='replace', index=False)

    print(f"✅ Successfully generated data for {len(df)} SKUs (seed={seed}).")
    print(f"💾 Saved to {db_path}")
    return df

if __name__ == "__main__":
    generate_synthetic_data()
