"""
Tests for root_cause_agent.py:
  Triangulation heuristics — OPERATIONAL_BLOCKAGE, SHELF_VOID, SHRINK_RISK, NORMAL
  Payload generation       — formatting for the LLM prompt
  Orchestration function   — end-to-end payload routing
"""

import pandas as pd
import pytest
from unittest.mock import patch
from root_cause_agent import (
    TriangulationResult,
    run_triangulation,
    build_diagnostic_payload,
    generate_root_cause_briefing
)


@pytest.fixture
def base_df():
    """Provides a basic synthetic DataFrame tailored for targeted heuristic testing."""
    return pd.DataFrame([
        {
            "SKU_ID": "TGT",
            "Product_Name": "Target SKU",
            "Category": "Grocery",
            "Daily_Sales_Units": 0.0,
            "On_Hand_Qty": 10,
            "Days_Since_Last_Sale": 10,
            "Sister_SKU_ID": "SIS",
            "Category_Velocity_Index": 1.0,  # Normal
            "Historical_Shrink_Score": 0.1,  # Normal
            "Location_Status": "Open"
        },
        {
            "SKU_ID": "SIS",
            "Product_Name": "Sister SKU",
            "Category": "Grocery",
            "Daily_Sales_Units": 2.0,  # e.g., double the category average
            "On_Hand_Qty": 50,
            "Days_Since_Last_Sale": 1,
            "Sister_SKU_ID": "TGT",
            "Category_Velocity_Index": 1.0,
            "Historical_Shrink_Score": 0.1,
            "Location_Status": "Open"
        },
        {
            "SKU_ID": "OTH",
            "Product_Name": "Other SKU",
            "Category": "Grocery",
            "Daily_Sales_Units": 1.0,  # this brings category average to: (0+2+1)/3 = 1.0
            "On_Hand_Qty": 20,
            "Days_Since_Last_Sale": 2,
            "Sister_SKU_ID": "SIS",
            "Category_Velocity_Index": 1.0,
            "Historical_Shrink_Score": 0.1,
            "Location_Status": "Open"
        }
    ])


class TestCategoryBlockage:
    def test_blockage_takes_priority(self, base_df):
        df = base_df.copy()
        # Force a state where BOTH blockage and shelf_void apply
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]
        df.at[tgt_idx, 'Category_Velocity_Index'] = 0.10 # < 0.20 Threshold
        # Sister daily sales is 2.0, Cat avg is 1.0, ratio is 2.0 > 1.20

        sku_row = df.loc[tgt_idx]
        result = run_triangulation(sku_row, df)
        
        assert result.flag == "OPERATIONAL_BLOCKAGE"
        assert result.category_velocity_ratio == 0.10
        assert "Category sales have halted" in result.explanation


class TestSubstitutionDetection:
    def test_shelf_void_triggered_by_sister_spike(self, base_df):
        df = base_df.copy()
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]

        # D-1 fix: TGT (Daily_Sales=0) is EXCLUDED from the category mean.
        # Peers: SIS=2.0, OTH=1.0  →  cat_mean = (2.0 + 1.0) / 2 = 1.5
        # sister_sales_ratio = 2.0 / 1.5 ≈ 1.33  (still > 1.20, SHELF_VOID triggered)
        sku_row = df.loc[tgt_idx]
        result = run_triangulation(sku_row, df)

        assert result.flag == "SHELF_VOID"
        assert result.sister_sales_ratio == pytest.approx(1.33, abs=0.01)
        assert "Customers are substituting" in result.explanation

    def test_no_shelf_void_if_ratio_low(self, base_df):
        df = base_df.copy()
        sis_idx = df.index[df['SKU_ID'] == 'SIS'][0]
        # Lower sister sales down to exactly category average
        df.at[sis_idx, 'Daily_Sales_Units'] = 1.0
        # New Cat Avg = (0 + 1 + 1)/3 = 0.66
        # Ratio = 1.0 / 0.66 = 1.5 -> Still big enough. Let's make sister 0.5.
        df.at[sis_idx, 'Daily_Sales_Units'] = 0.5
        # Cat Avg = (0 + 0.5 + 1)/3 = 0.5
        # Ratio = 0.5 / 0.5 = 1.0 < 1.20
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]
        sku_row = df.loc[tgt_idx]
        result = run_triangulation(sku_row, df)

        assert result.flag != "SHELF_VOID"


class TestShrinkAnomaly:
    def test_shrink_risk_triggered_by_high_score(self, base_df):
        df = base_df.copy()
        sis_idx = df.index[df['SKU_ID'] == 'SIS'][0]
        df.at[sis_idx, 'Daily_Sales_Units'] = 0.5 # kill the sister spike (1.0 ratio)
        
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]
        df.at[tgt_idx, 'Historical_Shrink_Score'] = 0.85 # > 0.75 threshold
        
        sku_row = df.loc[tgt_idx]
        result = run_triangulation(sku_row, df)
        
        assert result.flag == "SHRINK_RISK"
        assert result.shrink_score == 0.85
        assert "theft/loss risk" in result.explanation

class TestNormalCase:
    def test_normal_when_no_thresholds_met(self, base_df):
        df = base_df.copy()
        sis_idx = df.index[df['SKU_ID'] == 'SIS'][0]
        df.at[sis_idx, 'Daily_Sales_Units'] = 0.5 # kill sister spike
        
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]
        sku_row = df.loc[tgt_idx]
        # At this point: CVI=1.0, Shrink=0.1, Ratio=1.0
        result = run_triangulation(sku_row, df)
        
        assert result.flag == "NORMAL"


class TestBuildDiagnosticPayload:
    def test_payload_structure_matches_spec(self, base_df):
        sku_row = base_df.loc[base_df.index[base_df['SKU_ID'] == 'TGT'][0]].copy()
        # Force Some Daily Sales so expected frequency is 1 / 0.4 = 2.5
        sku_row['Daily_Sales_Units'] = 0.4
        
        result = TriangulationResult(
            flag="SHELF_VOID",
            sister_sales_ratio=1.45,
            category_velocity_ratio=0.91,
            shrink_score=0.31,
            explanation="Test explanation."
        )
        payload = build_diagnostic_payload(sku_row, result)
        
        assert payload["sku_id"] == "TGT"
        assert payload["product_name"] == "Target SKU"
        assert payload["on_hand_qty"] == 10
        assert payload["days_since_last_sale"] == 10
        assert payload["expected_frequency_days"] == 2.5
        assert payload["diagnostic_flag"] == "SHELF_VOID"
        assert payload["sister_sku_id"] == "SIS"
        assert payload["sister_sales_ratio"] == 1.45
        assert payload["category_velocity_index"] == 0.91
        assert payload["historical_shrink_score"] == 0.31
        assert payload["location_status"] == "Open"


class TestGenerateRootCauseBriefing:
    @patch('root_cause_agent.get_llm_response')
    def test_briefing_delegates_to_llm_factory(self, mock_llm, base_df):
        mock_llm.return_value = "Mocked Model Output"

        tgt_idx = base_df.index[base_df['SKU_ID'] == 'TGT'][0]
        sku_row = base_df.loc[tgt_idx]

        response = generate_root_cause_briefing(sku_row, base_df, "MockProvider", "mock-model")

        assert response == "Mocked Model Output"
        mock_llm.assert_called_once()

        # Verify prompt construction includes the flag and payload string representation
        prompt_arg = mock_llm.call_args[0][0]
        assert "Senior Category Management Consultant" in prompt_arg
        assert "SHELF_VOID" in prompt_arg  # base_df sister ratio = 2.0


# ─────────────────────────────────────────────────────────────────────────────
# Boundary conditions  (D-4)
# ─────────────────────────────────────────────────────────────────────────────
class TestBoundaryConditions:
    """Verify that thresholds are strictly exclusive (>, not >=)."""

    def test_sister_ratio_exactly_at_threshold_is_not_shelf_void(self, base_df):
        """Ratio == 1.20 must NOT trigger SHELF_VOID (rule is ratio > 1.20)."""
        df = base_df.copy()
        sis_idx = df.index[df['SKU_ID'] == 'SIS'][0]
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]

        # After the D-1 fix the cat_mean excludes TGT (Daily_Sales=0).
        # Peers are SIS and OTH. Set them so ratio == 1.20 exactly.
        # cat_mean (excl. TGT) = mean(SIS, OTH). Set OTH=1.0, SIS=1.20*mean => iteratively:
        # cat_mean = (sis + 1.0) / 2; ratio = sis / cat_mean = 1.20
        # => sis = 1.20 * (sis + 1.0) / 2  => 2*sis = 1.20*sis + 1.20
        # => 0.80*sis = 1.20 => sis = 1.5, cat_mean = (1.5+1.0)/2 = 1.25, ratio = 1.5/1.25 = 1.20
        df.at[sis_idx, 'Daily_Sales_Units'] = 1.5
        df.at[df.index[df['SKU_ID'] == 'OTH'][0], 'Daily_Sales_Units'] = 1.0

        sku_row = df.loc[tgt_idx]
        result = run_triangulation(sku_row, df)
        assert result.flag != "SHELF_VOID"
        assert result.sister_sales_ratio == pytest.approx(1.20, abs=1e-6)

    def test_shrink_score_exactly_at_threshold_is_not_shrink_risk(self, base_df):
        """Score == 0.75 must NOT trigger SHRINK_RISK (rule is score > 0.75)."""
        df = base_df.copy()
        sis_idx = df.index[df['SKU_ID'] == 'SIS'][0]
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]

        # Kill sister spike so only shrink path is considered
        df.at[sis_idx, 'Daily_Sales_Units'] = 0.5
        df.at[tgt_idx, 'Historical_Shrink_Score'] = 0.75  # boundary — not > 0.75

        sku_row = df.loc[tgt_idx]
        result = run_triangulation(sku_row, df)
        assert result.flag != "SHRINK_RISK"

    def test_phantom_sku_zero_excluded_from_category_mean(self, base_df):
        """
        Regression for D-1: the phantom SKU's own 0-sales row must NOT be included
        in the category mean computation.  Without the fix, including it would lower
        the mean and artificially inflate the sister ratio.
        """
        df = base_df.copy()
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]
        sis_idx = df.index[df['SKU_ID'] == 'SIS'][0]

        # With the fix, cat_mean excludes TGT (0.0).  Peers: SIS=0.8, OTH=1.0.
        # cat_mean = (0.8 + 1.0) / 2 = 0.90  →  ratio = 0.8 / 0.90 ≈ 0.89  (NOT a spike)
        # Without the fix (old code), cat_mean = (0.0 + 0.8 + 1.0) / 3 ≈ 0.60 → ratio ≈ 1.33
        # which would wrongly trigger SHELF_VOID.
        df.at[sis_idx, 'Daily_Sales_Units'] = 0.8
        df.at[df.index[df['SKU_ID'] == 'OTH'][0], 'Daily_Sales_Units'] = 1.0

        sku_row = df.loc[tgt_idx]
        result = run_triangulation(sku_row, df)
        assert result.flag != "SHELF_VOID", (
            "Phantom SKU's own zero must be excluded from cat_mean — "
            f"got sister_sales_ratio={result.sister_sales_ratio:.3f}"
        )

    def test_single_sku_category_does_not_crash(self, base_df):
        """
        Edge case: if all category peers are filtered out (single-SKU cat after
        excluding the phantom itself), cat_mean is NaN. Must return NORMAL, not crash.
        """
        df = base_df.copy()
        # Put TGT in its own unique category; no other SKU shares it.
        tgt_idx = df.index[df['SKU_ID'] == 'TGT'][0]
        df.at[tgt_idx, 'Category'] = 'Unique_Category'

        sku_row = df.loc[tgt_idx]
        # Should not raise; sister_sales_ratio falls back to 1.0
        result = run_triangulation(sku_row, df)
        assert result.sister_sales_ratio == 1.0
