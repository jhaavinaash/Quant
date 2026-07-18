@echo off
REM Quant-Center first-time setup (Windows)
echo === Quant Center Setup ===
cd /d %~dp0

if not exist .env (
  copy .env.example .env
  echo Created .env - please edit with your passwords and paths.
)

echo.
echo [1/3] Backend Python venv...
cd backend
if not exist venv python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
cd ..

echo.
echo [2/3] Frontend npm install...
cd frontend
call npm install
cd ..

echo.
echo [3/3] Streamlit venv...
if not exist venv-streamlit python -m venv venv-streamlit
call venv-streamlit\Scripts\activate
pip install -r streamlit-requirements.txt
deactivate

echo.
echo Done. Next steps:
echo   1. Edit .env with your settings
echo   2. docker compose up -d db
echo   3. cd backend ^&^& venv\Scripts\activate ^&^& python create_tables.py ^&^& uvicorn app.main:app --reload
echo   4. cd frontend ^&^& npm run dev
echo   5. streamlit run dashboard\app_ai.py
