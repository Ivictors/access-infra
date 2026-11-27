#!/usr/bin/env python3
"""Check registration, event ingestion, and the authenticated web view."""

import argparse
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
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


def gateway_request(path, token, method="GET", payload=None, expected=200):
    headers = {"Authorization": "Bearer " + token}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    request = Request(GATEWAY_URL + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            status, content = response.status, response.read()
    except HTTPError as error:
        status, content = error.code, error.read()
        error.close()
    if status != expected:
        raise RuntimeError(f"{method} {path} returned HTTP {status}, expected {expected}")
    return json.loads(content) if content else None


def register_credential(admin_token, device_id):
    credential_ref = "SIM-" + uuid.uuid4().hex.upper()
    payload = {"credentialRef": credential_ref}
    gateway_request("/credential-refs", admin_token, "POST", payload, 201)
    gateway_request(f"/devices/{device_id}/credential-refs", admin_token, "POST", payload, 204)
    return credential_ref


def check_negative_events(admin_token, device_id, device_key, credential_ref):
    occurred_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    unassigned_ref = "SIM-UNASSIGNED-" + uuid.uuid4().hex.upper()
    gateway_request("/credential-refs", admin_token, "POST", {"credentialRef": unassigned_ref}, 201)
    cases = (
        ("unassigned", device_key, unassigned_ref, True, 403),
        ("unknown-credential", device_key, "SIM-UNKNOWN-" + uuid.uuid4().hex.upper(), True, 403),
        ("invalid-key", "invalid-" + uuid.uuid4().hex, credential_ref, True, 401),
        ("invalid-payload", device_key, credential_ref, False, 400),
    )
    for label, token, reference, include_time, status in cases:
        external_id = "EVT-" + uuid.uuid4().hex.upper()
        event = {"deviceId": device_id, "externalEventId": external_id,
                 "eventType": "ACCESS_GRANTED", "credentialRef": reference}
        if include_time:
            event["occurredAt"] = occurred_at
        gateway_request("/device-events", token, "POST", event, status)
        history = gateway_request(f"/devices/{device_id}/events?limit=100", admin_token)
        if not isinstance(history, list) or any(item.get("externalEventId") == external_id for item in history):
            raise RuntimeError(f"{label} event was persisted or history was invalid")


def run_simulator(admin_token, device_id, device_key, credential_ref):
    if not SIMULATOR_PATH.is_file():
        raise RuntimeError(f"Simulator not found: {SIMULATOR_PATH}")
    environment = os.environ.copy()
    environment.update({
        "ACCESS_GATEWAY_ADMIN_TOKEN": admin_token,
        "ACCESS_GATEWAY_DEVICE_ID": device_id,
        "ACCESS_GATEWAY_DEVICE_KEY": device_key,
        "ACCESS_GATEWAY_CREDENTIAL_REF": credential_ref,
    })
    subprocess.run(
        [sys.executable, str(SIMULATOR_PATH), "--scenario", "duplicate", "--base-url", GATEWAY_URL],
        env=environment,
        check=True,
        timeout=45,
    )


def check_revocation(admin_token, device_id, device_key, credential_ref):
    occurred_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    event = {"deviceId": device_id, "externalEventId": "EVT-" + uuid.uuid4().hex.upper(),
             "eventType": "ACCESS_GRANTED", "credentialRef": credential_ref, "occurredAt": occurred_at}
    original = gateway_request("/device-events", device_key, "POST", event, 201)
    gateway_request(f"/devices/{device_id}/credential-refs", admin_token, "DELETE",
                    {"credentialRef": credential_ref}, 204)
    replay = gateway_request("/device-events", device_key, "POST", event, 200)
    if replay.get("id") != original.get("id"):
        raise RuntimeError("Replay after revocation did not preserve the original event")
    event["externalEventId"] = "EVT-" + uuid.uuid4().hex.upper()
    gateway_request("/device-events", device_key, "POST", event, 403)
    history = gateway_request(f"/devices/{device_id}/events?limit=100", admin_token)
    if not isinstance(history, list) or any(item.get("externalEventId") == event["externalEventId"] for item in history):
        raise RuntimeError("Event after credential revocation was persisted or history was invalid")


def check_web(serial, device_id, password):
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(WEB_URL + "/", timeout=10) as response:
        login_page = response.read().decode("utf-8")
    match = re.search(r'name="csrf_token" value="([0-9a-f]+)"', login_page)
    if match is None:
        raise RuntimeError("Login page did not provide a CSRF token")
    invalid_csrf = urlencode({"csrf_token": "invalid", "action": "login", "password": password}).encode()
    try:
        opener.open(Request(WEB_URL + "/", data=invalid_csrf, method="POST"), timeout=10)
    except HTTPError as error:
        status = error.code
        error.close()
        if status != 400:
            raise RuntimeError(f"Invalid login CSRF returned HTTP {status}, expected 400")
    else:
        raise RuntimeError("Login accepted an invalid CSRF token")
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
    logout_token = re.search(r'name="csrf_token" value="([0-9a-f]+)"', page)
    if logout_token is None:
        raise RuntimeError("Authenticated page did not provide a CSRF token")
    bad_logout = urlencode({"csrf_token": "invalid", "action": "logout"}).encode()
    try:
        opener.open(Request(WEB_URL + "/", data=bad_logout, method="POST"), timeout=10)
    except HTTPError as error:
        status = error.code
        error.close()
        if status != 400:
            raise RuntimeError(f"Invalid logout CSRF returned HTTP {status}, expected 400")
    else:
        raise RuntimeError("Logout accepted an invalid CSRF token")
    logout = urlencode({"csrf_token": logout_token.group(1), "action": "logout"}).encode()
    with opener.open(Request(WEB_URL + "/", data=logout, method="POST"), timeout=10) as response:
        logged_out_page = response.read().decode("utf-8")
    if 'name="password"' not in logged_out_page:
        raise RuntimeError("Logout did not return to the login page")
    with opener.open(WEB_URL + "/?device_id=" + device_id, timeout=10) as response:
        after_logout = response.read().decode("utf-8")
    if serial in after_logout or 'name="password"' not in after_logout:
        raise RuntimeError("Logged-out session still exposes device data")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", action="store_true",
                        help="check pinned images that predate credential reference assignment")
    args = parser.parse_args(argv)
    admin_token = require_environment("ACCESS_GATEWAY_ADMIN_TOKEN")
    web_password = require_environment("ACCESS_WEB_TEST_PASSWORD")
    wait_for_gateway()
    serial, device_id, device_key = register_device(admin_token)
    if args.legacy:
        credential_ref = "SIM-" + uuid.uuid4().hex.upper()
    else:
        credential_ref = register_credential(admin_token, device_id)
        check_negative_events(admin_token, device_id, device_key, credential_ref)
    run_simulator(admin_token, device_id, device_key, credential_ref)
    if not args.legacy:
        check_revocation(admin_token, device_id, device_key, credential_ref)
    check_web(serial, device_id, web_password)
    if args.legacy:
        print("PASS: legacy registration, duplicate ingestion, CSRF, web query, and logout")
    else:
        print("PASS: assignment, rejection, duplicate ingestion, revocation, CSRF, web query, and logout")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
