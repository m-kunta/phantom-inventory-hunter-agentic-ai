# 👻 Phantom Inventory Hunter — Quick Start Guide

> **For non-technical users:** This guide walks you through everything step-by-step with no coding experience needed.

---

## What You'll Need

- A computer running macOS or Windows
- An internet connection
- About **10–15 minutes** to set everything up for the first time

---

## Step 1 — Install Python

Python is the programming language the app runs on.

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow **"Download Python 3.x.x"** button
3. Open the downloaded file and follow the installer
   - ✅ **Important (Windows only):** On the first screen, check the box that says **"Add Python to PATH"** before clicking Install

**Verify it worked:** Open **Terminal** (Mac) or **Command Prompt** (Windows) and type:
```
python3 --version
```
You should see something like `Python 3.12.0`.

---

## Step 2 — Download the Project

1. Go to [github.com/m-kunta/phantom-inventory-hunter-agentic-ai](https://github.com/m-kunta/phantom-inventory-hunter-agentic-ai)
2. Click the green **Code** button → **Download ZIP**
3. Unzip the folder somewhere easy to find (e.g. your Desktop)
4. Open **Terminal** (Mac) or **Command Prompt** (Windows)
5. Navigate to the project folder — type and press Enter:
   ```
   cd ~/Desktop/phantom-inventory-hunter-agentic-ai
   ```
   *(Adjust the path if you unzipped it somewhere else)*

---

## Step 3 — Install the App's Requirements

Copy and paste these two commands into your terminal, one at a time:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

*(Windows users: replace `source .venv/bin/activate` with `.venv\Scripts\activate`)*

Wait for each command to finish before running the next one.

---

## Step 4 — Get a Free AI API Key

The AI "analyst" feature requires an API key from an AI provider. **We recommend Gemini — it's free.**

### 🟢 Option A: Gemini (Google) — Free, Recommended

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Click **"Copy"** next to the key that appears
5. Keep this copied — you'll need it in Step 5

> **No Google account?** Create one free at [accounts.google.com](https://accounts.google.com)

---

### 🟢 Option B: Groq — Free, Very Fast

Groq is another free option running open-source Llama models.

1. Go to [console.groq.com](https://console.groq.com) and sign up (free)
2. Click **API Keys** in the left menu
3. Click **"Create API Key"**, give it a name, copy the key
4. In Step 5 below, set `LLM_PROVIDER=Groq` and `GROQ_API_KEY=your_key`

---

### 🟢 Option C: Ollama — Completely Free, Works Offline

Ollama runs the AI model **on your computer** — no internet needed after setup, no account, no API key.

1. Go to [ollama.com](https://ollama.com) and click **Download**
2. Install it like a normal app
3. Open Terminal and run: `ollama pull llama3.2`
4. That's it! In the app sidebar, just select **"Ollama"** — no key needed

---

### 🔵 Option D: OpenAI (ChatGPT) — Paid

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in and click **"Create new secret key"**
3. Copy the key (it won't be shown again — save it somewhere safe)
4. Note: OpenAI requires you to add billing credits to use the API

---

### 🔵 Option E: Anthropic (Claude) — Paid

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up, go to **API Keys**, and click **"Create Key"**
3. Copy the key
4. Note: Anthropic requires billing setup

---

## Step 5 — Configure Your API Key

1. In the project folder, find the file called **`.env.example`**
2. Make a copy of it and rename the copy to **`.env`** (just `.env`, no `.example`)
   - On Mac: right-click → Duplicate, then rename
   - On Windows: copy & paste the file in the same folder, rename the copy
3. Open `.env` with any text editor (Notepad, TextEdit, VS Code)
4. Fill in your key. For example, for Gemini:
   ```
   LLM_PROVIDER=Gemini
   GEMINI_API_KEY=paste_your_key_here
   ```
5. Save the file

> ⚠️ **Never share your `.env` file or post your API key publicly.** It's already excluded from GitHub by `.gitignore`.

---

## Step 6 — Generate the Sample Data

In your terminal (with `.venv` active), run:
```bash
python3 data_gen.py
```

You should see:
```
✅ Successfully generated data for 50 SKUs (seed=42).
💾 Saved to phantom_inventory.db
```

---

## Step 7 — Launch the Dashboard

```bash
streamlit run app.py
```

Your browser will automatically open to **http://localhost:8501** with the live dashboard!

---

## Using the App

| Control | What it does |
|---|---|
| **Category Filter** | Show only Health & Beauty or Grocery SKUs |
| **Anomaly Threshold Multiplier** | Lower = more flags; Higher = stricter (fewer flags) |
| **AI Provider** | Switch between Gemini, OpenAI, Groq, Anthropic, or Ollama |
| **Model** | Override the AI model (advanced — leave as default if unsure) |
| **Select Flagged SKU** | Pick an item with ghost inventory |
| **Generate Store Audit Briefing** | Get the AI's explanation of what might be wrong |

---

## Troubleshooting

**"Command not found: python3"**
→ Python isn't installed or not in PATH. Redo Step 1.

**"No module named streamlit"**
→ Your virtual environment isn't active. Run `source .venv/bin/activate` first.

**"API key not valid"**
→ Check that you pasted the full key into `.env` with no extra spaces.

**"Quota exceeded"**
→ You've hit the free tier limit for the day. Try Groq or Ollama (both free with no daily limits).

**AI briefing panel shows nothing**
→ Make sure you clicked **"Generate Store Audit Briefing"** after selecting a flagged SKU.

---

## Getting Help

- Open an issue at [github.com/m-kunta](https://github.com/m-kunta)
- Author: **Mohith Kunta** — Supply Chain & AI Portfolio Project
