# 🔬 Feature Specification: Root Cause AI Agent

> **Status:** 🚧 In Progress — Logic & Testing Complete
> **Module:** `root_cause_agent.py` (to be added to `llm_providers.py` agentic layer)  
> **Author:** Mohith Kunta · [github.com/m-kunta](https://github.com/m-kunta)

---

## 1. Overview

The **Root Cause Agent** is an intelligent diagnostic layer for the Phantom Inventory Hunter. While the core system identifies *that* a phantom inventory event is likely occurring, this agent analyzes relational data signals to determine *why* it is happening — and provides actionable instructions for store operations.

> [!NOTE]
> This module extends the existing `generate_store_audit_briefing()` function with structured pre-analysis ("triangulation") before the LLM call, making the AI output far more precise and operationally actionable.

---

## 2. Data Requirements & Schema

The synthetic data engine (`data_gen.py`) must be extended with the following fields to enable diagnostic reasoning:

| Field | Type | Description | Source |
|---|---|---|---|
| `sister_sku_id` | `TEXT` | ID of the closest substitute product | Relational mapping |
| `category_velocity_index` | `FLOAT` | 7-day rolling avg sales for the entire category | Calculated metric |
| `historical_shrink_score` | `FLOAT` (0.0–1.0) | Risk rating based on past theft/loss data | Static attribute |
| `location_status` | `TEXT` | Status of the specific aisle or department | Simulated log (`Open`, `Closed`, `Restocking`) |

---

## 3. Diagnostic Logic — The "Triangulation" Engine

The agent uses a heuristic decision tree to classify the anomaly type *before* passing structured data to the LLM. This reduces hallucination and improves output quality.

### A. Substitution Detection → "Shelf Void"

If the target SKU has zero sales but the `sister_sku` shows a significant sales spike, the agent flags a **Shelf Void** — the item is missing from the shelf and customers are substituting.

$$V_{subs} = \frac{\text{Current Sister Sales}}{\text{Avg Sister Sales}} > 1.20$$

**Interpretation:** A ratio above 1.20 (20% spike) is a strong signal the target SKU has a physical availability problem.

---

### B. Category-Wide Anomaly → "Operational Blockage"

If sales are flat across the entire category, the agent flags an **Operational Blockage** — the aisle may be closed for maintenance, a reset, or a delivery blockage.

$$V_{cat} = \frac{\text{Current Category Velocity}}{\text{Baseline Category Velocity}} < 0.20$$

**Interpretation:** Category velocity below 20% of baseline suggests a store-operational cause, not a product-specific one.

---

### C. High-Shrink Anomaly → "Inventory Inaccuracy / Theft"

If `historical_shrink_score > 0.75` and sales halt abruptly despite high system inventory, the agent flags **Inventory Inaccuracy or Theft** — the recorded stock likely doesn't reflect physical reality.

> [!CAUTION]
> This flag should trigger a physical stock count, not just a shelf walk. High shrink scores combined with zero sales are a strong indicator of ORC (Organized Retail Crime) or systemic scan errors.

---

## 4. Agentic AI Layer — LLM Integration

Once a signal is detected by the triangulation engine, a **structured diagnostic payload** is forwarded to the LLM (via the existing `llm_providers.py` factory).

### Prompt Structure

| Component | Detail |
|---|---|
| **Role** | Senior Category Management Consultant |
| **Context** | SKU stats + sister-SKU performance + calculated diagnostic flag |
| **Task** | Synthesize into a "Situation → Action" report for store associates |
| **Constraint** | Professional, concise, prioritize high-value actions. Max 200 words. |

### Example Diagnostic Payload (JSON)

```json
{
  "sku_id": "SKU042",
  "product_name": "Grocery Product 42",
  "on_hand_qty": 18,
  "days_since_last_sale": 9,
  "expected_frequency_days": 1.2,
  "diagnostic_flag": "SHELF_VOID",
  "sister_sku_id": "SKU017",
  "sister_sales_ratio": 1.45,
  "category_velocity_index": 0.91,
  "historical_shrink_score": 0.31,
  "location_status": "Open"
}
```

---

## 5. UI/UX Specifications

The Streamlit interface (`app.py`) will be updated to include:

| Component | Description |
|---|---|
| **Diagnostic Tags** | Color-coded status badges on the main table: `Operational` · `Shelf Void` · `Shrink Risk` · `Blockage` |
| **Investigation Panel** | Expandable `st.expander` revealing a side-by-side comparison chart of the Ghost SKU vs. its Sister SKU sales trend |
| **AI Briefing Block** | Natural language "Situation → Action" output from the LLM, replacing the current generic briefing |

---

## 6. Success Metrics

| Metric | Description |
|---|---|
| **False Positive Reduction** | Decrease in ghost alerts caused by store-wide operational pauses (should be reclassified as `Blockage`, not `Phantom`) |
| **Resolution Speed** | Time from "Alert Triggered" → "Store Action Logged" |
| **Revenue Recovery (Lost Sales Opportunity)** | Calculated as: |

$$\text{LSO} = \text{Avg Daily Sales} \times \text{Unit Margin} \times \text{Days Out of Stock}$$

> [!TIP]
> The LSO metric is the most portfolio-compelling output of this module — it directly translates operational improvements into a dollar figure, making it ideal for executive reporting.

---

## 7. Implementation Checklist

- [x] Extend `data_gen.py` with 4 new schema fields (`Sister_SKU_ID`, `Category_Velocity_Index`, `Historical_Shrink_Score`, `Location_Status`)
- [x] Create `root_cause_agent.py` with the Triangulation Engine (substitution, blockage, shrink logic)
- [ ] Update `llm_providers.py` to accept structured diagnostic payloads
- [ ] Update `app.py` with diagnostic badge column and Investigation Panel
- [x] Update `README.md` and `QUICKSTART.md` for new setup requirements
- [x] Write unit tests for each triangulation heuristic

---

*Part of the [Phantom Inventory Hunter — Agentic AI](https://github.com/m-kunta/phantom-inventory-hunter-agentic-ai) project by Mohith Kunta.*
