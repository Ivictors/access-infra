#!/usr/bin/env python3
"""Check registration, event ingestion, and the authenticated web view."""

import http.cookiejar
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8080").rstrip("/")
WEB_URL = os.environ.get("WEB_URL", "http://127.0.0.1:8000").rstrip("/")
SIMULATOR_PATH = Path(os.environ.get(
    "SIMULATOR_PATH",
    str(Path(__file__).resolve().parents[2] / "simulator/device-simulator/main.py"),
))


def require_environment(name):
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Set {name} before running the integration check")
    return value


def wait_for_gateway():
    for _ in range(60):
        try:
            with urlopen(GATEWAY_URL + "/actuator/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("Gateway did not become healthy within 120 seconds")


def register_device(admin_token):
    serial = "IT-" + uuid.uuid4().hex[:16].upper()
    payload = json.dumps({"serialNumber": serial, "name": "Integration check"}).encode()
    request = Request(
        GATEWAY_URL + "/devices",
        data=payload,
        headers={
            "Authorization": "Bearer " + admin_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        if response.status != 201:
            raise RuntimeError(f"Device registration returned HTTP {response.status}")
        data = json.load(response)
    return serial, data["device"]["id"], data["apiKey"]


def run_simulator(admin_token, device_id, device_key):
    if not SIMULATOR_PATH.is_file():
        raise RuntimeError(f"Simulator not found: {SIMULATOR_PATH}")
    environment = os.environ.copy()
    environment.update({
        "ACCESS_GATEWAY_ADMIN_TOKEN": admin_token,
        "ACCESS_GATEWAY_DEVICE_ID": device_id,
        "ACCESS_GATEWAY_DEVICE_KEY": device_key,
    })
    subprocess.run(
        [sys.executable, str(SIMULATOR_PATH), "--scenario", "duplicate", "--base-url", GATEWAY_URL],
        env=environment,
        check=True,
        timeout=45,
    )


def check_web(serial, device_id, password):
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(WEB_URL + "/", timeout=10) as response:
        login_page = response.read().decode("utf-8")
    match = re.search(r'name="csrf_token" value="([0-9a-f]+)"', login_page)
    if match is None:
        raise RuntimeError("Login page did not provide a CSRF token")
    login = urlencode({
        "csrf_token": match.group(1),
        "action": "login",
        "password": password,
    }).encode()
    with opener.open(Request(WEB_URL + "/", data=login, method="POST"), timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Web login returned HTTP {response.status}")
    with opener.open(WEB_URL + "/?device_id=" + device_id, timeout=10) as response:
        page = response.read().decode("utf-8")
    if serial not in page or "ACCESS_GRANTED" not in page:
        raise RuntimeError("Web page did not show the registered device and event")


def main():
    admin_token = require_environment("ACCESS_GATEWAY_ADMIN_TOKEN")
    web_password = require_environment("ACCESS_WEB_TEST_PASSWORD")
    wait_for_gateway()
    serial, device_id, device_key = register_device(admin_token)
    run_simulator(admin_token, device_id, device_key)
    check_web(serial, device_id, web_password)
    print("PASS: registration, idempotent event ingestion, and authenticated web query")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
