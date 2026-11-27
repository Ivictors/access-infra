#!/usr/bin/env python3
"""Exercise Keycloak login, gateway JWT authorization, and device credentials."""

import html.parser
import http.cookiejar
import base64
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener, urlopen


WEB = "http://localhost:8000"
GATEWAY = "http://127.0.0.1:8080"
KEYCLOAK = "http://localhost:8180/realms/access-lab"
REDIRECT = WEB + "/?oidc_callback=1"


class LoginForm(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}
        self.in_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "kc-form-login":
            self.action = attrs.get("action")
            self.in_form = True
        elif tag == "input" and self.in_form and attrs.get("name"):
            self.fields[attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False


class CapturedCode(Exception):
    def __init__(self, url):
        self.url = url


class CaptureCallback(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        if url.startswith(REDIRECT):
            raise CapturedCode(url)
        return super().redirect_request(request, response, code, message, headers, url)


def request_json(url, token, method="GET", payload=None, expected=200):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": "Bearer " + token}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            status, content = response.status, response.read()
    except HTTPError as error:
        status, content = error.code, error.read()
        error.close()
    if status != expected:
        raise RuntimeError(f"{method} {url} returned {status}, expected {expected}: {content[:200]!r}")
    return json.loads(content) if content else None


def wait_for_stack():
    for _ in range(60):
        try:
            with urlopen(GATEWAY + "/actuator/health", timeout=3) as response:
                if response.status == 200:
                    with urlopen(WEB + "/", timeout=3) as web:
                        if web.status == 200:
                            return
        except (OSError, HTTPError):
            pass
        time.sleep(2)
    raise RuntimeError("Integrated stack did not become ready")


def login(username, password, cookies):
    opener = build_opener(HTTPCookieProcessor(cookies))
    with opener.open(WEB + "/?login=1", timeout=30) as response:
        page = response.read().decode("utf-8")
    form = LoginForm()
    form.feed(page)
    if not form.action:
        raise RuntimeError("Keycloak login form was not shown")
    # Browsers allow Secure cookies on localhost; Python's CookieJar does not.
    for cookie in cookies:
        if cookie.domain == "localhost.local":
            cookie.secure = False
    fields = form.fields | {"username": username, "password": password}
    try:
        with opener.open(Request(form.action, data=urlencode(fields).encode(), method="POST"), timeout=30) as response:
            page = response.read().decode("utf-8")
    except HTTPError as error:
        raise RuntimeError(f"Login returned {error.code} at {urlsplit(error.url).path}") from None
    if "UUID do dispositivo" not in page:
        raise RuntimeError("Web did not establish a session after Keycloak login")
    return opener


def user_access_token(client_secret, cookies):
    for cookie in cookies:
        if cookie.domain == "localhost.local":
            cookie.secure = False
    state = uuid.uuid4().hex
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    url = KEYCLOAK + "/protocol/openid-connect/auth?" + urlencode({
        "client_id": "access-web", "response_type": "code", "scope": "openid",
        "redirect_uri": REDIRECT, "state": state, "nonce": uuid.uuid4().hex,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    opener = build_opener(HTTPCookieProcessor(cookies), CaptureCallback())
    try:
        opener.open(url, timeout=30)
    except CapturedCode as callback:
        query = parse_qs(urlsplit(callback.url).query)
        if query.get("state") != [state] or not query.get("code"):
            raise RuntimeError("Invalid authorization response") from None
        code = query["code"][0]
    else:
        raise RuntimeError("Keycloak did not return an authorization code")
    body = urlencode({
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT, "client_id": "access-web", "client_secret": client_secret,
        "code_verifier": verifier,
    }).encode()
    with urlopen(Request(KEYCLOAK + "/protocol/openid-connect/token", data=body), timeout=30) as response:
        tokens = json.load(response)
    return tokens["access_token"], tokens["id_token"]


def main():
    password = os.environ.get("ACCESS_LAB_USER_PASSWORD", "")
    secret = os.environ.get("ACCESS_WEB_OIDC_CLIENT_SECRET", "")
    if not password or not secret:
        raise RuntimeError("Set ACCESS_LAB_USER_PASSWORD and ACCESS_WEB_OIDC_CLIENT_SECRET")
    wait_for_stack()
    cookies = http.cookiejar.CookieJar()
    web = login("access-admin", password, cookies)
    admin_token, id_token = user_access_token(secret, cookies)
    request_json(GATEWAY + "/devices/" + str(uuid.uuid4()), "invalid-token", expected=401)
    token_parts = admin_token.split(".")
    signature = token_parts[2]
    token_parts[2] = ("A" if signature[0] != "A" else "B") + signature[1:]
    request_json(GATEWAY + "/devices/" + str(uuid.uuid4()), ".".join(token_parts), expected=401)
    request_json(GATEWAY + "/devices/" + str(uuid.uuid4()), id_token, expected=401)
    serial = "OIDC-" + uuid.uuid4().hex[:16].upper()
    registration = request_json(GATEWAY + "/devices", admin_token, "POST",
                                {"serialNumber": serial, "name": "OIDC integration"}, 201)
    device_id, device_key = registration["device"]["id"], registration["apiKey"]
    reference = "OIDC-REF-" + uuid.uuid4().hex.upper()
    request_json(GATEWAY + "/credential-refs", admin_token, "POST", {"credentialRef": reference}, 201)
    request_json(GATEWAY + f"/devices/{device_id}/credential-refs", admin_token,
                 "POST", {"credentialRef": reference}, 204)
    event = {"deviceId": device_id, "externalEventId": "OIDC-EVT-" + uuid.uuid4().hex.upper(),
             "eventType": "ACCESS_GRANTED", "credentialRef": reference,
             "occurredAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    request_json(GATEWAY + "/device-events", device_key, "POST", event, 201)
    with web.open(WEB + "/?device_id=" + device_id, timeout=20) as response:
        page = response.read().decode("utf-8")
    if serial not in page or event["externalEventId"] not in page:
        raise RuntimeError("Authenticated web did not display the device event")
    with web.open(WEB + "/", timeout=20) as response:
        home = response.read().decode("utf-8")
    csrf = re.search(r'name="csrf_token" value="([a-f0-9]+)"', home)
    if not csrf:
        raise RuntimeError("Web did not render logout CSRF token")
    logout = Request(WEB + "/", data=urlencode({"action": "logout", "csrf_token": csrf.group(1)}).encode(), method="POST")
    with web.open(logout, timeout=30) as response:
        if response.url != WEB + "/" or "Entrar com Keycloak" not in response.read().decode("utf-8"):
            raise RuntimeError("Logout did not return to the unauthenticated web page")
    with web.open(WEB + "/?login=1", timeout=30) as response:
        form = LoginForm()
        form.feed(response.read().decode("utf-8"))
    if not form.action:
        raise RuntimeError("Keycloak SSO session remained active after logout")
    print("PASS: Keycloak login, JWT audience checks, admin access, device key, web event display, and SSO logout")


if __name__ == "__main__":
    main()
