"""Check staging health/readiness and notify a configured JSON webhook on failure."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def normalized_base_url(value: str) -> str:
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        (parsed.scheme != "https" and not (local and parsed.scheme == "http"))
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise ValueError("Base URL must be an HTTPS origin (HTTP is allowed only on localhost).")
    if parsed.path not in {"", "/"}:
        raise ValueError("Base URL must not include a path.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def post_alert(webhook_url: str, message: str) -> bool:
    webhook = urlsplit(webhook_url)
    if webhook.scheme != "https" or not webhook.netloc:
        print("Uptime alert webhook must use HTTPS.", file=sys.stderr)
        return False
    request = Request(
        webhook_url,
        data=json.dumps({"text": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Staging API origin")
    parser.add_argument(
        "--simulate-failure",
        action="store_true",
        help="Send a test alert without making health requests.",
    )
    args = parser.parse_args()
    try:
        base_url = normalized_base_url(args.base_url)
    except ValueError as error:
        parser.error(str(error))

    failures: list[str] = []
    if args.simulate_failure:
        failures.append("Simulated uptime alert test")
    else:
        opener = build_opener(NoRedirect)
        for path in ("/health", "/ready"):
            try:
                with opener.open(f"{base_url}{path}", timeout=10) as response:
                    if response.status != 200:
                        failures.append(f"{path} returned a non-success status")
            except (HTTPError, URLError, TimeoutError, OSError):
                failures.append(f"{path} did not return HTTP 200")

    if not failures:
        print("Staging health and readiness checks passed.")
        return 0

    webhook_url = os.environ.get("UPTIME_ALERT_WEBHOOK", "")
    if not webhook_url:
        print("Health check failed; UPTIME_ALERT_WEBHOOK is not configured.", file=sys.stderr)
        return 1
    message = "POUKTRY staging alert: " + "; ".join(failures)
    if not post_alert(webhook_url, message):
        print(
            "Health check failed and the uptime alert webhook did not acknowledge delivery.",
            file=sys.stderr,
        )
        return 1
    print("Uptime alert webhook acknowledged the notification.")
    return 0 if args.simulate_failure else 1


if __name__ == "__main__":
    raise SystemExit(main())
