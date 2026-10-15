# CrimeGuard Backend

## Start on Windows

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If `uvicorn` is not recognized, always use `python -m uvicorn` as above.

## Test

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/api/health
- http://127.0.0.1:8000/docs

The root route now returns a JSON status instead of FastAPI's default 404.
