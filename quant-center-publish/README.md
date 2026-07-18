# Quant Center — Trading Desk (website)

React website + FastAPI backend + Streamlit dashboard for your quant trading system.

| Part | Folder | What it is |
|------|--------|------------|
| **Website (new UI)** | `frontend/` | React app — open in browser |
| **API** | `backend/` | FastAPI server |
| **Classic dashboard** | `dashboard/app_ai.py` | Streamlit UI (original) |
| **Engines (separate repo)** | [Quant](https://github.com/jhaavinaash/Quant) | Screener + orchestrator |

---

## Folder on your laptop

| Machine | This repo | Quant engines repo |
|---------|-----------|-------------------|
| **Home** | `C:\Users\avinaash\quant-center` | `C:\Users\avinaash\quant` |
| **Office** | `C:\Users\dell\quant-center` | `C:\Users\dell\quant` |

**Git rule:** Push from **home** → Pull at **office**.

---

## First-time setup (home PC)

### 1. Clone this repo

```powershell
cd C:\Users\avinaash
git clone https://github.com/jhaavinaash/Quant-Center.git quant-center
cd quant-center
```

### 2. Create `.env`

```powershell
copy .env.example .env
notepad .env
```

Fill in passwords and paths. Use `C:\Users\avinaash\quant` for `QUANT_BASE_DIR`.

### 3. Website — install and run

**Terminal 1 — database + API:**
```powershell
cd C:\Users\avinaash\quant-center
docker compose up -d db
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python create_tables.py
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — React website:**
```powershell
cd C:\Users\avinaash\quant-center\frontend
npm install
npm run dev
```

Open: **http://localhost:5173**

Register first user:
```powershell
curl -X POST http://127.0.0.1:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"email\":\"you@example.com\",\"username\":\"trader\",\"password\":\"password123\"}"
```

### 4. Streamlit dashboard (classic UI)

```powershell
cd C:\Users\avinaash\quant-center
python -m venv venv-streamlit
.\venv-streamlit\Scripts\activate
pip install -r streamlit-requirements.txt
streamlit run dashboard\app_ai.py
```

Open: **http://localhost:8501**

---

## Push from home / pull at office

**Home (after changes):**
```powershell
cd C:\Users\avinaash\quant-center
git add .
git commit -m "update from home"
git push
```

**Office (get latest):**
```powershell
cd C:\Users\dell\quant-center
git pull
```

Same for the `quant` folder (engines repo).

---

## What’s in this repo

```
quant-center/
├── frontend/          ← React website (npm run dev)
├── backend/           ← FastAPI API (port 8000)
├── dashboard/         ← Streamlit app_ai.py
├── core/              ← Shared Python modules
├── Data/              ← CSV data for dashboard
├── Signals/           ← master_signals.csv
├── Portfolio/         ← trades_log.csv
├── Engines/           ← engine scripts (Run Engines button)
├── docker-compose.yml ← PostgreSQL + backend
└── .env.example       ← copy to .env
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Website blank / API error | Check backend running on port 8000 |
| `npm run build` fails | Run `npm install` in `frontend/` |
| Streamlit import error | `pip install -r streamlit-requirements.txt` |
| Engines not found | Clone [Quant](https://github.com/jhaavinaash/Quant) to `quant` folder and set `QUANT_BASE_DIR` in `.env` |

---

GitHub: https://github.com/jhaavinaash/Quant-Center
