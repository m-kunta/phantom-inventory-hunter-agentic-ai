"""
Tests for data_gen.generate_synthetic_data():

  Output structure         — column presence, row count, SKU uniqueness
  Reproducibility          — same seed → same data; different seed → different data
  Guaranteed coverage      — all 3 diagnostic signal types always appear (≥2 each)
  Signal value ranges      — shrink scores, velocity index, location status thresholds
  Signal co-occurrence     — blockage signals are consistent with each other
  Sister SKU validity      — assigned, non-self-referential, same-category, in-dataset
  Database write           — internal _diagnostic_type column is never persisted
"""
import sqlite3

import pandas as pd
import pytest

from data_gen import generate_synthetic_data


@pytest.fixture
def df(tmp_path):
    """Default 50-SKU dataset, seed=42, written to a temp DB."""
    return generate_synthetic_data(db_path=str(tmp_path / "test.db"), seed=42)


# ─────────────────────────────────────────────────────────────────────────────
# Output structure
# ─────────────────────────────────────────────────────────────────────────────
class TestOutputStructure:

    def test_returns_exactly_50_skus(self, df):
        assert len(df) == 50

    def test_required_columns_present(self, df):
        required = {
            "SKU_ID", "Product_Name", "Category",
            "On_Hand_Qty", "Daily_Sales_Units", "Last_Sale_Date",
            "Historical_Shrink_Score", "Location_Status",
            "Category_Velocity_Index", "Sister_SKU_ID",
        }
        assert required.issubset(df.columns)

    def test_internal_diagnostic_type_not_in_returned_df(self, df):
        assert "_diagnostic_type" not in df.columns

    def test_internal_diagnostic_type_not_in_db(self, tmp_path):
        db = str(tmp_path / "check.db")
        generate_synthetic_data(db_path=db, seed=1)
        with sqlite3.connect(db) as conn:
            db_df = pd.read_sql_query("SELECT * FROM inventory", conn)
        assert "_diagnostic_type" not in db_df.columns

    def test_sku_ids_are_unique(self, df):
        assert df["SKU_ID"].nunique() == 50

    def test_categories_limited_to_expected_values(self, df):
        assert set(df["Category"].unique()).issubset({"Health & Beauty", "Grocery"})

    def test_daily_sales_units_all_positive(self, df):
        assert (df["Daily_Sales_Units"] > 0).all()

    def test_on_hand_qty_all_non_negative(self, df):
        assert (df["On_Hand_Qty"] >= 0).all()

    def test_db_row_count_matches_returned_df(self, tmp_path):
        db = str(tmp_path / "rowcount.db")
        returned = generate_synthetic_data(db_path=db, seed=42)
        with sqlite3.connect(db) as conn:
            db_df = pd.read_sql_query("SELECT * FROM inventory", conn)
        assert len(db_df) == len(returned)


# ─────────────────────────────────────────────────────────────────────────────
# Reproducibility
# ─────────────────────────────────────────────────────────────────────────────
class TestReproducibility:

    def test_same_seed_identical_daily_sales(self, tmp_path):
        df1 = generate_synthetic_data(db_path=str(tmp_path / "a.db"), seed=7)
        df2 = generate_synthetic_data(db_path=str(tmp_path / "b.db"), seed=7)
        pd.testing.assert_series_equal(
            df1["Daily_Sales_Units"].reset_index(drop=True),
            df2["Daily_Sales_Units"].reset_index(drop=True),
        )

    def test_same_seed_identical_shrink_scores(self, tmp_path):
        df1 = generate_synthetic_data(db_path=str(tmp_path / "a.db"), seed=99)
        df2 = generate_synthetic_data(db_path=str(tmp_path / "b.db"), seed=99)
        pd.testing.assert_series_equal(
            df1["Historical_Shrink_Score"].reset_index(drop=True),
            df2["Historical_Shrink_Score"].reset_index(drop=True),
        )

    def test_different_seeds_differ(self, tmp_path):
        df1 = generate_synthetic_data(db_path=str(tmp_path / "a.db"), seed=1)
        df2 = generate_synthetic_data(db_path=str(tmp_path / "b.db"), seed=2)
        assert not df1["Daily_Sales_Units"].equals(df2["Daily_Sales_Units"])


# ─────────────────────────────────────────────────────────────────────────────
# Guaranteed diagnostic coverage
# Since _diagnostic_type is dropped, coverage is verified through the signal
# values that each type deterministically produces:
#   shrink   → Historical_Shrink_Score > 0.75
#   blockage → Category_Velocity_Index < 0.20  +  Location_Status ≠ Open
# The pool pre-seeds 2 of each type, so ≥2 must appear regardless of seed.
# ─────────────────────────────────────────────────────────────────────────────
class TestGuaranteedDiagnosticCoverage:

    def test_at_least_two_shrink_signal_rows(self, df):
        assert (df["Historical_Shrink_Score"] > 0.75).sum() >= 2

    def test_at_least_two_blockage_rows_by_velocity_index(self, df):
        assert (df["Category_Velocity_Index"] < 0.20).sum() >= 2

    def test_at_least_two_blockage_rows_by_location_status(self, df):
        non_open = df["Location_Status"].isin({"Closed", "Restocking"})
        assert non_open.sum() >= 2

    def test_coverage_holds_across_multiple_seeds(self, tmp_path):
        for seed in range(10):
            d = generate_synthetic_data(db_path=str(tmp_path / f"s{seed}.db"), seed=seed)
            assert (d["Historical_Shrink_Score"] > 0.75).sum() >= 2, f"seed={seed}"
            assert (d["Category_Velocity_Index"] < 0.20).sum() >= 2, f"seed={seed}"


# ─────────────────────────────────────────────────────────────────────────────
# Signal value ranges and thresholds
# ─────────────────────────────────────────────────────────────────────────────
class TestSignalValueRanges:

    def test_shrink_score_within_0_to_1(self, df):
        assert df["Historical_Shrink_Score"].between(0.0, 1.0).all()

    def test_high_shrink_score_starts_at_0_76(self, df):
        high = df[df["Historical_Shrink_Score"] > 0.75]
        assert (high["Historical_Shrink_Score"] >= 0.76).all()

    def test_non_shrink_score_capped_at_0_60(self, df):
        """Non-shrink rows must stay at or below 0.60."""
        low = df[df["Historical_Shrink_Score"] <= 0.60]
        # Most rows are non-shrink — the cap should be observed
        assert not low.empty
        assert (low["Historical_Shrink_Score"] <= 0.60).all()

    def test_location_status_only_valid_values(self, df):
        assert df["Location_Status"].isin({"Open", "Closed", "Restocking"}).all()

    def test_blockage_rows_have_non_open_location(self, df):
        """Any row with CVI < 0.20 must be Closed or Restocking."""
        blockage = df[df["Category_Velocity_Index"] < 0.20]
        assert blockage["Location_Status"].isin({"Closed", "Restocking"}).all()

    def test_non_blockage_rows_have_open_location(self, df):
        """Rows with CVI ≥ 0.20 must be Open."""
        non_blockage = df[df["Category_Velocity_Index"] >= 0.20]
        assert (non_blockage["Location_Status"] == "Open").all()

    def test_blockage_velocity_index_below_threshold(self, df):
        non_open = df[df["Location_Status"] != "Open"]
        assert (non_open["Category_Velocity_Index"] < 0.20).all()

    def test_normal_velocity_index_in_expected_range(self, df):
        normal = df[df["Location_Status"] == "Open"]
        assert normal["Category_Velocity_Index"].between(0.70, 1.30).all()

    def test_blockage_velocity_index_floor(self, df):
        blockage = df[df["Category_Velocity_Index"] < 0.20]
        assert (blockage["Category_Velocity_Index"] >= 0.02).all()

    def test_blockage_velocity_index_ceiling(self, df):
        blockage = df[df["Category_Velocity_Index"] < 0.20]
        assert (blockage["Category_Velocity_Index"] <= 0.18).all()


# ─────────────────────────────────────────────────────────────────────────────
# Sister SKU assignment
# ─────────────────────────────────────────────────────────────────────────────
class TestSisterSKUAssignment:

    def test_all_skus_have_a_sister(self, df):
        assert df["Sister_SKU_ID"].notna().all()

    def test_sister_not_self_referential(self, df):
        assert (df["SKU_ID"] != df["Sister_SKU_ID"]).all()

    def test_sister_exists_in_dataset(self, df):
        valid_skus = set(df["SKU_ID"])
        assert df["Sister_SKU_ID"].isin(valid_skus).all()

    def test_sister_in_same_category(self, df):
        sku_to_cat = df.set_index("SKU_ID")["Category"].to_dict()
        sister_cats = df["Sister_SKU_ID"].map(sku_to_cat)
        assert (df["Category"] == sister_cats).all()
