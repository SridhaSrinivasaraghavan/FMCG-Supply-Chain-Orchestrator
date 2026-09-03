# 🏭 Autonomous Multi-Agent FMCG Supply Chain Orchestrator

Welcome to the **Autonomous Supply Chain Orchestrator**. This system acts as a fully autonomous "Brain" for a Fast-Moving Consumer Goods (FMCG) company. It constantly monitors global news, assesses logistical and supplier risks, calculates financial trade-offs in real-time, and executes mitigation strategies (like emergency Purchase Orders) to ensure factories never go idle.

Built with **FastAPI** (Backend), **LangGraph** (Multi-Agent Orchestration), **PostgreSQL** (Database), and **Streamlit** (Live Streaming Frontend).

---

## 🧠 The Multi-Agent Workflow Explained

The autonomous supply chain management system processes unstructured external data through a series of specialized LLM (Large Language Model) agents, cross-references findings with a relational database, and executes deterministic financial optimization before taking action.

### System Architecture Flowchart

```mermaid
flowchart TD
    classDef process fill:#ffffff,stroke:#333333,stroke-width:2px,color:#000000
    classDef agent fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#000000
    classDef db fill:#fef08a,stroke:#ca8a04,stroke-width:2px,color:#000000
    classDef action fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#000000
    classDef human fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#000000

    SCRAPER[News Scraper Module]:::process
    
    subgraph Pipeline [Multi-Agent AI Pipeline]
        MIA[1. Market Intel Agent]:::agent
        RAA[2. Risk Assessment Agent]:::agent
        FAA[3. Financial Analyst Agent]:::agent
        SEA[4. Strategy Execution Agent]:::agent
    end

    subgraph Data [Database & Logs]
        DB[(Relational DB)]:::db
        LOG[(Disruption Logs)]:::db
    end

    Q{Decision Routing}:::process
    
    AUTO_PO[Auto-Execute PO]:::action
    ADV[Send Advisory]:::action
    HOLD[Hold & Monitor]:::action
    HUMAN[Approval Queue]:::human

    SCRAPER -->|Raw News| MIA
    
    MIA -->|Threat| RAA
    RAA -->|Impact| FAA
    FAA -->|Optimization| Q
    
    DB -.->|Routes| RAA
    DB -.->|Stock| FAA
    
    Q -->|High Stock| ADV
    Q -->|Low Impact| HOLD
    Q -->|Critical Stock| AUTO_PO
    Q -->|Over Ceiling| HUMAN
    
    ADV --> SEA
    HOLD --> SEA
    AUTO_PO --> SEA
    HUMAN -.->|Approval| SEA
    
    SEA --> LOG
```

### Workflow Execution

The pipeline operates sequentially, ensuring that unstructured data is structurally validated and quantified before any action is executed. 

**1. Ingestion & Market Intelligence Layer**
The workflow initiates when the **News Scraper Module** continuously monitors online news sources, filtering articles via supply-chain-specific keywords. When a relevant article is scraped, it is passed to the **Market Intel Agent**. This agent parses the unstructured text, leveraging a predefined delay inference matrix to estimate logistical delays based on the event type. It outputs a strict JSON payload containing the event severity, geographic region, and an AI confidence score.

**2. Network Risk Assessment Layer**
The validated threat payload is passed to the **Risk Assessment Agent**. This agent queries the underlying relational database to retrieve active transport routes, supplier locations, and current shipments. By intersecting the geographic threat data with the physical supply chain map, the agent identifies specific raw materials that are currently traveling through or originating from the compromised region.

**3. Financial Optimization Layer**
With the at-risk materials identified, the **Financial Analyst (CFO) Agent** calculates the exact financial exposure. It queries the Bill of Materials (BOM) to determine daily factory consumption rates and compares them against current inventory buffer stocks. If the estimated delay exceeds the buffer stock, the agent calculates the **Factory Idle Cost** against the **Backup Premium**. The agent utilizes deterministic mathematical models to find the financially optimal decision, and then generates an explicit rationale explaining the logic.

**4. Strategy Execution and Human-in-the-Loop**
The decisions are routed based on predefined business parameters:
- **Autonomous Execution:** If an emergency purchase order is financially optimal and falls below the maximum auto-approval cost ceiling (with high AI confidence), the **Strategy Execution Agent** immediately issues the Purchase Order (PO) to the backup supplier.
- **Proactive Advisories:** If the factory has sufficient inventory to weather the delay, the system avoids unnecessary premium costs and instead autonomously emails suppliers to adjust dispatch schedules.
- **Approval Queue (Human-in-the-loop):** If a proposed Purchase Order exceeds the financial ceiling, or if the initial Market Intel Agent reported a low confidence score, the action is safely halted. It is placed into an administrative **Approval Queue** where a human operator can review the compiled LLM reasonings, financial calculations, and proposed costs before manually approving or rejecting the order. 

All actions, including the comprehensive reasoning generated by each agent at every step, are permanently stored in the **Disruption Logs** for auditing and transparency.

---

## ✨ Key Features

- **Real-Time News Ingestion**: Monitors and ingests live logistical, weather, and geopolitical news via keyword filtering.
- **LLM-Powered Intelligence (LangGraph)**: Utilizes large language models to structure unstructured text, infer geographic impact, and calculate supply chain delays.
- **Deterministic Math + AI Reasoning**: Intersects LLM reasoning with hard constraints. The Financial Analyst Agent calculates raw numbers (Bill of Materials, Factory Idle Costs) *before* applying AI logic.
- **Autonomous Strategy Execution**: The system can draft emails, re-route supply chains, and issue emergency purchase orders autonomously without human intervention.
- **Human-in-the-Loop Safety Net**: High-risk, high-cost, or low-confidence decisions are automatically blocked and routed to an Approval Queue for human review.

## 🖥️ Frontend Architecture (Streamlit)

The system features a rich, live-updating Streamlit dashboard connected to the FastAPI backend via Server-Sent Events (SSE). 

1. **The Disruption Console (Live Stream)**
   - Displays real-time, step-by-step thoughts of each AI agent as they process a disruption.
   - Expandable UI blocks reveal the raw structured JSON payload, geographic region mappings, and detailed CFO rationales.
2. **Approval Queue Dashboard**
   - A dedicated administrative panel for Human-in-the-Loop review.
   - Presents pending high-cost Purchase Orders alongside the original threat context, impacted BOM calculations, and the CFO's explicit reasoning.
   - Admins can instantly "Approve" or "Reject" via interactive buttons.
3. **Disruption Logs (Audit Trail)**
   - A historical ledger of all processed disruptions.
   - Allows supply chain managers to review past incidents, autonomous actions taken, and the underlying mathematical justification for those actions.

## ⚠️ Edge Cases Handled

- **LLM Hallucinations**: Protected by strict Pydantic schemas in the inter-agent validation layer. If an LLM fabricates a material or region, the system safely falls back to defaults or drops the hallucination before executing a purchase.
- **Ambiguous News**: The Market Intel agent applies a "Confidence Score". If an article is vague or unrelated to the supply chain, it refuses to auto-execute and flags the action for human review in the Approval Queue.
- **Sufficient Buffer Stocks**: The system avoids panic-buying. If a 15-day delay hits but the factory has 20 days of buffer stock, the system intelligently issues a `PROACTIVE_ADVISORY` rather than wasting capital on premium backup suppliers.

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

**4. To Trigger the Human-in-the-Loop Edge Case (Ambiguous/Low Confidence)**
> "There are rumors on social media that something might happen near the ports eventually."
*Result:* The Market Intel Agent extracts a low confidence score (< 60%). The system refuses to auto-execute any backups and kicks the disruption straight to the Approval Queue for a human to verify the rumor.
