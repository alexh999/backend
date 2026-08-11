# StockApp Backend

Independent FastAPI backend project for the StockApp Flutter app.

This repository is separate from:

```text
D:\stockapp\flutter_stockapp
```

The Flutter application lives at:

```text
D:\stockapp\flutter_stockapp
```

## Current Scope

Phase 1 only creates the backend skeleton and the Health endpoint.

Implemented:

- FastAPI application entrypoint
- Versioned API router
- Health endpoint at `GET /api/v1/health`
- Minimal environment-based settings
- Minimal standard-library logging setup
- Minimal shared exception handling
- CORS registration from settings
- Health endpoint test

Skeleton only:

- `auth`
- `users`
- `market`
- `quant`
- `ai`
- `news`
- `tutorial`
- `forum`
- `db`
- `integrations/pandaai`
- `integrations/qlib`
- `integrations/siliconflow`

Not implemented in Phase 1:

- Database connections or tables
- Login or registration
- JWT or password hashing
- PandaAI calls
- Qlib execution
- SiliconFlow calls
- Market, Quant, AI, News, Forum, or Tutorial APIs
- Fake business data

## Python

This project was created with Python 3.12.13.

## Setup

Run these commands in Windows PowerShell:

```powershell
Set-Location D:\stockapp\backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

If the virtual environment does not exist yet:

```powershell
Set-Location D:\stockapp\backend
C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Run

After merging or pulling new code, prefer the PowerShell startup script. It applies
all Alembic migrations first and starts Uvicorn only if the database upgrade
succeeds:

```powershell
Set-Location D:\stockapp\backend
.\start_backend.ps1
```

Double-click entry:

```text
D:\stockapp\backend\start_backend.bat
```

Manual command:

```powershell
Set-Location D:\stockapp\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health endpoint:

```text
GET http://127.0.0.1:8000/api/v1/health
```

Android emulator example:

```text
GET http://10.0.2.2:8000/api/v1/health
```

## Test

```powershell
Set-Location D:\stockapp\backend
.\.venv\Scripts\python.exe -m pytest
```

## CORS

`CORS_ORIGINS` is configured for local development in `.env.example`.
Production origins should be set explicitly through environment variables and should not use a permanent wildcard without a concrete reason.
