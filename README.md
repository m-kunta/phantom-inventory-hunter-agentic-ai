# 👻 Phantom Inventory Hunter

> **AI-powered Ghost Inventory Detection for Retail Supply Chain**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.50+-red.svg)](https://streamlit.io/)
[![Gemini AI](https://img.shields.io/badge/Gemini-AI-purple.svg)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Author:** Mohith Kunta  
**GitHub:** [github.com/m-kunta](https://github.com/m-kunta)

> 💡 **New to coding?** See the [📘 Non-Technical Quick Start Guide](QUICKSTART.md) for step-by-step instructions — from installing Python to getting your first API key.

---

## 🔍 What is Phantom Inventory?

**Phantom Inventory Hunter** is a prototype data science application designed to identify retail "ghost inventory"—items that the system believes are in stock, but are not selling at expected probabilistic frequencies.

![Dashboard Preview](/Users/MKunta/.gemini/antigravity/brain/8e627a15-1074-4cff-9f50-1ebdc4b7cf81/phantom_dashboard_1772332720080.png)

This tool bridges the gap between raw statistical anomalies and actionable retail operations by leveraging **Agentic AI** to analyze flagged SKUs and generate prioritized store audit briefings.

**Phantom Inventory** (also called "Ghost Inventory") is a critical retail supply chain problem where a store's inventory management system records an item as **in-stock**, but the product is effectively **unavailable for sale** — because it's:

- 📦 **Misplaced** in a backroom or wrong shelf location
- 🛑 **Damaged** but not yet removed from the system
- 🔄 **Stuck** in a backroom receiving bottleneck
- 🖥️ Involved in a **system discrepancy** (shrinkage, miscounting)

Phantom inventory directly causes **lost sales**, **poor customer experience**, and **flawed replenishment decisions**.

This tool detects potential phantom inventory by flagging SKUs that:
1. Show **positive On-Hand Quantity** in the system
2. Have **not sold** for far longer than their historical velocity would suggest

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔬 **Ghost Detection Algorithm** | Flags SKUs where `Days Since Last Sale > N × Expected Sale Frequency` |
| 🎛️ **Adjustable Sensitivity** | A sidebar slider lets you tune the N-multiplier threshold interactively |
| 📊 **Risk Tiering** | Automatically classifies flagged items as **High** / **Medium** / **Low** risk |
| 🧠 **AI Store Audit Briefings** | Powered by Google Gemini — click any flagged SKU for a plain-English root-cause analysis |
| 🗂️ **Category Filtering** | Filter by `Health & Beauty` or `Grocery` in the sidebar |
| 💾 **SQLite Persistence** | All data stored locally in a lightweight SQLite database |
| ⚡ **Streamlit Dashboard** | Interactive, real-time, filterable UI with color-coded risk levels |

### 3. Agentic AI Root Cause Analysis

Clicking **"Generate Store Audit Briefing"** passes the anomaly context to an LLM provider of your choice. The LLM acts as a Virtual Supply Chain Analyst, generating a concise, readable brief for store associates explaining *why* the item is flagged and *where* they should look for it (e.g., specific backroom areas, top-stock, damaged bins).

![AI Detective Preview](/Users/MKunta/.gemini/antigravity/brain/8e627a15-1074-4cff-9f50-1ebdc4b7cf81/phantom_ai_detective_1772332708684.png)

**Provider Support:** The app includes a flexible factory class (`LLMProvider`) that currently supports:

---

## 🏗️ Architecture

```
phantom_inventory/
├── app.py                   # Main Streamlit dashboard & AI interface
├── llm_providers.py         # Provider factory (Gemini/OpenAI/Anthropic/Groq/Ollama)
├── data_gen.py              # Synthetic data engine (SQLite generator)
├── phantom_inventory.db     # Auto-generated SQLite database (git-ignored)
├── requirements.txt         # Python dependencies
├── .env                     # Your secret API keys (git-ignored, never commit!)
├── .env.example             # Safe template to share with collaborators
├── .gitignore               # Excludes .env, .venv/, *.db, __pycache__/ etc.
├── QUICKSTART.md            # Non-technical setup guide
└── README.md                # This file
```

### Data Flow

```
[data_gen.py] ──► [SQLite DB] ──► [app.py: load_data()]
                                         │
                               [Ghost Detection Algorithm]
                                         │
                    ┌────────────────────┴──────────────────────┐
                    │                                            │
             [Streamlit UI]                           [Gemini AI API]
           (Risk Table + Metrics)                 (Store Audit Briefing)
```

---

## 🔬 The Ghost Detection Algorithm

The core detection logic is simple but effective:

**Step 1 — Calculate Expected Sale Frequency:**
```
Expected_Frequency (days) = 1 / Daily_Sales_Units
```
*e.g., a SKU with 0.5 avg daily sales → expected to sell once every 2 days*

**Step 2 — Flag Phantom Candidates:**
```
Is_Phantom = (On_Hand_Qty > 0) AND (Days_Since_Last_Sale > Threshold × Expected_Frequency)
```
*Default threshold: 3× (configurable via the sidebar slider from 1× to 10×)*

**Step 3 — Assign Risk Level:**
```
deviation_ratio = Days_Since_Last_Sale / (Expected_Frequency × Threshold)
  • deviation_ratio ≥ 2  →  HIGH risk
  • deviation_ratio < 2  →  MEDIUM risk
  • Not flagged          →  LOW risk
```

---

## 🤖 The AI Analyst (Agentic Layer)

The app features a **provider-agnostic AI layer** (`llm_providers.py`) built on the Strategy Pattern. You can switch providers live from the **sidebar** without restarting the app, or set a default via `.env`.

### Supported Providers

| Provider | Package | Free Tier | Default Model | Key in `.env` |
|---|---|---|---|---|
| **Gemini** *(default)* | `google-genai` | ✅ Yes | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| **OpenAI** | `openai` | ❌ Paid | `gpt-4o-mini` | `OPENAI_API_KEY` |
| **Anthropic** | `anthropic` | ❌ Paid | `claude-3-5-haiku-latest` | `ANTHROPIC_API_KEY` |
| **Groq** | `groq` | ✅ Yes | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| **Ollama** | `ollama` | ✅ Free (local) | `llama3.2` | *(none needed)* |

### How Switching Works

1. **Sidebar** — Select any provider from the dropdown in the running app. Change models by editing the model text box.
2. **`.env`** — Set `LLM_PROVIDER=Groq` (or any name) to make a provider the persistent default.
3. **Missing packages** — If a provider's SDK isn't installed, the app shows a friendly install hint instead of crashing.

### Adding Ollama (fully local, free)

```bash
# 1. Install Ollama: https://ollama.com
# 2. Pull a model
ollama pull llama3.2
# 3. Select "Ollama" in the sidebar — no API key needed!
```

### Adding Groq (free API, fastest inference)

```bash
# Get a free API key at https://console.groq.com
# Add to .env:
GROQ_API_KEY=your_groq_api_key_here
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+ — [download here](https://www.python.org/downloads/)
- An API key for at least one AI provider (see below — free options available)

> 💡 **First time?** Follow the [QUICKSTART.md](QUICKSTART.md) guide instead — it explains everything in plain language.

### Getting an AI API Key

You only need **one** of these. Pick whichever suits you:

| Provider | Cost | Link | Time |
|---|---|---|---|
| **Gemini** *(recommended)* | 🆓 Free | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | 2 min |
| **Groq** | 🆓 Free | [console.groq.com](https://console.groq.com) | 3 min |
| **Ollama** | 🆓 Free (local) | [ollama.com](https://ollama.com) — no account needed | 5 min |
| **OpenAI** | 💳 Paid | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | 5 min |
| **Anthropic** | 💳 Paid | [console.anthropic.com](https://console.anthropic.com) | 5 min |

#### Gemini (step-by-step)
1. Sign in at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) with your Google account
2. Click **"Create API Key"**
3. Copy the key — paste it into your `.env` file as `GEMINI_API_KEY=...`

#### Groq (step-by-step)
1. Sign up free at [console.groq.com](https://console.groq.com)
2. Go to **API Keys** → **Create API Key** → copy it
3. Paste into `.env` as `GROQ_API_KEY=...` and set `LLM_PROVIDER=Groq`

#### Ollama — no account needed
1. Download and install from [ollama.com](https://ollama.com)
2. In terminal: `ollama pull llama3.2`
3. Select **"Ollama"** in the app sidebar — no key required

### Installation

**1. Clone the repository:**
```bash
git clone https://github.com/m-kunta/phantom-inventory-hunter-agentic-ai.git
cd phantom-inventory-hunter-agentic-ai
```

**2. Create and activate a virtual environment:**
```bash
python3 -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure your Gemini API Key:**

Copy the example env file and fill in your key — do **not** edit `app.py` directly:
```bash
cp .env.example .env
# Then open .env and set:
# GEMINI_API_KEY=your_actual_key_here
```
Get a free API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).

**5. Generate synthetic data:**
```bash
python data_gen.py
```
> **Tip:** Data is seeded (default `seed=42`) so the same dataset is generated on every run. Pass a different seed to get a new dataset: `python -c "from data_gen import generate_synthetic_data; generate_synthetic_data(seed=99)"`

**6. Launch the dashboard:**
```bash
streamlit run app.py
```

The app will open at **http://localhost:8501** 🎉

---

## 📦 Data Schema

The `inventory` table in `phantom_inventory.db` follows this schema:

| Column | Type | Description |
|---|---|---|
| `SKU_ID` | TEXT | Unique product identifier (e.g., `SKU001`) |
| `Product_Name` | TEXT | Human-readable product name |
| `Category` | TEXT | `Health & Beauty` or `Grocery` |
| `On_Hand_Qty` | INTEGER | Current stock quantity in the system |
| `Daily_Sales_Units` | FLOAT | Average daily sold units (velocity) |
| `Last_Sale_Date` | DATE | Date of the most recent recorded sale |

Computed fields added at runtime by `app.py`:

| Column | Description |
|---|---|
| `Days_Since_Last_Sale` | Calculated from `Last_Sale_Date` vs today |
| `Expected_Frequency` | `1 / Daily_Sales_Units` |
| `Is_Phantom` | Boolean flag (detection algorithm output) |
| `Risk_Level` | `High`, `Medium`, or `Low` |

---

## 🛠️ Dependencies

```
streamlit           # Interactive dashboard framework
pandas              # Data manipulation and analysis
numpy               # Numerical operations
python-dotenv       # Loads API keys safely from .env file
google-genai        # Gemini AI — default provider

# Optional (install for your chosen alternative provider):
# openai            # OpenAI GPT-4o / GPT-4o-mini
# anthropic         # Anthropic Claude 3.5
# groq              # Groq (Llama 3, Mixtral) — free tier
# ollama            # Ollama — fully local, no key needed
```

---

## 💡 Roadmap

### 🔬 Planned: Root Cause AI Agent
> **Full spec:** [ROOT_CAUSE_AGENT.md](ROOT_CAUSE_AGENT.md)

The next major module — moves beyond *detecting* phantom inventory to *diagnosing why* it's happening using relational data signals and a heuristic triangulation engine before the LLM call.

| Signal | Diagnostic Flag | Meaning |
|---|---|---|
| Sister-SKU sales spike +20% | `SHELF_VOID` | Item missing from shelf, customers substituting |
| Category velocity < 20% baseline | `OPERATIONAL_BLOCKAGE` | Aisle closed / maintenance / reset |
| Shrink score > 0.75 + zero sales | `SHRINK_RISK` | Theft or inventory inaccuracy |

New fields required: `sister_sku_id`, `category_velocity_index`, `historical_shrink_score`, `location_status`

---

### 🗃️ Other Future Enhancements

- [ ] **Real data connectors** (SAP, NetSuite, Shopify API)
- [ ] **Email/Slack alerts** for newly flagged High-risk SKUs
- [ ] **Historical trend charts** (7-day rolling sales velocity)
- [ ] **Multi-store support** with store-level filtering
- [ ] **Export to CSV/PDF** for store manager reports
- [ ] **ML anomaly scoring** as an alternative to rule-based thresholds

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for full text.

**What this means:**
- ✅ Free to use for personal, academic, or commercial projects
- ✅ Free to modify and distribute
- ⚠️ You **must** keep the copyright notice (i.e., credit Mohith Kunta) in any copy or derivative work

---

## 👤 Author

**Mohith Kunta**  
Supply Chain & AI Portfolio Project  
🔗 [github.com/m-kunta](https://github.com/m-kunta)

---

*Built with ❤️ to solve real retail supply chain problems with modern AI tooling.*
