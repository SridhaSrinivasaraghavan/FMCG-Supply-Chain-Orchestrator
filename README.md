# 🏭 Autonomous Multi-Agent FMCG Supply Chain Orchestrator

Welcome to the **Autonomous Supply Chain Orchestrator**. This system acts as a fully autonomous "Brain" for a Fast-Moving Consumer Goods (FMCG) company. It constantly monitors global news, assesses logistical and supplier risks, calculates financial trade-offs in real-time, and executes mitigation strategies (like emergency Purchase Orders) to ensure factories never go idle.

Built with **FastAPI** (Backend), **LangGraph** (Multi-Agent Orchestration), **PostgreSQL** (Database), and **Streamlit** (Live Streaming Frontend).

---

## 🧠 The Multi-Agent Workflow Explained

This system relies on a LangGraph state machine passing a central "State" object between four distinct AI agents. 

1. **Agent 1: Market Intel (The Scout)**
   - **What it does:** Scans raw, unstructured text (news articles, tweets, weather reports) and uses an LLM to extract a highly structured JSON payload representing the threat (e.g., event type, region, severity, delay days).
   - **Where it lives:** `backend/app/agents/market_intel.py`
2. **Agent 2: Risk Assessment (The Analyst)**
   - **What it does:** Takes the parsed threat and queries the PostgreSQL database to find out exactly what materials, routes, and suppliers are located in the affected region. It finds all available "Backup Suppliers" and formats this data.
   - **Where it lives:** `backend/app/agents/risk_assessment.py`
3. **Agent 3: Financial Analyst (The CFO)**
   - **What it does:** The most complex agent. It first runs raw deterministic math: *How many days of stock do we have left? How much will it cost if the factory goes idle? How much is the premium to buy from a backup supplier?* It then uses an LLM to review these numbers against strict company policies (e.g., quality vs. cost trade-offs) and decides whether to `HOLD_AND_MONITOR`, issue a `PROACTIVE_ADVISORY`, or `EXECUTE_BACKUP_PO`.
   - **Where it lives:** `backend/app/agents/financial_analyst.py`
4. **Agent 4: Strategy Execution (The Doer)**
   - **What it does:** Executes the CFO's decision. If an emergency PO is needed, it drafts the email, generates a PO record, and saves the logs to the database so the frontend can display it.
   - **Where it lives:** `backend/app/agents/strategy_execution.py`

---

## 📁 Project Structure (Where to change things)

If you are a developer looking to modify the system, here is where you go:

- `backend/app/agents/` - **Change Agent Logic here.** If you want to change how the CFO thinks, edit the `CFO_DECISION_PROMPT` inside `financial_analyst.py`.
- `backend/app/models.py` - **Change Database Tables here.** We use SQLAlchemy. If you want to add a new column to the `Supplier` table, do it here.
- `backend/app/schemas.py` - **Change API validation here.** We use Pydantic. If you want the frontend to receive different data, update the response schemas here.
- `backend/app/tools/` - **Change External Integrations here.** 
  - `db_tools.py`: Contains the SQL queries used by the Risk Assessment agent.
  - `vendor_notify.py`: Contains the logic for sending emails (Mocked currently, ready for SendGrid).
  - `keyword_builder.py`: Dynamically builds search queries based on the active suppliers in your DB.
- `frontend/app.py` - **Change the UI here.** The Streamlit dashboard that connects to the FastAPI backend via Server-Sent Events (SSE) to stream the AI's thoughts live.

---

## 🚀 Setup Guide for Teammates

### 1. Database Setup (PostgreSQL)
The system requires a SQL database to track inventory and suppliers.
1. Install PostgreSQL and ensure it is running.
2. Create a database named `fmcg_supply_chain`:
   ```sql
   CREATE DATABASE fmcg_supply_chain;
   ```
3. Update your `.env` file (see step 2) with the correct username and password (the default assumes `postgres` / `password`).

### 2. Environment Setup (`.env`)
Create a file named `.env` in the `backend/` directory. **NEVER push this file to GitHub.** This file configures how the system runs and which AI models it uses.

```env
# --- DATABASE ---
DATABASE_URL=postgresql://postgres:password@localhost:5432/fmcg_supply_chain

# --- LLM CONFIGURATION (HOW TO CHANGE MODELS) ---
# Set LLM_PROVIDER to 'ollama' (local), 'openai' (cloud), 'anthropic' (cloud), or 'mock' (testing)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
# If using OpenAI:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o

# --- SYSTEM VARIABLES ---
FACTORY_IDLE_COST_PER_DAY=5000.0

# --- EXTERNAL APIs ---
NEWS_API_KEY=your_newsapi_key_here
SENDGRID_API_KEY=your_sendgrid_key_here
```

### 3. Installing Local AI (Ollama)
If you want to run the AI entirely locally (free, secure, offline), you must install [Ollama](https://ollama.com/).
Once installed, open a terminal and pull the Llama model:
```bash
ollama run llama3.2
```

### 4. Installing Python Dependencies
You need Python 3.10+. We highly recommend using Conda or a virtual environment.
```bash
conda create -n fmcg_env python=3.11 -y
conda activate fmcg_env
pip install -r backend/requirements.txt
```

### 5. Seeding the Database (Crucial First Step!)
Before running the app, you must populate the empty database with our mock "Biscuit Factory" supply chain data.
```bash
cd backend
python seed.py
```

---

## 🏃‍♂️ Running the Application

You must run the Backend and the Frontend simultaneously in two separate terminals. Ensure your environment (`conda activate fmcg_env`) is active in both.

### Terminal 1: FastAPI Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
*Why? This starts the API that handles the database connections and runs the LangGraph AI pipeline.*

### Terminal 2: Streamlit Dashboard
```bash
cd frontend
streamlit run app.py
```
*Why? This starts the UI. It will automatically open a browser window at `http://localhost:8501`.*

---

## 🧪 Testing Workflows

To test if the agents are working, go to the **Disruption Console** in the Streamlit UI and paste different types of news to trigger different AI behaviors:

**1. To Trigger an Emergency Purchase Order (High Threat)**
> "Massive level-4 fire at the North region agricultural processing zone. Complete shutdown for 14 days."
*Result:* CFO will realize the factory will go idle, accept the premium price, and buy from a backup vendor in the South.

**2. To Trigger a Proactive Advisory (Medium Threat)**
> "Major traffic jam due to a marathon on NH-48 in the South. 5 hour delay."
*Result:* CFO will do the math, realize inventory is sufficient to survive a 5-hour delay, and instead instruct the Strategy agent to just email the vendor to dispatch early.

**3. To Trigger a "Hold and Monitor" (Low Threat)**
> "Minor labor protest in the West region, expecting a 1-day delay."
*Result:* CFO realizes we have plenty of stock and the delay is negligible, choosing to save money and do nothing.
