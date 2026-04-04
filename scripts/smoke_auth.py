#!/usr/bin/env python3
"""Smoke test registration and login flow for local Flask app."""

import re
import secrets
import time
from urllib.parse import urljoin

import requests

BASE_URL = "http://127.0.0.1:5055/"


def csrf_from(html: str) -> str | None:
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None


def main() -> int:
    session = requests.Session()

    reg_page = session.get(urljoin(BASE_URL, "register"), timeout=10)
    if reg_page.status_code != 200:
        print("REGISTER_PAGE_FAIL", reg_page.status_code)
        return 1

    reg_csrf = csrf_from(reg_page.text)
    if not reg_csrf:
        print("REGISTER_CSRF_MISSING")
        return 1

    suffix = f"{int(time.time())}_{secrets.token_hex(2)}"
    username = f"demo_{suffix}"
    email = f"{username}@example.com"
    password = "DemoPass123!"

    reg_payload = {
        "csrf_token": reg_csrf,
        "username": username,
        "email": email,
        "password": password,
        "confirm": password,
        "submit": "Register",
    }

    reg_submit = session.post(
        urljoin(BASE_URL, "register"),
        data=reg_payload,
        allow_redirects=True,
        timeout=10,
    )

    print("REGISTER_STATUS", reg_submit.status_code)
    print("REGISTER_FINAL_URL", reg_submit.url)

    login_page = session.get(urljoin(BASE_URL, "login"), timeout=10)
    if login_page.status_code != 200:
        print("LOGIN_PAGE_FAIL", login_page.status_code)
        return 1

    login_csrf = csrf_from(login_page.text)
    if not login_csrf:
        print("LOGIN_CSRF_MISSING")
        return 1

    login_payload = {
        "csrf_token": login_csrf,
        "email": email,
        "password": password,
        "submit": "Login",
    }

    login_submit = session.post(
        urljoin(BASE_URL, "login"),
        data=login_payload,
        allow_redirects=True,
        timeout=10,
    )

    print("LOGIN_STATUS", login_submit.status_code)
    print("LOGIN_FINAL_URL", login_submit.url)

    ok = ("/index" in login_submit.url) or ("/dashboard" in login_submit.url)
    print("LOGIN_SUCCESS", ok)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
