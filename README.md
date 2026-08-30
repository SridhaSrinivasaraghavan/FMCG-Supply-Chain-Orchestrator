# Autonomous Multi-Agent FMCG Supply Chain orchestrator 🏭🤖

An intelligent, multi-agent supply chain management system built with **FastAPI**, **LangGraph**, and **Streamlit**. This system autonomously scans the web for supply chain disruptions, evaluates risks, calculates financial impacts of idle factories vs. backup premiums, and autonomously executes mitigation strategies (like emergency Purchase Orders).

## Architecture

This project uses a 4-Agent LangGraph Pipeline:
1. **Market Intel Agent**: Extracts structured threat data from unstructured news.
2. **Risk Assessment Agent**: Cross-references threats with the PostgreSQL database to find vulnerable routes, materials, and available backup suppliers.
3. **Financial Analyst Agent (CFO)**: Calculates days of inventory remaining vs. delay duration, computes factory idle costs vs. backup vendor premiums, and makes a strategic "Hold", "Buy", or "Proactive Advisory" decision.
4. **Strategy Execution Agent**: Executes the CFO's decision by drafting emails and logging actions back to the database.

---

## 🚀 Setup Guide for Teammates

### 1. Prerequisites
- **Python 3.10+** (Conda recommended)
- **PostgreSQL** (Running locally on port 5432)
- **Ollama** (For local LLM inference)

### 2. Database Setup
1. Create a PostgreSQL database named `fmcg_supply_chain`.
   ```sql
   CREATE DATABASE fmcg_supply_chain;
   ```
2. The credentials are expected to be:
   - User: `postgres`
   - Password: `password` (Change this in your `.env` if different)

### 3. Environment Variables (`.env`)
Create a file named `.env` in the `backend/` directory. **NEVER push this file to GitHub.**
```env
# backend/.env
DATABASE_URL=postgresql://postgres:password@localhost:5432/fmcg_supply_chain

# API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
NEWS_API_KEY=your_newsapi_key_here
SENDGRID_API_KEY=your_sendgrid_key_here

# LLM Configuration
# Set to 'ollama' for local, 'openai' for GPT-4, or 'anthropic' for Claude
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
FACTORY_IDLE_COST_PER_DAY=5000.0
```

### 4. Install Local LLM (Ollama)
If using `LLM_PROVIDER=ollama`, you must install [Ollama](https://ollama.com/) on your machine.
Once installed, open a terminal and pull the Llama 3.2 model:
```bash
ollama run llama3.2
```

### 5. Install Python Dependencies
Open your terminal, create your environment, and install requirements:
```bash
conda create -n fmcg_env python=3.11 -y
conda activate fmcg_env
pip install -r backend/requirements.txt
```

### 6. Seed the Database
Run the seed script to create the tables and populate them with the mock Biscuit Factory data:
```bash
cd backend
python seed.py
```

---

## 🏃‍♂️ Running the Application

You will need **two terminal windows**. Ensure your Conda environment (`fmcg_env`) is activated in both.

### Terminal 1: The FastAPI Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### Terminal 2: The Streamlit Dashboard
```bash
cd frontend
streamlit run app.py
```

Open your browser to `http://localhost:8501`. 

## Testing the Pipeline
Go to the **Disruption Console** in the Streamlit UI. Paste a mock news article about a fire in the "North" region or a traffic jam on "NH-48", and watch the agents autonomously mitigate the risk via the live streaming terminal!
