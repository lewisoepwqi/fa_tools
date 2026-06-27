# FA Tools

财务通用工具包。第一个 MVP 是银行流水转日记账。

## Local Database

```bash
docker compose up -d postgres
```

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Verification

```bash
cd backend && pytest -q
cd frontend && npm run build && npm run e2e
```
