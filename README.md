# FA Tools

财务通用工具包。第一个 MVP 是银行流水转公司日记账。

## Local Backend

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
