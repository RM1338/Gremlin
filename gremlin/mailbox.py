"""A throwaway inbox, so a run can clear an email+OTP login on its own.

mail.tm hands out a real, disposable mailbox over a plain REST API with no
account of our own to manage: Gremlin creates one, gives the address to the
login filler, and polls it for the verification code. stdlib HTTP only — no
new dependency, same as the model backends.

If mail.tm is unreachable the caller gets a MailboxError and the run falls
back to ordinary exploration (it just never gets past the login wall).
"""
from __future__ import annotations

import json
import re
import secrets
import time
import urllib.error
import urllib.request

_BASE = "https://api.mail.tm"
# OTP codes are almost always 6 digits; fall back to any 4-8 run before giving up.
_CODE_RES = (re.compile(r"\b(\d{6})\b"), re.compile(r"\b(\d{4,8})\b"))


class MailboxError(RuntimeError):
    pass


def _extract_code(text: str) -> str | None:
    for rx in _CODE_RES:
        m = rx.search(text or "")
        if m:
            return m.group(1)
    return None


def _members(resp) -> list:
    """A list endpoint returns a bare array with `Accept: application/json` and a
    `{"hydra:member": [...]}` envelope with ld+json. Accept either."""
    if isinstance(resp, list):
        return resp
    return resp.get("hydra:member", []) if isinstance(resp, dict) else []


def _api(method: str, path: str, token: str | None = None,
         body: dict | None = None, timeout: float = 15.0):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(_BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body_txt = e.read()[:200].decode(errors="replace")
        raise MailboxError(f"mail.tm {method} {path} -> HTTP {e.code}: {body_txt}") from e
    except urllib.error.URLError as e:
        raise MailboxError(f"mail.tm unreachable: {e.reason}") from e
    return json.loads(raw) if raw else {}


class Mailbox:
    """A freshly provisioned disposable inbox. `.address` is the email to type."""

    def __init__(self) -> None:
        domains = _members(_api("GET", "/domains?page=1"))
        usable = [d["domain"] for d in domains if d.get("isActive", True)]
        if not usable:
            raise MailboxError("mail.tm offered no usable domain")
        self.address = f"gremlin{secrets.token_hex(6)}@{usable[0]}"
        password = secrets.token_hex(12)
        _api("POST", "/accounts", body={"address": self.address, "password": password})
        self._token = _api("POST", "/token",
                           body={"address": self.address, "password": password})["token"]
        self._seen: set[str] = set()

    def wait_for_code(self, timeout: float = 90.0, poll: float = 4.0) -> str | None:
        """Poll until a not-yet-seen message yields a numeric code, or give up.

        Each message is inspected once; a mailbox instance never returns a code
        from the same message twice, so a second OTP screen waits for a second
        email rather than replaying the first.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            msgs = _members(_api("GET", "/messages?page=1", token=self._token))
            for msg in msgs:
                mid = msg.get("id")
                if not mid or mid in self._seen:
                    continue
                self._seen.add(mid)
                full = _api("GET", f"/messages/{mid}", token=self._token)
                blob = " ".join(str(full.get(k, "")) for k in ("subject", "intro", "text"))
                code = _extract_code(blob)
                if code:
                    return code
            time.sleep(poll)
        return None


if __name__ == "__main__":
    assert _extract_code("Your code is 481920. It expires soon.") == "481920"
    assert _extract_code("code: 4821") == "4821"
    assert _extract_code("no digits here") is None
    assert _extract_code("order 12 shipped, PIN 903117") == "903117"  # prefers the 6-run
    print("extract ok")
    mb = Mailbox()
    print("address:", mb.address)
    print("code:", mb.wait_for_code(timeout=20))
