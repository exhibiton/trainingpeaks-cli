"""Authentication helpers for TrainingPeaks CLI."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from tp_cli.core.config import resolve_cookie_store
from tp_cli.core.constants import API_BASE


class AuthError(RuntimeError):
    """Raised when authentication fails."""


class TrainingPeaksAuth:
    """Authentication manager for cookie/token based auth."""

    def __init__(
        self,
        config: Dict[str, Any],
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookie_file: Optional[Path] = None,
    ) -> None:
        self.config = config
        self.username = username or os.getenv("TP_USERNAME")
        self.password = password or os.getenv("TP_PASSWORD")
        self.cookie_file = cookie_file or resolve_cookie_store(config)

    def _op_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        token_file = Path("~/.openclaw/op_service_token").expanduser()
        if "OP_SERVICE_ACCOUNT_TOKEN" not in env and token_file.exists():
            env["OP_SERVICE_ACCOUNT_TOKEN"] = token_file.read_text().strip()
        return env

    def _op_read(self, ref: str) -> str:
        result = subprocess.run(
            ["op", "read", ref],
            capture_output=True,
            text=True,
            env=self._op_env(),
            check=False,
        )
        if result.returncode != 0:
            raise AuthError(f"op read failed for {ref}: {result.stderr.strip()}")
        return result.stdout.strip()

    def _load_op_cookies(self) -> Optional[List[Dict[str, Any]]]:
        auth_cfg = self.config.get("auth", {})
        if not auth_cfg.get("use_1password", False):
            return None

        doc_name = str(auth_cfg.get("op_cookie_document") or "").strip()
        vault = str(auth_cfg.get("op_vault") or "").strip()
        if not doc_name or not vault:
            return None
        try:
            result = subprocess.run(
                ["op", "document", "get", doc_name, "--vault", vault],
                capture_output=True,
                text=True,
                env=self._op_env(),
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                cookies = json.loads(result.stdout)
                if isinstance(cookies, list):
                    return cookies
        except Exception:
            return None
        return None

    def _save_op_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        auth_cfg = self.config.get("auth", {})
        if not auth_cfg.get("use_1password", False):
            return

        doc_name = str(auth_cfg.get("op_cookie_document") or "").strip()
        vault = str(auth_cfg.get("op_vault") or "").strip()
        if not doc_name or not vault:
            return

        fd, temp_name = tempfile.mkstemp(prefix="tp-cli-cookies-", suffix=".json")
        tmp_path = Path(temp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(cookies, handle, indent=2)
                handle.write("\n")

            subprocess.run(
                ["op", "document", "edit", doc_name, "--vault", vault, str(tmp_path)],
                capture_output=True,
                text=True,
                env=self._op_env(),
                check=False,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _cookies_to_jar(cookies: List[Dict[str, Any]]) -> Dict[str, str]:
        jar: Dict[str, str] = {}
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            name = cookie.get("name") or cookie.get("Name")
            value = cookie.get("value") or cookie.get("Value")
            if name and value is not None:
                jar[str(name)] = str(value)
        return jar

    def _try_token(self, jar: Dict[str, str]) -> Optional[str]:
        try:
            response = requests.get(f"{API_BASE}/users/v3/token", cookies=jar, timeout=10)
            if response.status_code != 200:
                return None
            data = response.json()
            if data.get("success") and data.get("token", {}).get("access_token"):
                return str(data["token"]["access_token"])
        except Exception:
            return None
        return None

    def _load_local_cookies(self) -> Optional[List[Dict[str, Any]]]:
        if not self.cookie_file.exists():
            return None
        try:
            data = json.loads(self.cookie_file.read_text())
            return data if isinstance(data, list) else None
        except Exception:
            return None

    def _save_local_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_file.write_text(json.dumps(cookies, indent=2) + "\n")

    def _resolve_credentials(self) -> Tuple[str, str]:
        username = self.username
        password = self.password

        if username and password:
            return username, password

        auth_cfg = self.config.get("auth", {})
        username_ref = auth_cfg.get("op_username_ref")
        password_ref = auth_cfg.get("op_password_ref")

        if not username and username_ref:
            try:
                username = self._op_read(str(username_ref))
            except AuthError:
                username = None
        if not password and password_ref:
            try:
                password = self._op_read(str(password_ref))
            except AuthError:
                password = None

        if not username or not password:
            raise AuthError(
                "Missing credentials. Provide --username/--password or TP_USERNAME/TP_PASSWORD."
            )
        return username, password

    def login_playwright(self) -> List[Dict[str, Any]]:
        """Login using Playwright and return browser cookies."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise AuthError(
                "Playwright is not installed. Install it with "
                "`pip install trainingpeaks-cli[browser]`."
            ) from exc

        username, password = self._resolve_credentials()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(
                "https://home.trainingpeaks.com/login",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            time.sleep(2)

            page.fill("#Username", username)
            page.fill("#Password", password)
            with page.expect_navigation(timeout=20000):
                page.press("#Password", "Enter")
            time.sleep(3)

            cookies = context.cookies()
            browser.close()

        if not cookies:
            raise AuthError("Playwright login did not yield cookies")

        self._save_local_cookies(cookies)
        return cookies

    def login(self, force: bool = False) -> Tuple[str, Dict[str, str]]:
        """Authenticate and return bearer token + cookie jar."""
        if not force:
            op_cookies = self._load_op_cookies()
            if op_cookies:
                jar = self._cookies_to_jar(op_cookies)
                token = self._try_token(jar)
                if token:
                    self._save_local_cookies(op_cookies)
                    return token, jar

            cached = self._load_local_cookies()
            if cached:
                jar = self._cookies_to_jar(cached)
                token = self._try_token(jar)
                if token:
                    return token, jar

        fresh_cookies = self.login_playwright()
        jar = self._cookies_to_jar(fresh_cookies)
        token = self._try_token(jar)
        if not token:
            raise AuthError("Login succeeded but failed to exchange cookies for a bearer token")

        self._save_op_cookies(fresh_cookies)
        return token, jar

    def logout(self) -> bool:
        """Delete local cached cookie file."""
        if self.cookie_file.exists():
            self.cookie_file.unlink()
            return True
        return False

    def get_user_info(self, token: str) -> Dict[str, Any]:
        """Return authenticated user profile."""
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_BASE}/users/v3/user", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
