# AI Daily LeetCode Coach

An AI-powered LeetCode coach that syncs coding progress, generates personalized daily practice plans, analyzes mistakes, builds a knowledge base, and schedules adaptive reviews. The local, single-user MVP uses the NeetCode 150 curriculum.

## Run locally

Install Python 3.11–3.14 and Node.js 22.12+ or 24+. Run these commands from the repository root.

**Terminal 1 · FastAPI**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
python -m uvicorn backend.app.main:app --reload
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. Use a Python version from the range above when creating the environment.

**Terminal 2 · React**

```bash
cd frontend
npm ci
npm run dev
```

Open the [dashboard](http://127.0.0.1:5173/) or [FastAPI’s interactive API docs](http://127.0.0.1:8000/docs).

To enable AI, set `OPENAI_API_KEY` in the root `.env` and restart FastAPI. `OPENAI_MODEL` defaults to `gpt-4o-mini` and can be set to another model that supports Structured Outputs. The key stays on the backend. Without a key, the planner uses local rules and feedback analysis is disabled. When OpenAI is temporarily unavailable, the planner falls back to rules and the feedback form keeps your draft for retry.

## Try each feature

| Feature | Local check |
| --- | --- |
| LeetCode profile | Enter your public LeetCode username. Check the solved counts and the synced problem count in Study progress. Refresh and confirm the profile stays connected. |
| Daily plan | Enter 30, 45, or 60 minutes and generate a plan. Verify that each item has a LeetCode link, time estimate, and reason. Reload to see the same saved plan for today. |
| Mistake notes | With AI enabled, submit “I solved Two Sum easily, but needed two hints for Group Anagrams because I couldn’t pick a hashing key.” Look for the Group Anagrams note and a weak-concept tag. |
| Review schedule | After that session, check that Group Anagrams is scheduled for tomorrow. For a same-day simulation without changing your clock, use the API docs to generate a plan with tomorrow’s date. |
| Progress | Check the session count, synced problems, and upcoming reviews. Restart the backend to confirm the data persists. |

## How the pieces fit

| Component | Responsibility |
| --- | --- |
| `frontend/src/main.tsx` | React forms and dashboard. Vite forwards `/api` to FastAPI during local development. |
| `backend/app/main.py` | Validates REST requests and coordinates database reads and writes. |
| `backend/app/leetcode.py` | Requests public solved counts and recent accepted submissions from LeetCode GraphQL. |
| `backend/app/coach.py` | Ranks curriculum candidates, validates plan choices, analyzes feedback, and calculates review dates. |
| `backend/app/ai.py` | Calls the OpenAI Responses API with Pydantic-generated JSON schemas. |
| `backend/app/db.py` | Creates SQLite tables for profiles, synced problems, plans, session results, and reviews. The database defaults to `coach.sqlite3` at the repository root. |

The planner excludes known solves from new practice, prioritizes overdue and difficult reviews, and uses session history to rank weak topics. FastAPI supplies canonical links and time estimates. It checks the AI’s selected problems against the catalog and time budget before saving. The fallback uses the same ranked candidates. The curriculum snapshot comes from the public [NeetCode practice list](https://neetcode.io/practice).

Feedback is sent to OpenAI for structured extraction. SQLite stores the original feedback and parsed results in the same transaction as the review updates. Unsolved attempts, struggled attempts, and attempts with two or more hints return the next day. One hint or unclear performance starts at two days. Successful independent attempts use a difficulty-based interval that grows with the success streak and caps at 30 days.

LeetCode GraphQL is a best-effort integration. Recent accepted submissions are a rolling sample of up to 20, so the app may recommend a problem you solved before your first sync. Partial syncs preserve available data from the previous sync for that username. The MVP stores one local coaching history and uses the connected profile as a source of public practice data. Changing the username updates that source. Run both services locally because the app has no multi-user authentication.

## Run the checks

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
```

Tests use temporary SQLite databases and mock AI or LeetCode responses where relevant. They cover persistence, partial sync and deduplication, budget and curriculum validation, feedback extraction, and review intervals.
