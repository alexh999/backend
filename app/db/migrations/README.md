# Database Migrations

The repository uses Alembic for schema migrations.

Run from the backend root:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

The first migration creates the shared `users` table.
