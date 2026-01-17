"""
================================================================================
  Phantom Inventory Hunter — Root Cause Agent
================================================================================
  Author:      Mohith Kunta
  GitHub:      https://github.com/m-kunta
  Description: Triangulation Engine to pre-analyze and classify Phantom
               Inventory signals before sending structured payloads to the LLM.
================================================================================
"""

import math
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any
from llm_providers import get_llm_response


@dataclass
class TriangulationResult:
    """Structured output from the Triangulation Engine."""
    flag: str
    sister_sales_ratio: float
    category_velocity_ratio: float
    shrink_score: float
    explanation: str


def run_triangulation(sku_row: pd.Series, full_df: pd.DataFrame) -> TriangulationResult:
    """
    Applies heuristic decision trees to classify the root cause of the anomaly.
    Prioritizes store-wide/category anomalies first, then product-specific ones.

    Args:
        sku_row: A pandas Series representing the flagged SKU.
        full_df: The complete inventory DataFrame (used to calculate category metrics
                 and retrieve sister SKU data).

    Returns:
        TriangulationResult predicting the root cause (SHELF_VOID,
        OPERATIONAL_BLOCKAGE, SHRINK_RISK, or NORMAL).
    """
    # 1. Retrieve essential static fields
    category = sku_row.get("Category", "")
    sister_sku_id = sku_row.get("Sister_SKU_ID")
    category_velocity_index = float(sku_row.get("Category_Velocity_Index", 1.0))
    shrink_score = float(sku_row.get("Historical_Shrink_Score", 0.0))

    # 2. Compute Sister Sales Ratio (V_subs proxy)
    # We compare the sister's daily sales against the category average daily sales.
    sister_sales_ratio = 1.0
    if sister_sku_id and not full_df.empty:
        # Compute category mean excluding the phantom SKU itself.
        # Including it would deflate the mean (it has 0 sales), artificially
        # inflating the sister ratio and producing false SHELF_VOID positives.
        sku_id = sku_row.get("SKU_ID", None)
        cat_mask = (full_df["Category"] == category) & (full_df["SKU_ID"] != sku_id)
        cat_mean = full_df.loc[cat_mask, "Daily_Sales_Units"].mean()

        # Guard against NaN (e.g. single-SKU category, all-zero peers, or empty mask).
        if not (math.isnan(cat_mean) if isinstance(cat_mean, float) else False) and cat_mean > 0:
            sister_row_df = full_df[full_df["SKU_ID"] == sister_sku_id]
            if not sister_row_df.empty:
                sister_sales = float(sister_row_df.iloc[0].get("Daily_Sales_Units", 0.0))
                sister_sales_ratio = sister_sales / cat_mean

    # 3. Apply Heuristics in Priority Order

    # Priority A: Store/Category Blockage
    if category_velocity_index < 0.20:
        return TriangulationResult(
            flag="OPERATIONAL_BLOCKAGE",
            sister_sales_ratio=round(sister_sales_ratio, 2),
            category_velocity_ratio=round(category_velocity_index, 2),
            shrink_score=round(shrink_score, 2),
            explanation="Category sales have halted (<20% of baseline). Likely an aisle closure or reset."
        )

    # Priority B: Physical Shelf Void / Substitution
    if sister_sales_ratio > 1.20:
        return TriangulationResult(
            flag="SHELF_VOID",
            sister_sales_ratio=round(sister_sales_ratio, 2),
            category_velocity_ratio=round(category_velocity_index, 2),
            shrink_score=round(shrink_score, 2),
            explanation="Sister SKU showing a >20% sales spike. Customers are substituting due to empty shelf."
        )

    # Priority C: Inventory Inaccuracy or Theft
    if shrink_score > 0.75:
        return TriangulationResult(
            flag="SHRINK_RISK",
            sister_sales_ratio=round(sister_sales_ratio, 2),
            category_velocity_ratio=round(category_velocity_index, 2),
            shrink_score=round(shrink_score, 2),
            explanation="High historical theft/loss risk. Strong potential for Organized Retail Crime or system error."
        )

    # Priority D: Default / Normal Anomaly
    return TriangulationResult(
        flag="NORMAL",
        sister_sales_ratio=round(sister_sales_ratio, 2),
        category_velocity_ratio=round(category_velocity_index, 2),
        shrink_score=round(shrink_score, 2),
        explanation="Anomaly detected, but no extreme multi-signal correlation found."
    )


def build_diagnostic_payload(sku_row: pd.Series, result: TriangulationResult) -> Dict[str, Any]:
    """
    Transforms the raw DataFrame row and triangulation result into a clean,
    structured JSON-serializable dictionary for grounding the LLM.
    """
    expected_freq = 999.0
    daily_sales = float(sku_row.get("Daily_Sales_Units", 0.0))
    if daily_sales > 0:
        expected_freq = 1.0 / daily_sales

    return {
        "sku_id": str(sku_row.get("SKU_ID", "")),
        "product_name": str(sku_row.get("Product_Name", "")),
        "on_hand_qty": int(sku_row.get("On_Hand_Qty", 0)),
        "days_since_last_sale": int(sku_row.get("Days_Since_Last_Sale", 0)),
        "expected_frequency_days": round(expected_freq, 2),
        "diagnostic_flag": result.flag,
        "sister_sku_id": str(sku_row.get("Sister_SKU_ID", "")),
        "sister_sales_ratio": result.sister_sales_ratio,
        "category_velocity_index": result.category_velocity_ratio,
        "historical_shrink_score": result.shrink_score,
        "location_status": str(sku_row.get("Location_Status", "Open"))
    }


def generate_root_cause_briefing(sku_row: pd.Series, full_df: pd.DataFrame, provider: str, model: str) -> str:
    """
    Orchestrates the Triangulation Engine and requests a specialized Store Audit Briefing
    from the selected LLM. Replaces the generic prompt in app.py.

    Args:
        sku_row: A pandas Series row for the flagged Phantom item.
        full_df: The complete inventory DataFrame.
        provider: 'Gemini', 'OpenAI', etc.
        model: Example: 'gemini-2.5-flash'

    Returns:
        Structured Store Audit Briefing text from the LLM.
    """
    # 1. Run analysis
    result = run_triangulation(sku_row, full_df)

    # 2. Build structured payload
    payload = build_diagnostic_payload(sku_row, result)

    # 3. Formulate the focused prompt
    prompt = f"""
Act as a Senior Category Management Consultant. Analyze the following diagnostic payload for a "Phantom Inventory" event. 
We have pre-analyzed the anomaly and classified it with a specific `diagnostic_flag`.

DIAGNOSTIC PAYLOAD:
{payload}

TASK:
Write a "Situation -> Action" briefing for store floor associates.
- Situation: Explain the anomaly, specifically referencing the `diagnostic_flag` and its supporting evidence (e.g. sister sales spike, category deadness, or high shrink).
- Action: Give 2-3 highly specific, prioritized physical actions the store associate must take to resolve this specific category of problem.

CONSTRAINT:
Maintain a professional, concise tone. Maximum 200 words. Do not use generic advice.
"""

    return get_llm_response(prompt, provider, model)
