#!/usr/bin/env python3
"""Forward a Jira/Zendesk/generic ticket through AnonReq, not the model vendor."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def extract_ticket(payload: dict) -> tuple[str, str]:
    issue = payload.get("issue") or {}
    fields = issue.get("fields") or {}
    if issue.get("key") or fields:
        key = str(issue.get("key") or "JIRA")
        summary = str(fields.get("summary") or "")
        description = str(fields.get("description") or "")
        return key, f"{summary}\n\n{description}".strip()

    ticket = payload.get("ticket") or {}
    if ticket:
        key = str(ticket.get("id") or "ZENDESK")
        subject = str(ticket.get("subject") or "")
        description = str(ticket.get("description") or "")
        return key, f"{subject}\n\n{description}".strip()

    title = str(payload.get("title") or payload.get("summary") or "TICKET")
    body = str(payload.get("body") or payload.get("description") or "")
    return title, f"{title}\n\n{body}".strip()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: forward_ticket.py <ticket.json>", file=sys.stderr)
        return 2

    with open(sys.argv[1], encoding="utf-8") as fh:
        payload = json.load(fh)

    key, text = extract_ticket(payload)
    url = os.environ.get("ANONREQ_URL", "http://localhost:8080").rstrip("/")
    api_key = os.environ.get("ANONREQ_API_KEY", "")
    body = json.dumps({
        "model": os.environ.get("ANONREQ_MODEL", "gpt-4o"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Du bist First-Level-Support. Der Text kann Tokens wie "
                    "[TAX_ID_DE_0] enthalten; das sind maskierte Identifikatoren."
                ),
            },
            {"role": "user", "content": text},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-AnonReq-Locale": "de-DE",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"FAIL {key}: HTTP {exc.code}\n{exc.read().decode('utf-8', errors='replace')}")
        return 1

    answer = data["choices"][0]["message"]["content"]
    print(f"ticket={key}\n{answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
