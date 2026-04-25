# nicheBrains — Backend

Flask + SQLAlchemy + Flask-RESTX + CrewAI. Implements the deterministic
scoring engine, multi-tenant data layer, REST API with auto-generated
Swagger documentation, and the two-agent CrewAI orchestration.

---

## Folder structure

```
backend/
├── app/
│   ├── __init__.py             create_app() factory
│   ├── extensions/             db, jwt, cors initialisers
│   ├── api/
│   │   └── v1/
│   │       ├── namespaces/     One Flask-RESTX Namespace per resource
│   │       │   ├── auth.py         POST /auth/login, /auth/register
│   │       │   ├── users.py        /users/me
│   │       │   ├── firms.py        /firms, /firms/{id}/financials
│   │       │   ├── snapshot.py     /snapshot/{sector}   (W0.0 read-only)
│   │       │   ├── prescreener.py  /prescreener/        (W0.1 6-Q band)
│   │       │   ├── nra.py          /nra/                (W1 40-Q dTAS v2)
│   │       │   ├── charters.py     /charters/draft, /charters/{id}/approve
│   │       │   ├── experts.py      /experts, /experts/match/{charterId}
│   │       │   ├── partner.py      /partner/cohort/{sector}, /distribution
│   │       │   ├── admin.py        /admin/users, /admin/users/{id}/modules
│   │       │   └── platform.py     /platform/overview, /architecture, /benchmarks
│   │       └── security.py     login_required, role_required, module_required
│   ├── agents/
│   │   └── crews/              CrewAI surface — exactly TWO agents (Narrator + Drafter)
│   ├── models/                 SQLAlchemy ORM (every model carries tenant_id)
│   │   ├── base.py                 TenantScopedMixin, TimestampMixin
│   │   ├── tenant.py
│   │   ├── user.py                 + UserRole enum
│   │   ├── permission.py           UserModulePermission (admin RBAC)
│   │   ├── person.py               + sub_persona (v3.1)
│   │   ├── reference.py            Sector, Dimension catalogues
│   │   ├── firm.py
│   │   ├── financials.py           FirmFinancials (P&L + BS for ROIC)
│   │   ├── assessment.py           AssessmentRun + Score + Horizon/Priority/Transformation
│   │   ├── charter.py              Charter, Milestone, Match
│   │   ├── engagement.py           Engagement, Outcome
│   │   ├── expert.py
│   │   ├── partner.py
│   │   └── evidence.py             Polymorphic L0-L4 evidence records
│   ├── services/
│   │   ├── scoring/
│   │   │   ├── engine.py           banker_round, boundary_snap, classify_band
│   │   │   ├── questions.py        40-Q dTAS v2 catalogue (5 dims × 8 Qs)
│   │   │   ├── rules.py            young-firm floor, skip resolution, contradictions
│   │   │   └── transformation.py   v3.1 Table 4 inference (with Hybrid ≤5pt rule)
│   │   ├── value_creation/         ROIC = OpMargin × CapTurnover × (1−ETR)
│   │   ├── ranking/
│   │   │   ├── initiative_ranker.py    impact × feasibility, 3–5 shortlist
│   │   │   └── expert_ranker.py        top-3, requires ≥1 L0/L3 anchor
│   │   ├── snapshot_service.py     READ-ONLY (AC#9)
│   │   ├── nra_service.py
│   │   ├── charter_service.py      DRAFT only — agents never sign
│   │   ├── matching_service.py
│   │   ├── partner_service.py      cohort_benchmark + distribution; min 10 (v3.1)
│   │   ├── benchmarks.py           v3.1 Table 5 promotion gates
│   │   └── modules.py              17-module catalogue + ROLE_DEFAULTS
│   ├── seed/
│   │   ├── seed_data.py            Reference data + demo tenants/users
│   │   └── migrate_v31.py          Idempotent v3.1 column-add migration
│   └── utils/
│       └── citations.py            L-pill checker (AC#4)
├── tests/
│   └── unit/
│       ├── test_scoring.py         Determinism + 35/65/85 unreachability
│       └── test_rankers.py
├── manage.py                       CLI: init-db | seed | migrate
├── wsgi.py                         Entry point (gunicorn-compatible)
├── requirements.txt
├── pytest.ini
├── .env.example
└── .python-version                 3.12
```

---

## Setup

### 1. Python version

**Use Python 3.12.** Some CrewAI transitive deps (older `chromadb`,
`tokenizers`, `pydantic-core` wheels) raise:

```
TypeError: Can't replace canonical symbol for '__firstlineno__' with new int value 615
```

on Python 3.13. The lower-bound pins in `requirements.txt`
(chromadb≥0.5.20, tokenizers≥0.20, pydantic-core≥2.27) avoid this on 3.13
**if** up-to-date wheels are available, but 3.12 is the safe default. A
`.python-version` file is included for pyenv / asdf users.

### 2. Install

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env                      # set OPENAI_API_KEY at minimum
```

### 3. Initialise the database

```bash
python manage.py seed                     # creates tables + reference data + demo tenants
```

### 4. Run

```bash
python wsgi.py                            # dev server on http://localhost:5000
```

| URL                                  | What                  |
|--------------------------------------|-----------------------|
| `http://localhost:5000/api/v1/docs/` | Swagger UI            |
| `http://localhost:5000/healthz`      | Liveness probe        |

---

## CLI commands (`python manage.py <cmd>`)

| Command   | Effect                                                        |
|-----------|---------------------------------------------------------------|
| `init-db` | `db.create_all()` — tables only, no data                      |
| `seed`    | Tables + reference data (sectors, dimensions) + demo tenants  |
| `migrate` | Idempotent ALTER TABLE for v3.1 column additions (see below)  |

### `migrate` — when to run it

If you upgrade an existing database from v5.0 → v3.1, run:

```bash
python manage.py migrate
```

Expected output the first time:

```
[ok] applied 7 migrations:
    + persons.sub_persona
    + assessment_runs.horizon
    + assessment_runs.priority_mode
    + assessment_runs.priority_dimension
    + assessment_runs.priority_driver
    + assessment_runs.transformation_type
    + assessment_runs.transformation_secondary
```

Subsequent runs: `[ok] schema already up to date`.

The migration is implemented in `app/seed/migrate_v31.py` using
`inspect()` + raw `ALTER TABLE ... ADD COLUMN` (SQLite doesn't support
`ADD COLUMN IF NOT EXISTS`). Safe to re-run.

If you ever get into an unrecoverable schema-drift state on the dev
SQLite file, the nuclear option is:

```bash
rm instance/nichebrains.db
python manage.py seed
```

---

## Demo users (seeded by `python manage.py seed`)

| Role     | Email                          | Password   | What they see                       |
|----------|--------------------------------|------------|-------------------------------------|
| owner    | `owner@demo.nichebrains.ai`    | `demo1234` | Full SME journey, can sign Gate 1   |
| operator | `operator@demo.nichebrains.ai` | `demo1234` | SME journey w/o approval rights     |
| expert   | `expert@demo.nichebrains.ai`   | `demo1234` | Pipeline / profile / outcomes       |
| partner  | `partner@demo.nichebrains.ai`  | `demo1234` | Cohort + scheme registry            |
| admin    | `admin@demo.nichebrains.ai`    | `demo1234` | Tenant-local user permissions       |

---

## Scoring engine — invariants

Implemented in `app/services/scoring/engine.py`, validated by
`tests/unit/test_scoring.py`.

- **Banker's rounding** on every intermediate float-to-int step
- **Boundary snap**: 35→36, 65→66, 85→86 (the spec mandates these
  composites are *unreachable* so the band line is always crossed)
- **Bands**: Legacy <35 · Siloed 36–64 · Strategic 66–84 · Future-Ready 86–100
- **dTAS v2**: 5 dimensions × 8 questions × four weights;
  `dim_score = ROUND(SUM(weighted)/32 × 100, 0)`
- **Composite**: weighted blend of 5 dim scores (weights from `Dimension`
  table), then banker_round + boundary_snap

Auxiliary rules in `app/services/scoring/rules.py`:

- `apply_young_firm_floor` — firms <3 yr can't fall below band 2 on T (Tech)
- `resolve_skips` — skipped Q gets the median of answered questions in same dim
- `resolve_contradiction` — opposing-direction Qs trigger reconciliation prompt

---

## API conventions

- **Versioning**: every route is mounted under `/api/v1/`
- **Auth**: `POST /auth/login` returns a JWT; clients send
  `Authorization: Bearer <token>` on every subsequent request
- **Tenant scope**: enforced by `TenantScopedMixin.tenant_id` filter on
  every query; cross-tenant reads return 403
- **RBAC**:
  - Coarse: `@role_required('owner')` decorator on namespace methods
  - Fine: `@module_required('NRA')` checks `UserModulePermission`
- **Errors**: `{"error": "...", "code": "..."}` with appropriate HTTP status
- **Swagger**: every namespace has `@ns.doc(...)` + `@ns.response(...)`
  + request/response models for browsable docs at `/api/v1/docs/`

---

## CrewAI configuration

`app/agents/crews/nichebrains_crew.py` declares **two** `Agent` instances
(Narrator + Drafter) and a single `Crew` that runs them sequentially.

The CrewAI / OpenAI dependency tangle:

- `crewai 1.14.x` requires `openai>=2.0.0`
- We pin `openai>=2.0.0,<3.0.0` and `langchain-openai>=0.3.0,<0.4.0`
- The crew falls back to `crewai.LLM` (native) when available; otherwise
  uses `langchain-openai.ChatOpenAI`

Set `OPENAI_API_KEY` in `.env`. To use a different model:

```bash
# .env
OPENAI_MODEL=gpt-4o-mini
```

---

## Tests

```bash
pytest                                    # everything
pytest tests/unit/test_scoring.py         # determinism + boundary snap
pytest tests/unit/test_rankers.py         # initiative + expert rankers
pytest -k "transformation"                # name-match
```

The "Shree Vardhman Textiles" determinism check
(`TestDeterminism.test_same_input_same_output`) feeds the same payload
three times and asserts byte-identical composites.

---

## Switching to Postgres

SQLite is the dev default. To run against Postgres:

```bash
# .env
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/nichebrains
```

Then `python manage.py seed` (uses `db.create_all()`, no Alembic
migration needed for green-field DB). For incremental migrations on a
non-empty Postgres DB, use Flask-Migrate (`flask db migrate / upgrade`).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `no such column: persons.sub_persona` | DB created before v3.1 | `python manage.py migrate` then restart Flask |
| `TypeError: Can't replace canonical symbol for '__firstlineno__'` | Python 3.13 + old CrewAI wheels | Use Python 3.12 |
| `crewai requires openai>=2` | Stale `openai==1.x` pin | `pip install -U -r requirements.txt` |
| 401 on every endpoint | JWT expired or missing | Re-login via `POST /auth/login` |
| 403 on a read | Cross-tenant access attempt | Check the user's `tenant_id` matches the resource |
