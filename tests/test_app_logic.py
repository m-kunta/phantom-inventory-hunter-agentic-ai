"""
Tests for pure logic functions extracted from app.py:

  determine_risk()               — phantom severity classification
  color_risk_levels()            — CSS colour string generation
  load_data()                    — SQLite loading + derived-column computation
  generate_store_audit_briefing()— prompt construction + LLM delegation
"""
import sqlite3

import pandas as pd
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

# conftest.py has already injected the streamlit mock into sys.modules before
# this file is collected, so `import app` is safe here.
import app


# ─────────────────────────────────────────────────────────────────────────────
# determine_risk
# ─────────────────────────────────────────────────────────────────────────────
class TestDetermineRisk:
    """
    Algorithm:
        deviation_ratio = Days_Since_Last_Sale / (Expected_Frequency × multiplier)
        Is_Phantom=False  → "Low"
        Is_Phantom=True, ratio < 2  → "Medium"
        Is_Phantom=True, ratio ≥ 2  → "High"
    """

    def _row(self, is_phantom: bool, days: float, freq: float) -> pd.Series:
        return pd.Series(
            {
                "Is_Phantom": is_phantom,
                "Days_Since_Last_Sale": days,
                "Expected_Frequency": freq,
            }
        )

    def test_non_phantom_returns_low(self):
        assert app.determine_risk(self._row(False, 0, 1.0), 3.0) == "Low"

    def test_non_phantom_ignores_extreme_gap(self):
        """Large Days_Since_Last_Sale doesn't matter when Is_Phantom is False."""
        assert app.determine_risk(self._row(False, 9999, 0.1), 1.0) == "Low"

    def test_phantom_deviation_below_2_is_medium(self):
        # ratio = 8 / (5.0 × 1.0) = 1.6 → Medium
        assert app.determine_risk(self._row(True, 8, 5.0), 1.0) == "Medium"

    def test_phantom_deviation_just_below_2_is_medium(self):
        # ratio ≈ 1.998 → still Medium
        assert app.determine_risk(self._row(True, 9.99, 5.0), 1.0) == "Medium"

    def test_phantom_deviation_exactly_2_is_high(self):
        # ratio = 10 / (5.0 × 1.0) = 2.0 — boundary is ≥2, so High
        assert app.determine_risk(self._row(True, 10, 5.0), 1.0) == "High"

    def test_phantom_deviation_above_2_is_high(self):
        # ratio = 30 / (5.0 × 1.0) = 6.0 → High
        assert app.determine_risk(self._row(True, 30, 5.0), 1.0) == "High"

    def test_larger_multiplier_lowers_ratio_to_medium(self):
        # multiplier=5: ratio = 20 / (5.0 × 5.0) = 0.8 → Medium
        assert app.determine_risk(self._row(True, 20, 5.0), 5.0) == "Medium"

    def test_smaller_multiplier_raises_ratio_to_high(self):
        # multiplier=1: ratio = 20 / (5.0 × 1.0) = 4.0 → High
        assert app.determine_risk(self._row(True, 20, 5.0), 1.0) == "High"


# ─────────────────────────────────────────────────────────────────────────────
# color_risk_levels
# ─────────────────────────────────────────────────────────────────────────────
class TestColorRiskLevels:

    def test_high_returns_red(self):
        assert "#ff4b4b" in app.color_risk_levels("High")

    def test_medium_returns_orange(self):
        assert "#ffa421" in app.color_risk_levels("Medium")

    def test_low_returns_green(self):
        assert "#00cc96" in app.color_risk_levels("Low")

    def test_all_known_levels_are_bold(self):
        for level in ("High", "Medium", "Low"):
            assert "font-weight: bold" in app.color_risk_levels(level)

    def test_unknown_value_has_empty_colour(self):
        result = app.color_risk_levels("Critical")
        # color_map.get returns "" for unknown keys → "color: ;"
        assert "color: ;" in result


# ─────────────────────────────────────────────────────────────────────────────
# load_data
# ─────────────────────────────────────────────────────────────────────────────
class TestLoadData:

    def _write_db(self, tmp_path, rows: list[dict]) -> str:
        db = str(tmp_path / "inv.db")
        with sqlite3.connect(db) as conn:
            pd.DataFrame(rows).to_sql("inventory", conn, if_exists="replace", index=False)
        return db

    def _base_row(self, days_ago: int = 5, daily_sales: float = 2.0) -> dict:
        return {
            "SKU_ID": "SKU001",
            "Product_Name": "Widget",
            "Category": "Grocery",
            "On_Hand_Qty": 10,
            "Daily_Sales_Units": daily_sales,
            "Last_Sale_Date": (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
        }

    def test_returns_non_empty_dataframe(self, tmp_path):
        df = app.load_data(self._write_db(tmp_path, [self._base_row()]))
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_derived_column_days_since_last_sale_present(self, tmp_path):
        df = app.load_data(self._write_db(tmp_path, [self._base_row()]))
        assert "Days_Since_Last_Sale" in df.columns

    def test_derived_column_expected_frequency_present(self, tmp_path):
        df = app.load_data(self._write_db(tmp_path, [self._base_row()]))
        assert "Expected_Frequency" in df.columns

    def test_days_since_last_sale_computed_correctly(self, tmp_path):
        df = app.load_data(self._write_db(tmp_path, [self._base_row(days_ago=7)]))
        assert df["Days_Since_Last_Sale"].iloc[0] == 7

    def test_expected_frequency_positive_sales(self, tmp_path):
        # 1 / 4.0 = 0.25
        df = app.load_data(self._write_db(tmp_path, [self._base_row(daily_sales=4.0)]))
        assert df["Expected_Frequency"].iloc[0] == pytest.approx(0.25)

    def test_expected_frequency_zero_sales_returns_sentinel(self, tmp_path):
        df = app.load_data(self._write_db(tmp_path, [self._base_row(daily_sales=0.0)]))
        assert df["Expected_Frequency"].iloc[0] == 999

    def test_missing_table_returns_empty_dataframe(self, tmp_path):
        # Create an empty SQLite file with no tables.
        empty_db = str(tmp_path / "empty.db")
        sqlite3.connect(empty_db).close()
        assert app.load_data(empty_db).empty

    def test_nonexistent_path_returns_empty_dataframe(self, tmp_path):
        # SQLite creates the file but the table is absent → exception → empty df.
        assert app.load_data(str(tmp_path / "ghost.db")).empty

    def test_multiple_rows_all_loaded(self, tmp_path):
        rows = [self._base_row(days_ago=i, daily_sales=float(i + 1)) for i in range(1, 6)]
        df = app.load_data(self._write_db(tmp_path, rows))
        assert len(df) == 5


# ─────────────────────────────────────────────────────────────────────────────
# generate_store_audit_briefing
# ─────────────────────────────────────────────────────────────────────────────
class TestGenerateStoreAuditBriefing:
    """Verify prompt construction and correct delegation to get_llm_response."""

    def _sku(self) -> pd.Series:
        return pd.Series(
            {
                "SKU_ID": "SKU042",
                "Product_Name": "Test Widget",
                "Category": "Grocery",
                "On_Hand_Qty": 15,
                "Daily_Sales_Units": 2.5,
                "Days_Since_Last_Sale": 30,
                "Expected_Frequency": 0.4,
            }
        )

    def test_returns_value_from_llm(self):
        with patch("app.get_llm_response", return_value="AI briefing text"):
            result = app.generate_store_audit_briefing(self._sku(), "OpenAI", "gpt-4o-mini")
        assert result == "AI briefing text"

    def test_prompt_contains_sku_id(self):
        with patch("app.get_llm_response") as mock_llm:
            mock_llm.return_value = ""
            app.generate_store_audit_briefing(self._sku(), "OpenAI", "gpt-4o-mini")
            prompt = mock_llm.call_args[0][0]
        assert "SKU042" in prompt

    def test_prompt_contains_product_name(self):
        with patch("app.get_llm_response") as mock_llm:
            mock_llm.return_value = ""
            app.generate_store_audit_briefing(self._sku(), "OpenAI", "gpt-4o-mini")
            prompt = mock_llm.call_args[0][0]
        assert "Test Widget" in prompt

    def test_prompt_contains_days_since_last_sale(self):
        with patch("app.get_llm_response") as mock_llm:
            mock_llm.return_value = ""
            app.generate_store_audit_briefing(self._sku(), "OpenAI", "gpt-4o-mini")
            prompt = mock_llm.call_args[0][0]
        assert "30" in prompt

    def test_prompt_contains_on_hand_qty(self):
        with patch("app.get_llm_response") as mock_llm:
            mock_llm.return_value = ""
            app.generate_store_audit_briefing(self._sku(), "OpenAI", "gpt-4o-mini")
            prompt = mock_llm.call_args[0][0]
        assert "15" in prompt

    def test_passes_provider_to_llm(self):
        with patch("app.get_llm_response") as mock_llm:
            mock_llm.return_value = ""
            app.generate_store_audit_briefing(self._sku(), "Groq", "llama-3.3-70b")
            _, provider, _ = mock_llm.call_args[0]
        assert provider == "Groq"

    def test_passes_model_to_llm(self):
        with patch("app.get_llm_response") as mock_llm:
            mock_llm.return_value = ""
            app.generate_store_audit_briefing(self._sku(), "Groq", "llama-3.3-70b")
            _, _, model = mock_llm.call_args[0]
        assert model == "llama-3.3-70b"
