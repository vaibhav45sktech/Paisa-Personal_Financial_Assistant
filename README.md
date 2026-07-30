# paisa. — Personal Wealth Manager

A full-featured personal-finance planner + wealth-manager built on
**Flask + PostgreSQL + Bootstrap 5**, with **Gemini AI Coach**, statement
import pipeline, dynamic health scoring, and a playful money-themed UI.

Currency: **INR (₹)**. Indian numbering everywhere.

---

## What's in it

| Area                        | What it does                                                                        |
|-----------------------------|-------------------------------------------------------------------------------------|
| **Auth**                    | Signup / login (email OR username), bcrypt hashing, CSRF, **lockout after 5 fails**, **Flask-Limiter** rate-limiting |
| **Financial Profile**       | Income type + 14-category monthly budget                                            |
| **Goals**                   | Multi-add goals with priority + target date + monthly-save hint                     |
| **Accounts**                | Bank / wallet / cash / credit-card / UPI                                            |
| **Assets**                  | FD / gold / stocks / mutual funds / property / crypto                               |
| **Statement Import**        | CSV upload → auto-parse → auto-categorize → review UI → confirm → creates Expenses/Income → updates balances |
| **Budgets**                 | Per-category monthly budgets · **Chart.js** Actual-vs-Budgeted                      |
| **Financial Health Score**  | 0-100 with 5 sub-scores (Emergency 30, Savings 20, DTI 25, Investments 10, Discipline 15). Rendered as an **animated SVG face + arc dial** that gets happier as your score rises |
| **AI Financial Coach**      | Multi-turn Gemini chat, seeded with your live financials, proactive weekly insights |
| **Purchase Impact Analyzer**| EMI calculator + affordability status (Affordable / Borderline / Danger) + recommendations |
| **Notifications**           | Alerts, warnings, coach nudges — with unread pulse-dot badge in navbar              |
| **Reports**                 | Printable monthly report → browser print → save as PDF                              |
| **Fun UI**                  | Money-bill cursor everywhere · confetti on Excellent health scores · coin-emoji drops on primary buttons · blinking eyes & morphing mouth on health face · coin-flip brand badge · bounce-in cards |

---

## Tech Stack

| Layer     | Tech                                                                 |
| --------- | -------------------------------------------------------------------- |
| Backend   | Flask 3 (App Factory + Blueprints), SQLAlchemy 2, Alembic migrations |
| Auth      | Flask-Login (session) + Flask-Bcrypt                                 |
| Forms     | Flask-WTF + WTForms (CSRF + server-side validation)                  |
| Rate-lim  | Flask-Limiter (in-memory default; swap to Redis for prod)            |
| DB        | PostgreSQL (UUID PKs, FKs with cascade)                              |
| UI        | Bootstrap 5 + Bootstrap Icons + Chart.js + Outfit/Figtree fonts      |
| AI        | Gemini 2.5 Flash via `google-genai` SDK (optional; graceful fallback)|
| Fun       | Inline SVG cursor + CSS keyframes + JS confetti/coin-drops           |

---

## Folder structure

personal_finance_assistant/
├── run.py                          # Application entry point
├── config.py                       # Configuration classes (Dev, Prod, Test)
├── requirements.txt                # Python dependencies
├── .env.example                    # Template for environment variables
├── README.md                       # Documentation
├── migrations/                     # Alembic migration scripts
└── app/
    ├── __init__.py                 # create_app() application factory
    ├── extensions.py               # db, migrate, login_manager, bcrypt, csrf, limiter
    ├── models/                     # 14 ORM models across 10 modular files
    │   ├── user.py                 # UserMixin, UUID PK, login lockout logic
    │   ├── financial_profile.py    # Income profile & budget categories
    │   ├── financial_goal.py       # Goal details & priorities
    │   └── ...                     # Accounts, Assets, Transactions, Notifications
    ├── services/                   # Application Business Logic
    │   ├── parser_service.py       # CSV statement parser
    │   ├── pdf_parser.py          # PDF statement parser (optional via pdfplumber)
    │   ├── categorizer_service.py # Rule-based + Gemini AI fallback categorizer
    │   ├── statement_service.py   # Statement ingestion pipeline
    │   ├── health_engine.py       # Health Score & Net Worth calculations
    │   ├── dashboard_service.py   # Budget aggregates & actual vs. expected calculations
    │   ├── ai_service.py          # Gemini AI Coach integration
    │   ├── analyzer_service.py    # EMI calculation & purchase affordability engine
    │   └── notification_service.py# Alert & warning dispatcher
    ├── auth/                       # Blueprint: /auth (Login, Signup, Logout)
    ├── main/                       # Blueprint: / (Landing Page)
    ├── dashboard/                  # Blueprint: /dashboard
    ├── finance/                   # Blueprint: /finance (Profile setup, Goals)
    ├── accounts/                   # Blueprint: /accounts (Bank/Wallet management)
    ├── statements/                 # Blueprint: /statements (Upload & Review pipeline)
    ├── budgets/                    # Blueprint: /budgets (Category allocations)
    ├── ai_coach/                   # Blueprint: /coach (Gemini multi-turn chat)
    ├── analyzer/                   # Blueprint: /analyzer (Purchase impact calculator)
    ├── notifications/              # Blueprint: /notifications
    ├── reports/                    # Blueprint: /reports (Monthly printable exports)
    ├── templates/                  # Jinja2 template hierarchy organized by blueprint
    └── static/
        ├── css/style.css           # Custom styling, keyframes, cursor & health face styles
        └── js/main.js              # Live budget totals, goal cloning, confetti & coin drops
---

## Local setup

```bash
# 1. Clone / unzip and cd into the folder
cd personal_finance_assistant

# 2. Create + activate a virtual env
python -m venv .venv
.venv\Scripts\activate    # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create the Postgres database
createdb paisa_db                # or: psql -c "CREATE DATABASE paisa_db;"

# 5. Copy env template and edit values
cp .env.example .env
#   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
#   DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/paisa_db

# 6. Initialise migrations + create tables
export FLASK_APP=run.py
flask db init                    # first time only
flask db migrate -m "initial schema"
flask db upgrade

# 7. Run the app
flask run --host 0.0.0.0 --port 5000
#   or:   python run.py
```

Open **http://localhost:5000**.

> The initial migration is bundled. On future schema changes:
> `flask db migrate -m "your msg"` → `flask db upgrade`.

---

## Guided flow after signup

1. **Set your Financial Profile** (income + 14-category budget) — you land here right after signup.
2. **Add your Goals** (name / amount / date / priority).
3. **Add an Account** at `/accounts/new` (e.g. HDFC Savings, ₹120,000).
4. **Upload a CSV statement** at `/statements/upload`:
   - Columns: `Date, Description, Amount`  *(positive = credit, negative = debit)*
   - OR `Date, Description, Debit, Credit`
5. Review the auto-categorised rows → change any dropdown → **Confirm selected**.
6. **Set your monthly budgets** at `/budgets/` (icons come from the auto-seeded 20 default categories).
7. **Dashboard** now shows your animated Financial Health Score face,
   Net Worth, Actual-vs-Budgeted bars, and quick-action tiles.
8. Try the **AI Coach** (`/coach/`) — ask "How can I save more this month?"
9. Try the **Purchase Analyzer** (`/analyzer/`) — enter a bike price and see if
   the EMI would strain your income.
10. Hit **Reports** (`/reports/`) → **Save as PDF** for a monthly summary.

---

## Enabling the AI Coach (Gemini free tier)

Get a free key at [aistudio.google.com](https://aistudio.google.com/) (15 req/min, 1M tokens/day free).

```bash
echo 'GEMINI_API_KEY=your-key-here' >> .env
# google-genai is already pinned in requirements.txt
```

Restart the app. `/coach/` now uses live Gemini responses seeded with your
financial context (health score, net worth, monthly income/spend, goals).
Insights on the empty-chat screen are also Gemini-generated.

Without a key, the Coach page still loads and shows a friendly "add your API
key" message. Nothing else in the app depends on Gemini.

---

## Financial Health Score

Computed on every dashboard load — nothing is stored.

| Component            | Max | What we measure                                     |
|----------------------|-----|-----------------------------------------------------|
| Emergency fund ratio | 30  | Liquid cash / monthly expenses (target 6 months)    |
| Savings rate         | 20  | (Income − Expenses) / Income   (target 30%)         |
| Debt-to-Income (DTI) | 25  | EMI-category spend / Income                         |
| Investment ratio     | 10  | Invested assets / total wealth (target 40%)         |
| Budget discipline    | 15  | Actual vs budgeted variance                         |

Grades: **85+ Excellent** · 70+ Good · 50+ Fair · 30+ Needs work · below **Critical**.

The face changes with your grade: 😄 → 🙂 → 😐 → 😟 → 😱. Score 85+ triggers **confetti**.

---

## Security

- Bcrypt hashed passwords (never stored in plaintext)
- CSRF token on every POST via Flask-WTF
- All authenticated routes guarded with `@login_required`
- Flask-Limiter rate-limits: `20/hour` on `/auth/login`, `10/hour` on `/auth/signup`
- Login lockout after **5 failed attempts** (`is_locked` on `User`)
- Uploaded statements are streamed & parsed **in memory** — never written to disk
- Session cookies `HttpOnly`; `Secure` in production

---

## Environment variables

| Var             | Purpose                                          |
| --------------- | ------------------------------------------------ |
| `SECRET_KEY`    | Flask session signing key                        |
| `DATABASE_URL`  | SQLAlchemy connection URI (Postgres)             |
| `FLASK_APP`     | `run.py`                                         |
| `FLASK_ENV`     | `development` or `production`                    |
| `GEMINI_API_KEY`| Gemini AI Coach (optional; free tier available)  |

---

## Roadmap

Shipped: Auth + lockout · Profile · Goals · Accounts · Assets · Statement
import + review + confirm · Auto-categorization (rule-based + Gemini
fallback) · Budgets + Actual-vs-Budget · Financial Health Score with animated
face · Net Worth · AI Coach chat with proactive insights · Purchase Impact
Analyzer · Notifications · Printable Reports · Money-bill cursor · Confetti ·
Coin-drop animations.

Still open:

- [ ] PDF statement parsing (`pdfplumber` is wired — enable in requirements to activate)
- [ ] Reportlab-based server-side PDF generation (currently uses browser print)
- [ ] Automated weekly-digest notifications (cron / apscheduler)
- [ ] Password reset (email-based) + Flask-Mail
- [ ] Plaid / Yodlee live bank sync

---

## License

MIT.
