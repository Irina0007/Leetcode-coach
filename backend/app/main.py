import json
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated

from . import ai, coach, leetcode
from .db import SCHEMA, database, read_state, save_state


class ProfileRequest(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")


class PlanRequest(BaseModel):
    minutes: int = Field(ge=15, le=180)
    day: date = Field(default_factory=date.today)


class FeedbackRequest(BaseModel):
    feedback: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=4000)]
    day: date = Field(default_factory=date.today)


def study_history(connection):
    sessions = list(connection.execute("SELECT * FROM sessions ORDER BY id"))
    results = [item for session in sessions for item in json.loads(session["results"])]
    return sessions, results


def create_app(path=None):
    @asynccontextmanager
    async def lifespan(app):
        with database(path) as connection:
            connection.executescript(SCHEMA)
        yield

    app = FastAPI(title="Daily LeetCode Coach", lifespan=lifespan)

    @app.get("/api/dashboard")
    def dashboard(day: date | None = None):
        today = (day or date.today()).isoformat()
        with database(path) as connection:
            row = connection.execute(
                "SELECT payload FROM plans WHERE day = ? ORDER BY id DESC LIMIT 1", (today,)
            ).fetchone()
            profile = read_state(connection, "profile")
            sessions, results = study_history(connection)
            reviews = [dict(review) for review in connection.execute(
                "SELECT * FROM reviews ORDER BY due, priority DESC"
            )]
            plans = connection.execute("SELECT count(*) FROM plans").fetchone()[0]
            synced = connection.execute(
                "SELECT count(*) FROM accepted WHERE username = ?", (profile["username"] if profile else "",)
            ).fetchone()[0]
        notes = [item for item in results if item["mistake"] or item["takeaway"] or (
            item["performance"] in {"struggled", "unsolved"} or (item["hints"] or 0) > 0
        )]
        concepts = Counter(concept for item in notes for concept in item["concepts"])
        return {
            "plan": json.loads(row["payload"]) if row else None,
            "profile": profile,
            "ai_enabled": ai.configured(),
            "notes": list(reversed(notes)),
            "weak_concepts": [{"name": name, "count": count} for name, count in concepts.most_common()],
            "reviews": [{**review, "title": coach.CURRICULUM[review["slug"]]["title"]} for review in reviews],
            "progress": {
                "plans": plans, "sessions": len(sessions), "synced_problems": synced,
                "due": sum(review["due"] <= today for review in reviews),
            },
        }

    @app.post("/api/profile")
    def sync_profile(request: ProfileRequest):
        username = request.username.lower()
        try:
            counts, accepted, recent_available = leetcode.get_profile(username)
        except leetcode.ProfileNotFound as error:
            raise HTTPException(404, "LeetCode could not find that username.") from error
        if not counts and not recent_available:
            raise HTTPException(502, "LeetCode data is temporarily unavailable. Your saved data is still available.")
        if not counts and not accepted:
            with database(path) as connection:
                previous = read_state(connection, "profile")
            if not previous or previous["username"] != username:
                raise HTTPException(502, "Could not verify this profile from the available public data.")
        with database(path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = read_state(connection, "profile")
            same_user = previous and previous["username"] == username
            profile = {
                "username": username,
                "counts": counts or (previous["counts"] if same_user else {}),
                "counts_available": bool(counts),
                "recent_available": recent_available,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            connection.executemany("""
                INSERT INTO accepted VALUES (?, ?, ?, ?)
                ON CONFLICT(username, slug) DO UPDATE SET
                    title = excluded.title, accepted_at = max(accepted.accepted_at, excluded.accepted_at)
            """, [(username, *item) for item in accepted])
            save_state(connection, "profile", profile)
        return profile

    @app.post("/api/plans")
    def save_plan(request: PlanRequest):
        day = request.day.isoformat()
        with database(path) as connection:
            profile = read_state(connection, "profile")
            accepted = {row["slug"] for row in connection.execute(
                "SELECT slug FROM accepted WHERE username = ?", (profile["username"] if profile else "",)
            )}
            reviews = {row["slug"]: dict(row) for row in connection.execute("SELECT * FROM reviews")}
            _, results = study_history(connection)
        options = coach.candidates(day, request.minutes, accepted, reviews, results)
        items, source = coach.choose_plan(options, request.minutes, results)
        plan = {**request.model_dump(mode="json"), "items": items, "source": source}
        with database(path) as connection:
            connection.execute("INSERT INTO plans(day, payload) VALUES (?, ?)", (day, json.dumps(plan)))
        return plan

    @app.post("/api/sessions")
    def log_session(request: FeedbackRequest):
        try:
            results = coach.analyze_feedback(request.feedback)
        except ai.CoachUnavailable as error:
            raise HTTPException(503, str(error)) from error
        if not results:
            raise HTTPException(422, "Mention a NeetCode 150 problem you practiced so the coach can match it.")
        day = request.day.isoformat()
        with database(path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for item in results:
                slug = item["slug"]
                problem = coach.CURRICULUM[slug]
                item.update(title=problem["title"], topic=problem["topic"], day=day)
                previous = connection.execute("SELECT * FROM reviews WHERE slug = ?", (slug,)).fetchone()
                if previous and day < previous["last_practice"]:
                    continue
                streak = previous["streak"] if previous else 0
                if previous and day == previous["last_practice"]:
                    streak = max(0, streak - 1)
                due, streak, priority = coach.review_schedule(
                    request.day, problem["difficulty"], item["performance"], item["hints"], streak,
                )
                connection.execute(
                    "INSERT OR REPLACE INTO reviews VALUES (?, ?, ?, ?, ?)",
                    (slug, due.isoformat(), streak, priority, day),
                )
            connection.execute(
                "INSERT INTO sessions(day, feedback, results) VALUES (?, ?, ?)",
                (day, request.feedback, json.dumps(results)),
            )
        return {"results": results}

    return app


app = create_app()
