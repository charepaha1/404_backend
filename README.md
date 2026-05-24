# Python backend for 404

Backend stores data in MongoDB.

## Start

```powershell
cd backend
python -m pip install -r requirements.txt
python server.py
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

MongoDB database is created automatically. Defaults:

```text
MONGO_URI=mongodb://localhost:27017
MONGO_DB=diplom_404
```

To migrate old SQLite data from `backend/data/app.db`:

```powershell
python migrate_sqlite_to_mongo.py
```

## Structure

```text
server.py    - starts the HTTP server
handler.py   - API routes and request handling
services.py  - business logic for auth, events, orders and admin actions
database.py  - MongoDB connection, indexes and seed data
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
$env:MONGO_URI="mongodb://localhost:27017"
$env:MONGO_DB="diplom_404"
python backend/server.py
```
