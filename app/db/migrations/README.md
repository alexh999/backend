# Database Migrations

The repository uses Alembic for schema migrations.

Run from the backend root:

```powershell
.\\.venv\\Scripts\\python.exe -m alembic upgrade head
```

The first migration creates the shared `users` table. Existing paper-trading
tables remain managed by the current development startup path until they receive
their own explicit migration; this migration does not drop, recreate, or alter
those tables.
