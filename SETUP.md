# Quant Center — setup guide (home + office)

Two GitHub repositories:

| Repo | Folder on laptop | Purpose |
|------|------------------|---------|
| [jhaavinaash/Quant](https://github.com/jhaavinaash/Quant) | `quant` | Engines, screener, orchestrator, data |
| [jhaavinaash/Quant-Center](https://github.com/jhaavinaash/Quant-Center) | `quant-center` | Website / dashboard (`app_ai.py`) |

## Folder paths (keep identical on both laptops)

| Machine | Quant (backend) | Quant-Center (website) |
|---------|-----------------|------------------------|
| Office | `C:\Users\dell\quant` | `C:\Users\dell\quant-center` |
| Home | `C:\Users\avinaash\quant` | `C:\Users\avinaash\quant-center` |

---

## First-time setup (home laptop)

### 1. Clone both repos

Open PowerShell:

```powershell
cd C:\Users\avinaash
git clone https://github.com/jhaavinaash/Quant.git quant
git clone https://github.com/jhaavinaash/Quant-Center.git quant-center
```

For **Quant-Center** (private repo), sign in to GitHub when Git asks.

### 2. Python environment (do this inside each folder)

**Backend (`quant`):**
```powershell
cd C:\Users\avinaash\quant
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

**Website (`quant-center`):**
```powershell
cd C:\Users\avinaash\quant-center
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Fill in `.env` with your Telegram, email, and Google Sheet values (same on both laptops).

### 3. Run the dashboard

```powershell
cd C:\Users\avinaash\quant-center
.\venv\Scripts\activate
streamlit run dashboard\app_ai.py
```

Browser opens at `http://localhost:8501`.

### 4. Run engines (backend folder)

```powershell
cd C:\Users\avinaash\quant
.\venv\Scripts\activate
python core\orchestrator.py
```

Or use **Run Engines** in the dashboard if `quant-center` includes the `Engines` folder.

---

## Daily sync (home ↔ office)

**Before work:**
```powershell
git pull
```

**After work:**
```powershell
git add .
git commit -m "describe what you changed"
git push
```

Do this in **both** `quant` and `quant-center` when you changed files in that project.

---

## Publish website files to Quant-Center (from `quant` repo)

If you edited the dashboard in the `quant` folder and need to copy changes to `quant-center`:

```powershell
cd C:\Users\avinaash\quant
.\scripts\sync_quant_center.ps1 -Target C:\Users\avinaash\quant-center
cd C:\Users\avinaash\quant-center
git add .
git commit -m "sync from quant"
git push
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: yfinance` | `pip install -r requirements.txt` inside venv |
| Alerts not sending | Check `.env` has Telegram + email values |
| `Run Engines` not found | Ensure `Engines` folder exists in quant-center, or run orchestrator from `quant` |
| `git pull` asks for login | Use GitHub Desktop or sign in: `gh auth login` |

---

## What was fixed in this update

- Complete `requirements.txt` (numpy, yfinance, feedparser, etc.)
- `config.py` finds `Data` / `Signals` / `Engines` folders reliably
- Secrets moved to `.env` (not stored in GitHub)
- `core/signal_alerts.py` added (dashboard alert button)
- `Data/nifty500_universe.csv` added for Gemini flasher
- Sync script to push web files to Quant-Center
