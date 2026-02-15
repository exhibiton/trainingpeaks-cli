"""TrainingPeaks API client with retry and rate limiting."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from tp_cli.core.constants import API_BASE


class APIError(RuntimeError):
    """Raised for API failures after retries."""


class TrainingPeaksAPI:
    """Thin wrapper around TrainingPeaks REST API."""

    def __init__(
        self,
        token: str,
        base_url: str = API_BASE,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        timeout_seconds: int = 30,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self._has_sent_request = False

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self.rate_limit_delay > 0 and self._has_sent_request:
                    time.sleep(self.rate_limit_delay)

                self._has_sent_request = True
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    params=params,
                    json=json_data,
                    timeout=self.timeout_seconds,
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(response.text, response=response)
                response.raise_for_status()

                if not response.text:
                    return {}
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(min(2**attempt, 8))

        raise APIError(f"API request failed for {method} {path}: {last_error}")

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._request("POST", path, json_data=payload)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def get_user(self) -> Dict[str, Any]:
        return self.get("/users/v3/user")

    def get_user_id(self) -> str:
        user_data = self.get_user()
        return str(user_data["user"]["userId"])

    def get_workouts(self, user_id: str, start_date: str, end_date: str) -> Any:
        return self.get(f"/fitness/v6/athletes/{user_id}/workouts/{start_date}/{end_date}")

    def get_workout(self, user_id: str, workout_id: str) -> Any:
        return self.get(f"/fitness/v1/athletes/{user_id}/workouts/{workout_id}")

    def create_workout(self, user_id: str, payload: Dict[str, Any]) -> Any:
        return self.post(f"/fitness/v6/athletes/{user_id}/workouts", payload)

    def delete_workout(self, user_id: str, workout_id: str) -> Any:
        return self.delete(f"/fitness/v6/athletes/{user_id}/workouts/{workout_id}")

    def get_athlete_settings(self, user_id: str) -> Any:
        return self.get(f"/fitness/v1/athletes/{user_id}/settings")
