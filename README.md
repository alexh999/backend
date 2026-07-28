# StockApp Backend

FastAPI backend for the Flutter app in `D:\stockapp\flutter_stockapp`.

## Current Scope

Implemented now:

- FastAPI application entrypoint
- Versioned API router
- Health endpoint at `GET /api/v1/health`
- Market stock detail endpoint at `GET /api/v1/market/stocks/{symbol}/detail`
- PandaAI-backed market integration with internal response mapping
- Environment-based settings, logging, exception handling, and CORS setup

## Python

Use Python `3.12`.

## Local Setup

1. Install dependencies:

```powershell
Set-Location D:\stockapp\backend-main
& 'F:\python 3.12\python.exe' -m pip install -e ".[dev]"
```

2. Ensure `D:\stockapp\backend-main\.env` exists.

`PANDAAI_USERNAME` and `PANDAAI_PASSWORD` must be stored in `.env` only.

## Run

Preferred local start command:

```powershell
Set-Location D:\stockapp\backend-main
.\scripts\start-dev.ps1
```

If `8010` is already occupied by an old backend instance:

```powershell
Set-Location D:\stockapp\backend-main
.\scripts\stop-dev.ps1
```

Manual alternative:

```powershell
Set-Location D:\stockapp\backend-main
& 'F:\python 3.12\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

Useful URLs:

```text
Health:  http://127.0.0.1:8010/api/v1/health
Detail:  http://127.0.0.1:8010/api/v1/market/stocks/AAPL/detail
Emulator: http://10.0.2.2:8010/api/v1/health
```

## Test

```powershell
Set-Location D:\stockapp\backend-main
& 'F:\python 3.12\python.exe' -m pytest
```

## Notes

- Real credentials must never be committed.
- `.env.example` is only a template.
- Flutter Android emulator traffic should use `http://10.0.2.2:8010`.
