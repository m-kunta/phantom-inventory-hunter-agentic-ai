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
    # Seed both RNGs for reproducibility — same seed always produces the same dataset.
    random.seed(seed)
    np.random.seed(seed)

    # Define categories
    categories = ['Health & Beauty', 'Grocery']

    # Generate 50 SKUs
    skus = []

    # Base date is today
    today = datetime.now()

    # Pre-seed the diagnostic type pool so all three root-cause signals are
    # guaranteed to appear at least twice regardless of RNG luck.
    guaranteed_types = ['shelf_void', 'shelf_void', 'blockage', 'blockage', 'shrink', 'shrink']
    random.shuffle(guaranteed_types)
    phantom_type_pool = list(guaranteed_types)

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
            # Pull from the guaranteed pool first so each diagnostic type appears
            # at least twice; fall back to random choice once the pool is exhausted.
            if phantom_type_pool:
                diagnostic_type = phantom_type_pool.pop()
            else:
                diagnostic_type = random.choice(['shelf_void', 'blockage', 'shrink'])
        else:
            # Normal recency
            days_since_last_sale = random.randint(0, int(expected_frequency * 2) + 1)
            diagnostic_type = 'normal'

        last_sale_date = (today - timedelta(days=days_since_last_sale)).strftime('%Y-%m-%d')

        # ── Root Cause Agent fields ────────────────────────────────────────────
        # Historical_Shrink_Score: 0.0–1.0 theft/loss risk rating.
        # Shrink phantoms get a high score (>0.75); all others stay low.
        if diagnostic_type == 'shrink':
            shrink_score = round(random.uniform(0.76, 1.0), 2)
        else:
            shrink_score = round(random.uniform(0.0, 0.60), 2)

        # Location_Status: aisle operational state.
        # Blockage phantoms are Closed or Restocking; everything else is Open.
        if diagnostic_type == 'blockage':
            location_status = random.choice(['Closed', 'Restocking'])
        else:
            location_status = 'Open'

        # Category_Velocity_Index: ratio of current 7-day category sales to baseline.
        # Values < 0.20 signal an Operational Blockage (whole section is dead).
        # Normal range is 0.70–1.30.
        if diagnostic_type == 'blockage':
            category_velocity_index = round(random.uniform(0.02, 0.18), 3)
        else:
            category_velocity_index = round(random.uniform(0.70, 1.30), 3)

        skus.append({
            'SKU_ID': f"SKU{i:03d}",
            'Product_Name': product_name,
            'Category': category,
            'On_Hand_Qty': on_hand,
            'Daily_Sales_Units': daily_sales,
            'Last_Sale_Date': last_sale_date,
            'Historical_Shrink_Score': shrink_score,
            'Location_Status': location_status,
            'Category_Velocity_Index': category_velocity_index,
            '_diagnostic_type': diagnostic_type,   # internal — dropped before DB write
        })

    # Convert to DataFrame
    df = pd.DataFrame(skus)

    # ── Sister SKU assignment ──────────────────────────────────────────────────
    # Each SKU is paired with the closest substitute in the same category.
    # For shelf_void phantoms we prefer a high-sales sister so the triangulation
    # engine can detect the substitution spike (sister_sales_ratio > 1.20).
    df['Sister_SKU_ID'] = None

    for category in categories:
        cat_mask = df['Category'] == category
        cat_skus = df.loc[cat_mask, 'SKU_ID'].tolist()
        cat_mean_sales = df.loc[cat_mask, 'Daily_Sales_Units'].mean()

        for idx, row in df[cat_mask].iterrows():
            if row['_diagnostic_type'] == 'shelf_void':
                # Prefer sisters whose daily sales exceed the category mean so
                # the triangulation engine sees a natural spike ratio.
                high_sales = df.loc[
                    cat_mask &
                    (df['SKU_ID'] != row['SKU_ID']) &
                    (df['Daily_Sales_Units'] > cat_mean_sales),
                    'SKU_ID'
                ].tolist()
                candidates = high_sales if high_sales else [s for s in cat_skus if s != row['SKU_ID']]
            else:
                candidates = [s for s in cat_skus if s != row['SKU_ID']]

            df.at[idx, 'Sister_SKU_ID'] = random.choice(candidates) if candidates else None

    # Drop internal column — not stored in the database
    df = df.drop(columns=['_diagnostic_type'])

    # Persist to SQLite using a context manager so the connection is safely
    # closed even if an exception occurs during the write.
    with sqlite3.connect(db_path) as conn:
        df.to_sql('inventory', conn, if_exists='replace', index=False)

    print(f"✅ Successfully generated data for {len(df)} SKUs (seed={seed}).")
    print(f"💾 Saved to {db_path}")
    return df

if __name__ == "__main__":
    generate_synthetic_data()
