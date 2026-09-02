# Local setup

Getting the app running from a fresh clone/zip. Takes about 10 minutes.

## ⚠️ Python version matters

Use **Python 3.10 – 3.13**. Do **not** use Python 3.14.

`psycopg2-binary==2.9.10` (the Postgres driver) ships prebuilt wheels only up
to Python 3.13. On 3.14 pip tries to compile it from source and fails with:

```
Error: pg_config executable not found.
```

If you see that error, you're on the wrong Python version — that's the cause,
not a missing Postgres install. Check with `python --version`, and if you have
several versions installed, point the venv at a supported one explicitly:

```bash
# Windows
"C:\Users\<you>\AppData\Local\Programs\Python\Python313\python.exe" -m venv .venv
# macOS / Linux
python3.13 -m venv .venv
```

---

## 1. Dependencies

```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 2. PostgreSQL

The app needs a running Postgres. Easiest is Docker:

```bash
docker run -d --name paisa-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=paisa_db \
  -p 5432:5432 postgres:16-alpine
```

Already have Postgres installed? Just create a database named `paisa_db` and
adjust the URL in step 3 to match your own user/password.

## 3. Environment file

`.env` is deliberately not committed (it holds secrets). Create it from the
template:

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

Then set at minimum:

```
SECRET_KEY=any-long-random-string
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/paisa_db
```

`GEMINI_API_KEY` is optional — leave it blank. Without it the AI Coach shows a
setup notice and everything else works normally, including the health score,
priority engine, consent centre and purchase analyzer. Free key at
<https://aistudio.google.com/> if you want the coach live.

## 4. Create the schema

```bash
flask db upgrade
```

Expected output — two migrations:

```
Running upgrade  -> ae970c14e138, Initial schema
Running upgrade ae970c14e138 -> aaf9ee727619, Add user_type and consents
```

## 5. Run

```bash
python run.py
```

Open <http://127.0.0.1:5000>, sign up, and pick a user type (Student /
Micro-Entrepreneur / General).

---

## Note: the database starts empty

The zip contains code, not data — no users, accounts or transactions come with
it. A brand-new account shows empty dashboards until you add data. To see the
app do something interesting:

1. Sign up
2. **Finance → Profile**: set a monthly income and a category budget
3. **Accounts**: add an account with a balance
4. **Statements**: import a CSV, or add expenses manually

Only then does the Financial Health Score appear. This is deliberate — the
dashboard withholds a score rather than computing one from an empty ledger,
because zero logged spending would otherwise read as perfect frugality and
score ~90/100.

## Tests

```bash
# one-time: create the test database
docker exec paisa-postgres psql -U postgres -c "CREATE DATABASE paisa_test;"

pytest tests/ -q
```

61 tests, covering the consent engine, priority engine, health scoring and the
end-to-end demo scenario. The suite refuses to run unless it is pointed at a
database whose name contains `test`, so it can't touch your dev data.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `pg_config executable not found` | Python 3.14 — use 3.13 or lower (see top) |
| `connection refused` on port 5432 | Postgres isn't running; start the container |
| `relation "users" does not exist` | `flask db upgrade` hasn't been run |
| `429 Too Many Requests` on signup | Rate limit (10 signups/hour). Wait, or restart the app to clear the in-memory counter |
| `Bad Request: The referrer header is missing` | Only affects scripted POSTs over HTTPS, not browsers |
