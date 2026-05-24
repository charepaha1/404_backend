# Python backend for 404

Backend runs without external packages: only Python standard library and SQLite.

## Start

```powershell
py backend/server.py
```

API will be available at:

```text
http://localhost:8000/api
```

Default admin:

```text
email: admin@404.local
password: admin404
```

The SQLite database is created automatically at `backend/data/app.db`.

## Structure

```text
server.py    - starts the HTTP server
handler.py   - API routes and request handling
services.py  - business logic for auth, events, orders and admin actions
database.py  - SQLite connection, tables and seed data
schemas.py   - converts database rows to frontend JSON
auth.py      - passwords and token logic
config.py    - ports, paths and environment variables
utils.py     - small shared helpers
errors.py    - API error class
```

Useful environment variables:

```powershell
$env:BACKEND_PORT="8000"
$env:BACKEND_SECRET="replace-this-secret"
$env:BACKEND_DB="backend/data/app.db"
py backend/server.py
```
