"""Tests for HenrikClient backfill-related endpoints."""

from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from valorant_analyst.api.henrik_client import HenrikAPIError, HenrikClient


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        body: Any,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body) if not isinstance(body, str) else body
        self.headers = headers or {}

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self) -> Any:
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, url: str, headers=None, params=None, timeout=None) -> _FakeResponse:
        self.calls.append((url, params))
        if not self._responses:
            raise AssertionError(f"unexpected extra GET to {url}")
        return self._responses.pop(0)


def _client(session: _FakeSession, **kwargs: Any) -> HenrikClient:
    return HenrikClient(api_key="test-key", session=session, **kwargs)


def test_get_stored_matches_passes_query_params() -> None:
    session = _FakeSession(
        [_FakeResponse(200, {"status": 200, "data": [], "results": {"total": 0}})]
    )
    client = _client(session)
    client.get_stored_matches("ap", "Name", "JP1", page=2, size=10, mode="premier")

    url, params = session.calls[0]
    assert url.endswith("/valorant/v1/stored-matches/ap/Name/JP1")
    assert params == {"page": 2, "size": 10, "mode": "premier"}


def test_get_premier_team_endpoint() -> None:
    session = _FakeSession([_FakeResponse(200, {"status": 1, "data": {"id": "x"}})])
    client = _client(session)
    payload = client.get_premier_team("MyTeam", "MTM")
    assert payload["data"]["id"] == "x"
    assert session.calls[0][0].endswith("/valorant/v1/premier/MyTeam/MTM")


def test_get_premier_team_history_endpoint() -> None:
    session = _FakeSession(
        [_FakeResponse(200, {"data": {"league_matches": []}})]
    )
    client = _client(session)
    client.get_premier_team_history("MyTeam", "MTM")
    assert session.calls[0][0].endswith("/valorant/v1/premier/MyTeam/MTM/history")


def test_get_premier_team_validates_args() -> None:
    client = _client(_FakeSession([]))
    with pytest.raises(ValueError):
        client.get_premier_team("", "tag")
    with pytest.raises(ValueError):
        client.get_premier_team_history("name", "")


def test_get_match_by_id_hits_v2_endpoint() -> None:
    session = _FakeSession([_FakeResponse(200, {"status": 200, "data": {"x": 1}})])
    client = _client(session)
    payload = client.get_match_by_id("abc-123")
    assert payload == {"status": 200, "data": {"x": 1}}
    assert session.calls[0][0].endswith("/valorant/v2/match/abc-123")


def test_429_triggers_retry_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    session = _FakeSession(
        [
            _FakeResponse(429, {"errors": [{"message": "rate limited"}]},
                          headers={"Retry-After": "3"}),
            _FakeResponse(200, {"status": 200, "data": {"ok": True}}),
        ]
    )
    client = _client(session, max_retries=2, rate_limit_backoff=1.0)
    payload = client.get_match_by_id("m-1")

    assert payload["data"] == {"ok": True}
    assert len(session.calls) == 2
    assert sleeps and sleeps[0] >= 3.0


def test_429_exhausted_raises() -> None:
    session = _FakeSession(
        [
            _FakeResponse(429, {"err": "rl"}, headers={"Retry-After": "0"}),
            _FakeResponse(429, {"err": "rl"}, headers={"Retry-After": "0"}),
        ]
    )
    client = _client(session, max_retries=1, rate_limit_backoff=0.0)
    with pytest.raises(HenrikAPIError) as excinfo:
        client.get_match_by_id("m-1")
    assert excinfo.value.status_code == 429


def test_timeout_raises_friendly_error() -> None:
    class _TimeoutSession(_FakeSession):
        def get(self, *a, **kw):
            raise requests.Timeout("boom")

    client = _client(_TimeoutSession([]))
    with pytest.raises(HenrikAPIError) as excinfo:
        client.get_match_by_id("m-1")
    assert "timed out" in str(excinfo.value)


def test_get_stored_matches_validates_args() -> None:
    client = _client(_FakeSession([]))
    with pytest.raises(ValueError):
        client.get_stored_matches("", "n", "t")
    with pytest.raises(ValueError):
        client.get_stored_matches("ap", "n", "t", page=0)
    with pytest.raises(ValueError):
        client.get_stored_matches("ap", "n", "t", size=0)
