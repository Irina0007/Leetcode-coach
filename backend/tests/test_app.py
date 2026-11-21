from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_plan_survives_restart(tmp_path):
    path = tmp_path / "test.sqlite3"
    with TestClient(create_app(path)) as client:
        response = client.post("/api/plans", json={"minutes": 30})
        assert response.status_code == 200
        plan = response.json()
        assert sum(item["minutes"] for item in plan["items"]) <= 30
        assert client.post("/api/plans", json={"minutes": 1}).status_code == 422
    with TestClient(create_app(path)) as client:
        assert client.get("/api/dashboard").json()["plan"] == plan


def test_profile_partial_sync_preserves_counts_and_deduplicates(tmp_path, monkeypatch):
    from backend.app import leetcode
    from backend.app.db import database

    path = tmp_path / "profile.sqlite3"
    responses = iter([
        ({"All": 12}, [("two-sum", "Two Sum", 10)], True),
        ({}, [("two-sum", "Two Sum", 20)], True),
        ({}, [], False),
    ])
    monkeypatch.setattr(leetcode, "get_profile", lambda _: next(responses))
    with TestClient(create_app(path)) as client:
        assert client.post("/api/profile", json={"username": "Learner"}).status_code == 200
        partial = client.post("/api/profile", json={"username": "learner"}).json()
        assert partial["counts"] == {"All": 12}
        assert not partial["counts_available"]
        assert client.post("/api/profile", json={"username": "learner"}).status_code == 502
        assert client.get("/api/dashboard").json()["profile"] == partial
    with database(path) as connection:
        assert [tuple(row) for row in connection.execute("SELECT slug, accepted_at FROM accepted")] == [
            ("two-sum", 20),
        ]


def test_feedback_updates_notes_and_fits_due_review_in_plan(tmp_path, monkeypatch):
    from backend.app import ai

    def generate(schema, instructions, context):
        assert schema is ai.FeedbackResults
        return schema(results=[
            ai.PracticeResult(
                slug="group-anagrams", performance="struggled", hints=2,
                concepts=["hashing", " Hashing "], mistake="Used an unordered key.",
                takeaway="Sort each word before grouping.",
            )
        ])

    monkeypatch.setattr(ai, "generate", generate)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app(tmp_path / "feedback.sqlite3")) as client:
        assert client.post("/api/sessions", json={
            "day": "2026-11-20", "feedback": "I needed two hints for Group Anagrams.",
        }).status_code == 200
        dashboard = client.get("/api/dashboard?day=2026-11-21").json()
        assert dashboard["reviews"][0]["due"] == "2026-11-21"
        assert dashboard["weak_concepts"] == [{"name": "hashing", "count": 1}]
        assert dashboard["progress"]["due"] == 1
        plan = client.post("/api/plans", json={"minutes": 45, "day": "2026-11-21"}).json()
        assert plan["items"][0]["slug"] == "group-anagrams"
        assert {item["kind"] for item in plan["items"]} == {"New", "Review"}
        assert sum(item["minutes"] for item in plan["items"]) <= 45
        assert client.get("/api/dashboard?day=2026-11-22").json()["plan"] is None


def test_ai_plan_rejects_unknown_slugs_and_over_budget(monkeypatch):
    from backend.app import ai, coach

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    options = coach.candidates("2026-11-20", 30, set(), {}, [])
    assert len(coach.CURRICULUM) == 150

    def answer(slugs):
        return ai.PlanChoices(choices=[ai.Choice(slug=slug, reason="Practice") for slug in slugs])

    monkeypatch.setattr(ai, "generate", lambda *_: answer(["invented-question"]))
    assert coach.choose_plan(options, 30, [])[1] == "rules"
    monkeypatch.setattr(ai, "generate", lambda *_: answer([item["slug"] for item in options[:3]]))
    assert coach.choose_plan(options, 30, [])[1] == "rules"
    monkeypatch.setattr(ai, "generate", lambda *_: answer([options[0]["slug"]]))
    assert coach.choose_plan(options, 30, [])[1] == "ai"


def test_review_interval_increases_with_independent_success():
    from datetime import date

    from backend.app.coach import review_schedule

    day = date(2026, 11, 20)
    assert review_schedule(day, "Hard", "solved", 0, 0) == (date(2026, 11, 22), 1, 1)
    assert review_schedule(day, "Easy", "solved", 0, 1) == (date(2026, 11, 28), 2, 1)
    assert review_schedule(day, "Easy", "unsolved", None, 3) == (date(2026, 11, 21), 0, 4)
