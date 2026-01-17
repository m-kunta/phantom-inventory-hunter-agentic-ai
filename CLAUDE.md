# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

**Python environment** — the venv lives at `.venv/`. Always use it:
```bash
source .venv/bin/activate
# or call directly:
.venv/bin/python <script>
```

**Run the dashboard:**
```bash
streamlit run app.py
```

**Regenerate synthetic data** (overwrites `phantom_inventory.db`):
```bash
python data_gen.py
# Or with a custom seed:
python -c "from data_gen import generate_synthetic_data; generate_synthetic_data(seed=99)"
```

**Install an optional AI provider SDK:**
```bash
pip install openai        # OpenAI
pip install anthropic     # Anthropic
pip install groq          # Groq
pip install ollama        # Ollama (also requires the desktop app from ollama.com)
```

**Run tests:**
```bash
pytest tests/ -v
# Run a single test file:
pytest tests/test_root_cause_agent.py -v
```

---

## Architecture

### Module responsibilities

| File | Role |
|---|---|
| `app.py` | Streamlit entry point. Owns the UI, ghost detection algorithm, risk classification, and the `generate_store_audit_briefing()` agentic call. |
| `llm_providers.py` | Provider factory. Single public function `get_llm_response(prompt, provider, model)`. All provider SDKs are lazy-imported inside their private `_call_*()` handler — never at module level. |
| `data_gen.py` | Synthetic data engine. Generates 50 SKUs to SQLite. |
| `root_cause_agent.py` | Triangulation Engine. `run_triangulation()` classifies phantom root cause (SHELF_VOID / OPERATIONAL_BLOCKAGE / SHRINK_RISK / NORMAL). `build_diagnostic_payload()` structures the result for the LLM. `generate_root_cause_briefing()` orchestrates the full pipeline. |

### Data flow

```
data_gen.py → phantom_inventory.db → app.py:load_data()
                                           │
                                 Ghost Detection Algorithm
                                           │
                         ┌─────────────────┴──────────────────┐
                         │                                     │
                   Streamlit UI                    root_cause_agent.py
               (Risk Table + Metrics)              (Triangulation Engine)
                                                          │
                                                  llm_providers.py
                                               (Diagnostic AI Briefing)
```

### Ghost detection algorithm (in `app.py`)

All three steps run inside the Streamlit reactive loop against the filtered DataFrame:

1. `Expected_Frequency = 1 / Daily_Sales_Units`
2. `Is_Phantom = (On_Hand_Qty > 0) AND (Days_Since_Last_Sale > sensitivity × Expected_Frequency)`
3. `deviation_ratio = Days_Since_Last_Sale / (Expected_Frequency × sensitivity)` → ≥2 = **High**, <2 = **Medium**, not flagged = **Low**

### Adding a new LLM provider (`llm_providers.py`)

1. Add an entry to `PROVIDER_DEFAULTS` — display name, default model string, and `key_env` (or `None` for local).
2. Add a private `_call_<name>(prompt, model) -> str` function. Import the SDK inside the function body, not at the top of the file.
3. Register it in the `dispatch` dict inside `get_llm_response()`.

That is the complete change — no modifications to `app.py` needed; it reads `PROVIDER_DEFAULTS` dynamically.

### Key implementation details

- **`@st.cache_data(ttl=60)`** on `load_data()` — any code that writes to the SQLite DB must call `load_data.clear()` afterward and `st.rerun()` to reflect the change in the UI. See the CSV upload and synthetic data generation blocks in `app.py` for the pattern.

- **`_diagnostic_type` in `data_gen.py`** — an internal field used during generation to drive realistic signal values for the Root Cause Agent fields. It is dropped with `df.drop(columns=['_diagnostic_type'])` before the DB write and never appears in `phantom_inventory.db`.

- **Guaranteed diagnostic coverage** — `data_gen.py` pre-seeds a `phantom_type_pool` with `['shelf_void', 'shelf_void', 'blockage', 'blockage', 'shrink', 'shrink']` (shuffled) before the SKU loop. This ensures all three root-cause signal types always appear regardless of the RNG seed, so the triangulation engine always has examples of each flag type to work with.

- **Sister SKU assignment for `shelf_void`** — phantom candidates of type `shelf_void` are preferentially paired with a sister SKU whose `Daily_Sales_Units` is above the category mean. This makes the substitution spike ratio (`sister.daily_sales / category_mean`) naturally detectable by the triangulation engine.

### Root Cause Agent schema fields (in `phantom_inventory.db` as of v0.2)

| Column | Signal threshold |
|---|---|
| `Sister_SKU_ID` | TEXT — same-category substitute SKU |
| `Category_Velocity_Index` | FLOAT — ratio of current to baseline category sales; **< 0.20** = Operational Blockage |
| `Historical_Shrink_Score` | FLOAT 0–1 — **> 0.75** combined with zero sales = Shrink Risk |
| `Location_Status` | TEXT — `Open` / `Closed` / `Restocking`; non-Open corroborates Blockage |

### Environment / secrets

Copy `.env.example` → `.env`. Only `LLM_PROVIDER` and the key for your chosen provider are required. `app.py` reads `LLM_PROVIDER` at startup to set the sidebar default; the key status indicator reads the relevant `*_API_KEY` variable live (and allows the user to input/update the key directly from the UI, which persists it to `.env`).
