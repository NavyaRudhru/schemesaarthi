SCHEMESAARTHI AI PROJECT BUNDLE

Open this folder in VS Code. Start backend and frontend in two PowerShell terminals.
Detailed setup, admin bootstrap, API list, tests and troubleshooting are in README.md.

Backend: cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; Copy-Item .env.example .env; python scripts_seed.py; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Frontend: cd frontend; Copy-Item .env.example .env; npm install; npm run dev
Open http://localhost:5173
API docs: http://127.0.0.1:8000/docs
