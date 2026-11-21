import json
import os
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError


class StructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Choice(StructuredOutput):
    slug: str
    reason: str


class PlanChoices(StructuredOutput):
    choices: list[Choice]


class PracticeResult(StructuredOutput):
    slug: str
    performance: Literal["easy", "solved", "struggled", "unsolved", "unknown"]
    hints: int | None
    concepts: list[str]
    mistake: str | None
    takeaway: str | None


class FeedbackResults(StructuredOutput):
    results: list[PracticeResult]


class CoachUnavailable(Exception):
    pass


def configured():
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def generate(schema, instructions, context):
    if not configured():
        raise CoachUnavailable("Set OPENAI_API_KEY in the backend .env file to enable AI coaching.")
    try:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"].strip()},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "store": False,
                "instructions": instructions,
                "input": json.dumps(context),
                "text": {"format": {
                    "type": "json_schema", "name": schema.__name__,
                    "schema": schema.model_json_schema(), "strict": True,
                }},
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "completed":
            for item in payload.get("output", []):
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        return schema.model_validate_json(part["text"])
    except (httpx.HTTPError, ValueError, ValidationError, KeyError, TypeError) as error:
        raise CoachUnavailable("The AI coach is temporarily unavailable. Try again.") from error
    raise CoachUnavailable("The AI coach could not complete that request. Try again.")
