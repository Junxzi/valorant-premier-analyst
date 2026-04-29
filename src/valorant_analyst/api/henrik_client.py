"""Thin wrapper around the HenrikDev unofficial Valorant API."""

from __future__ import annotations

import contextlib
import time
from typing import Any

import requests

DEFAULT_BASE_URL = "https://api.henrikdev.xyz"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_RETRIES = 1
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 5.0


class HenrikAPIError(RuntimeError):
    """Raised when the HenrikDev API returns an error or invalid response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HenrikClient:
    """Minimal client for HenrikDev's Valorant endpoints."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        rate_limit_backoff: float = DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for HenrikClient.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._max_retries = max(0, max_retries)
        self._rate_limit_backoff = max(0.0, rate_limit_backoff)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._api_key,
            "Accept": "application/json",
            "User-Agent": "valorant-premier-analyst/0.1",
        }

    def _sleep_for_retry_after(self, response: requests.Response) -> None:
        retry_after = response.headers.get("Retry-After")
        delay = self._rate_limit_backoff
        if retry_after:
            with contextlib.suppress(ValueError):
                delay = max(delay, float(retry_after))
        time.sleep(delay)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        attempts = 0
        while True:
            attempts += 1
            try:
                response = self._session.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self._timeout,
                )
            except requests.Timeout as exc:
                raise HenrikAPIError(
                    f"Request to HenrikDev API timed out after {self._timeout}s: {url}"
                ) from exc
            except requests.RequestException as exc:
                raise HenrikAPIError(f"Failed to reach HenrikDev API: {exc}") from exc

            if response.status_code == 429 and attempts <= self._max_retries:
                self._sleep_for_retry_after(response)
                continue

            if not response.ok:
                snippet = (response.text or "")[:200]
                raise HenrikAPIError(
                    f"HenrikDev API returned HTTP {response.status_code} for {url}. "
                    f"Body: {snippet}",
                    status_code=response.status_code,
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise HenrikAPIError(
                    f"HenrikDev API returned non-JSON response for {url}."
                ) from exc

            if not isinstance(payload, dict):
                raise HenrikAPIError(
                    f"Unexpected JSON shape from HenrikDev API for {url}: "
                    f"expected object, got {type(payload).__name__}."
                )
            return payload

    def get_matches_by_player(
        self,
        region: str,
        name: str,
        tag: str,
        size: int = 10,
    ) -> dict[str, Any]:
        """Fetch the most recent matches for a Riot ID.

        Endpoint: GET /valorant/v3/matches/{region}/{name}/{tag}
        """
        if not region or not name or not tag:
            raise ValueError("region, name and tag are all required.")
        if size <= 0:
            raise ValueError("size must be a positive integer.")

        path = f"/valorant/v3/matches/{region}/{name}/{tag}"
        return self._get(path, params={"size": size})

    def get_stored_matches(
        self,
        region: str,
        name: str,
        tag: str,
        page: int = 1,
        size: int = 25,
        mode: str | None = None,
        map_name: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a *page* of historical matches (summary level).

        Endpoint: GET /valorant/v1/stored-matches/{region}/{name}/{tag}

        Useful for backfill: paginate through a player's full history to
        discover ``match_id`` values, then fetch each match in detail with
        :meth:`get_match_by_id`. ``mode`` (e.g. ``"premier"``) lets the server
        do the filtering when supported.
        """
        if not region or not name or not tag:
            raise ValueError("region, name and tag are all required.")
        if page <= 0:
            raise ValueError("page must be a positive integer.")
        if size <= 0:
            raise ValueError("size must be a positive integer.")

        params: dict[str, Any] = {"page": page, "size": size}
        if mode:
            params["mode"] = mode
        if map_name:
            params["map"] = map_name
        path = f"/valorant/v1/stored-matches/{region}/{name}/{tag}"
        return self._get(path, params=params)

    def get_premier_team(
        self,
        team_name: str,
        team_tag: str,
    ) -> dict[str, Any]:
        """Fetch Premier team details (members, stats, division).

        Endpoint: GET /valorant/v1/premier/{team_name}/{team_tag}
        """
        if not team_name or not team_tag:
            raise ValueError("team_name and team_tag are required.")
        path = f"/valorant/v1/premier/{team_name}/{team_tag}"
        return self._get(path)

    def get_premier_team_history(
        self,
        team_name: str,
        team_tag: str,
    ) -> dict[str, Any]:
        """Fetch a Premier team's official league match history.

        Endpoint: GET /valorant/v1/premier/{team_name}/{team_tag}/history

        The response contains ``data.league_matches[]`` with one entry per
        Premier league match: ``id`` (match UUID), ``points_before``,
        ``points_after`` and ``started_at``.
        """
        if not team_name or not team_tag:
            raise ValueError("team_name and team_tag are required.")
        path = f"/valorant/v1/premier/{team_name}/{team_tag}/history"
        return self._get(path)

    def get_match_by_id(self, match_id: str) -> dict[str, Any]:
        """Fetch the full detail for a single match.

        Endpoint: GET /valorant/v2/match/{matchid}

        The ``data`` field in the response is shaped exactly like one element
        of :meth:`get_matches_by_player`'s ``data`` array, so the existing
        normalizer can consume it directly.
        """
        if not match_id:
            raise ValueError("match_id is required.")
        path = f"/valorant/v2/match/{match_id}"
        return self._get(path)
