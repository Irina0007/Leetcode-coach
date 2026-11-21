import re

import httpx

ENDPOINT = "https://leetcode.com/graphql/"
STATS_QUERY = """query Profile($username: String!) {
  matchedUser(username: $username) {
    username
    submitStatsGlobal { acSubmissionNum { difficulty count } }
  }
}"""
RECENT_QUERY = """query Recent($username: String!) {
  recentAcSubmissionList(username: $username, limit: 20) { title titleSlug timestamp }
}"""


class ProfileNotFound(Exception):
    pass


def query(client, document, username):
    try:
        response = client.post(ENDPOINT, json={
            "query": document, "variables": {"username": username},
        })
        response.raise_for_status()
        payload = response.json()
        return payload.get("data") or {}
    except (httpx.HTTPError, ValueError, AttributeError):
        return {}


def get_profile(username):
    with httpx.Client(timeout=8) as client:
        stats = query(client, STATS_QUERY, username)
        recent = query(client, RECENT_QUERY, username).get("recentAcSubmissionList")

    user = stats.get("matchedUser")
    if "matchedUser" in stats and user is None and not recent:
        raise ProfileNotFound
    stats = (user or {}).get("submitStatsGlobal") or {}
    counts = {
        item["difficulty"]: item["count"]
        for item in stats.get("acSubmissionNum") or []
        if isinstance(item.get("difficulty"), str) and isinstance(item.get("count"), int)
    }
    accepted = []
    for item in recent or []:
        try:
            if re.fullmatch(r"[a-z0-9-]+", item["titleSlug"]) and isinstance(item["title"], str):
                accepted.append((item["titleSlug"], item["title"], int(item["timestamp"])))
        except (KeyError, ValueError, TypeError):
            continue
    return counts, accepted, isinstance(recent, list)
