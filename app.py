"""
================================================================================
  Phantom Inventory Hunter (Ghost Inventory Detection)
================================================================================
  Author:      Mohith Kunta
  GitHub:      https://github.com/m-kunta
  Description: An AI-powered Supply Chain dashboard that detects "Phantom
               Inventory" — items recorded as in-stock but showing anomalous
               sales gaps, suggesting misplacement, backroom bottlenecks, or
               system discrepancies.
  Tech Stack:  Streamlit · Pandas · SQLite · Multi-provider AI (Gemini /
               OpenAI / Anthropic / Groq / Ollama)
================================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
from llm_providers import get_llm_response, PROVIDER_DEFAULTS
import random
from data_gen import generate_synthetic_data

# Load environment variables from .env file (never commit .env to git!)
load_dotenv(override=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION & SETUP
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Phantom Inventory Hunter", layout="wide", page_icon="👻")

# Risk level ordering for correct sort priority (High → Medium → Low)
RISK_ORDER: dict[str, int] = {"High": 0, "Medium": 1, "Low": 2}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL HELPER FUNCTIONS
# Defined at module level to avoid re-creation on every Streamlit rerun.
# Author: Mohith Kunta | https://github.com/m-kunta
# ─────────────────────────────────────────────────────────────────────────────

def determine_risk(row: pd.Series, multiplier: float) -> str:
    """
    Classify a SKU's risk level based on how far its Days_Since_Last_Sale
    deviates from the expected sale frequency.

    Returns:
        'High'   — deviation is 2× or more above the threshold
        'Medium' — flagged as phantom but below 2× deviation
        'Low'    — not flagged as phantom inventory
    """
    if not row["Is_Phantom"]:
        return "Low"
    deviation_ratio = row["Days_Since_Last_Sale"] / (row["Expected_Frequency"] * multiplier)
    return "High" if deviation_ratio >= 2 else "Medium"


def color_risk_levels(val: str) -> str:
    """Return a CSS style string for a given Risk_Level value (Pandas Styler)."""
    color_map = {"High": "#ff4b4b", "Medium": "#ffa421", "Low": "#00cc96"}
    color = color_map.get(val, "")
    return f"color: {color}; font-weight: bold;"


# ─────────────────────────────────────────────────────────────────────────────
# CORE DATA FUNCTIONS
# Author: Mohith Kunta | https://github.com/m-kunta
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_data(db_path: str = "phantom_inventory.db") -> pd.DataFrame:
    """
    Load inventory data from a local SQLite database and compute derived metrics.
    Uses a context manager for safe connection handling.

    Returns:
        DataFrame with Days_Since_Last_Sale and Expected_Frequency columns added.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM inventory", conn)

        df["Last_Sale_Date"] = pd.to_datetime(df["Last_Sale_Date"])
        today = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
        df["Days_Since_Last_Sale"] = (today - df["Last_Sale_Date"]).dt.days
        df["Expected_Frequency"] = np.where(
            df["Daily_Sales_Units"] > 0,
            1 / df["Daily_Sales_Units"],
            999,
        )
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}. Please run data_gen.py first.")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# AGENTIC AI LAYER — Provider-Agnostic Store Audit Briefing
# Author: Mohith Kunta | https://github.com/m-kunta
# ─────────────────────────────────────────────────────────────────────────────

def generate_store_audit_briefing(sku_data: pd.Series, provider: str, model: str) -> str:
    """
    Build a structured prompt from the flagged SKU's data and send it
    to the selected LLM provider via the get_llm_response() factory.

    Args:
        sku_data: A pandas Series row representing a single flagged SKU.
        provider: Provider display name (e.g., 'Gemini', 'OpenAI').
        model:    Model identifier string (e.g., 'gemini-2.5-flash').

    Returns:
        AI-generated Store Audit Briefing as a string.
    """
    prompt = f"""
    Act as a Retail Supply Chain Expert. Analyze the following SKU data which has been flagged for "Phantom Inventory" (Ghost Inventory).

    SKU Details:
    - ID: {sku_data["SKU_ID"]}
    - Product: {sku_data["Product_Name"]}
    - Category: {sku_data["Category"]}
    - On Hand Quantity: {sku_data["On_Hand_Qty"]}
    - Average Daily Sales: {sku_data["Daily_Sales_Units"]}
    - Days Since Last Sale: {sku_data["Days_Since_Last_Sale"]}
    - Expected Sale Frequency: Every {sku_data["Expected_Frequency"]:.2f} days

    Explain WHY this anomalous gap in sales is suspicious despite having inventory on hand.
    Provide a concise "Store Audit Briefing" with a few potential root causes (e.g., misplaced
    pallet, backroom bottleneck, system discrepancy, damaged goods). Keep it under 150 words.
    """
    return get_llm_response(prompt, provider, model)


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI LAYOUT
# Author: Mohith Kunta | https://github.com/m-kunta
# ─────────────────────────────────────────────────────────────────────────────

st.title("👻 Phantom Inventory Hunter Dashboard")
st.markdown(
    "Identify **'Ghost Inventory'** — items that systems show as in-stock, but are not "
    "selling at expected frequencies. This suggests they may be lost in the backroom, "
    "misplaced, or damaged."
)

# [Feature Addition #1] CSV Data Upload (Added: 2026-03-03)
# ── Data Source Sidebar ───────────────────────────────────────────────────
st.sidebar.header("📁 Data Source")

# [Feature Addition #3] Sample CSV Download (Added: 2026-03-03)
sample_csv = "SKU_ID,Product_Name,Category,On_Hand_Qty,Daily_Sales_Units,Last_Sale_Date\nSKU999,Sample Item,Grocery,50,2.5,2026-01-01"
st.sidebar.download_button(
    label="Download Sample CSV Template",
    data=sample_csv,
    file_name="sample_inventory_template.csv",
    mime="text/csv",
)

uploaded_file = st.sidebar.file_uploader(
    "Upload Inventory Data (CSV)", 
    type=["csv"],
    help="Required columns: SKU_ID, Product_Name, Category, On_Hand_Qty, Daily_Sales_Units, Last_Sale_Date"
)

if uploaded_file is not None:
    # We only process the uploaded file if:
    # 1. We haven't processed this exact file yet
    # 2. OR the user hasn't explicitly overridden it by requesting synthetic data
    
    # Check if a new file was uploaded compared to our last memory
    is_new_upload = ("last_uploaded_file" not in st.session_state) or (st.session_state.last_uploaded_file != uploaded_file.name)
    
    if is_new_upload:
        # A new file was dropped in, clear any synthetic override flags
        st.session_state.pop("synthetic_override", None)
        
    if not st.session_state.get("synthetic_override", False) and is_new_upload:
        try:
            uploaded_df = pd.read_csv(uploaded_file)
            required_cols = {'SKU_ID', 'Product_Name', 'Category', 'On_Hand_Qty', 'Daily_Sales_Units', 'Last_Sale_Date'}
            
            if not required_cols.issubset(uploaded_df.columns):
                st.sidebar.error(f"Missing required columns. Uploaded columns: {list(uploaded_df.columns)}. Required: {list(required_cols)}")
            else:
                with sqlite3.connect("phantom_inventory.db") as conn:
                    uploaded_df.to_sql('inventory', conn, if_exists='replace', index=False)
                
                # Mark this file as processed in session state
                st.session_state.last_uploaded_file = uploaded_file.name
                st.sidebar.success("Successfully loaded CSV data! Refreshing...")
                load_data.clear() # Clear the cache so it reloads from DB
                st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error parsing CSV file: {e}")

st.sidebar.markdown("---")

# [Feature Addition #2] Generate Synthetic Data (Added: 2026-03-03)
st.sidebar.subheader("🎲 Synthetic Data")
if st.sidebar.button("Generate New Synthetic Data", help="Overwrites the SQLite database with 50 new random SKUs"):
    if uploaded_file is not None:
        st.sidebar.warning("⚠️ Please remove the uploaded CSV file (click the 'X') before generating synthetic data.")
    else:
        new_seed = random.randint(1, 100000)
        with st.spinner("Generating new data..."):
            generate_synthetic_data(seed=new_seed)
            st.session_state["synthetic_override"] = True  # Flag to ignore the CSV currently in the uploader
            st.session_state.pop("last_uploaded_file", None) # Force clearing last upload state
            load_data.clear() # Clear DB cache
            st.rerun()

st.sidebar.markdown("---")

df = load_data()

if not df.empty:
    # ── Sidebar ───────────────────────────────────────────────────────────────
    st.sidebar.header("🔧 Filter & Settings")

    # Category filter
    categories = ["All"] + list(df["Category"].unique())
    selected_category = st.sidebar.selectbox("📂 Category Filter", categories)

    # Sensitivity slider
    sensitivity = st.sidebar.slider(
        "📏 Anomaly Threshold Multiplier (× Expected Frequency)",
        min_value=1.0,
        max_value=10.0,
        value=3.0,
        step=0.5,
        help="Flag items if Days Since Last Sale > (Multiplier × Expected Frequency)",
    )

    st.sidebar.markdown("---")

    # ── AI Provider Selector ──────────────────────────────────────────────────
    st.sidebar.subheader("🤖 AI Provider")

    provider_names = list(PROVIDER_DEFAULTS.keys())
    # Read default provider from .env if set, otherwise default to Gemini
    env_default = os.getenv("LLM_PROVIDER", "Gemini")
    default_idx = provider_names.index(env_default) if env_default in provider_names else 0

    selected_provider = st.sidebar.selectbox(
        "Provider",
        options=provider_names,
        index=default_idx,
        help="Switch AI providers without restarting. Set LLM_PROVIDER in .env to persist your choice.",
    )

    # Default model for the chosen provider, overridable by the user
    default_model = PROVIDER_DEFAULTS[selected_provider]["model"]
    selected_model = st.sidebar.text_input(
        "Model",
        value=default_model,
        help=f"Default for {selected_provider}: {default_model}",
    )

    # API key status indicator
    key_env = PROVIDER_DEFAULTS[selected_provider]["key_env"]
    if key_env:
        if os.getenv(key_env):
            st.sidebar.success(f"✅ `{key_env}` configured")
        else:
            st.sidebar.warning(f"⚠️ Set `{key_env}` in your `.env` file")
    else:
        st.sidebar.info("ℹ️ Ollama runs locally — no API key needed")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style='text-align: center; color: #888; font-size: 0.8rem; padding: 0.5rem 0;'>
            Built by <strong>Mohith Kunta</strong><br>
            <a href='https://github.com/m-kunta' target='_blank'
               style='color: #a78bfa; text-decoration: none;'>
               🔗 github.com/m-kunta
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Data Filtering ────────────────────────────────────────────────────────
    if selected_category != "All":
        df_filtered = df[df["Category"] == selected_category].copy()
    else:
        df_filtered = df.copy()

    # ── Ghost Detection Algorithm ─────────────────────────────────────────────
    # Flag: (On_Hand_Qty > 0) AND (Days_Since_Last_Sale > Sensitivity × Expected_Frequency)
    df_filtered["Is_Phantom"] = (
        (df_filtered["On_Hand_Qty"] > 0)
        & (df_filtered["Days_Since_Last_Sale"] > (sensitivity * df_filtered["Expected_Frequency"]))
    )

    df_filtered["Risk_Level"] = df_filtered.apply(
        lambda row: determine_risk(row, sensitivity), axis=1
    )

    # ── Dashboard Metrics ─────────────────────────────────────────────────────
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total SKUs Analyzed", len(df_filtered))
    col2.metric("Phantom Inventory Flags", int(df_filtered["Is_Phantom"].sum()))
    col3.metric("High Risk SKUs", int((df_filtered["Risk_Level"] == "High").sum()))
    st.markdown("---")

    # ── Inventory Monitoring Table ────────────────────────────────────────────
    st.subheader("📊 Inventory Monitoring Table")

    display_cols = [
        "SKU_ID", "Product_Name", "Category",
        "On_Hand_Qty", "Daily_Sales_Units", "Days_Since_Last_Sale", "Risk_Level",
    ]
    # Sort by risk severity (High → Medium → Low), then by gap length descending
    df_display = (
        df_filtered[display_cols]
        .assign(_sort_key=df_filtered["Risk_Level"].map(RISK_ORDER))
        .sort_values(by=["_sort_key", "Days_Since_Last_Sale"], ascending=[True, False])
        .drop(columns=["_sort_key"])
    )

    st.dataframe(
        df_display.style.map(color_risk_levels, subset=["Risk_Level"]),
        use_container_width=True,
        hide_index=True,
    )

    # ── Agentic Layer: AI Analyst ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🧠 Virtual Supply Chain Analyst")
    st.markdown(
        f"Select a flagged **Phantom SKU** to generate a targeted Store Audit Briefing "
        f"using **{selected_provider}** (`{selected_model}`)."
    )

    phantom_skus = df_filtered[df_filtered["Is_Phantom"]]["SKU_ID"].tolist()

    if phantom_skus:
        phantom_df = df_filtered[df_filtered["Is_Phantom"]][["SKU_ID", "Product_Name"]]
        sku_options = dict(
            zip(phantom_df["SKU_ID"], phantom_df["SKU_ID"] + " — " + phantom_df["Product_Name"])
        )

        selected_sku = st.selectbox(
            "Select Flagged SKU to Analyze:",
            options=phantom_skus,
            format_func=lambda x: sku_options[x],
        )

        if st.button("Generate Store Audit Briefing", type="primary"):
            sku_data = df_filtered[df_filtered["SKU_ID"] == selected_sku].iloc[0]
            with st.spinner(f"Analyzing with {selected_provider} ({selected_model})..."):
                briefing = generate_store_audit_briefing(sku_data, selected_provider, selected_model)
                st.info(f"**Store Audit Briefing for {selected_sku}** *(via {selected_provider})*\n\n{briefing}")
    else:
        st.success("🎉 No Phantom Inventory detected with the current sensitivity threshold!")
else:
    st.warning("⚠️ No data loaded. Please run `python data_gen.py` to generate the synthetic SQLite database.")

# ────────────────────────────────────────────────────────────────────────────── FOOTER
st.markdown("""
<div style='
    text-align: center;
    margin-top: 3rem;
    padding: 1.5rem;
    border-top: 1px solid #333;
    color: #888;
    font-size: 0.85rem;
    line-height: 1.8;
'>
    👻 <strong>Phantom Inventory Hunter</strong> &nbsp;|&nbsp; Agentic AI Supply Chain Tool<br>
    Built by <strong>Mohith Kunta</strong> &nbsp;&mdash;&nbsp;
    <a href='https://github.com/m-kunta' target='_blank'
       style='color: #a78bfa; text-decoration: none;'>
        github.com/m-kunta
    </a>
    &nbsp;|&nbsp; MIT License
</div>
""", unsafe_allow_html=True)
