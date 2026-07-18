# Quant — trading engines & screener

Backend for the Quant Center system: engines, orchestrator, data, and signals.

**Website / dashboard** lives in a separate repo: [Quant-Center](https://github.com/jhaavinaash/Quant-Center)

## Setup (home or office)

See **[SETUP.md](SETUP.md)** for full instructions.

Quick start:

```powershell
cd C:\Users\avinaash\quant
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python core\orchestrator.py
```

Dashboard: clone `quant-center` and run `streamlit run dashboard\app_ai.py`
