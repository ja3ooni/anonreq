#!/usr/bin/env python3
"""Send claim text (or stdin) through AnonReq. Extract PDF to text before this."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: submit_claim.py <claim.txt|->", file=sys.stderr)
        return 2
    source = sys.argv[1]
    text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    url = os.environ.get("ANONREQ_URL", "http://localhost:8080").rstrip("/")
    api_key = os.environ.get("ANONREQ_API_KEY", "")
    body = json.dumps({
        "model": os.environ.get("ANONREQ_MODEL", "gpt-4o"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Du bist Versicherungssachbearbeitung. Tokens wie [KVNR_0] "
                    "sind maskiert. Keine Klarwerte verlangen."
                ),
            },
            {
                "role": "user",
                "content": "Bitte Deckungszusage skizzieren:\n\n" + text,
            },
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
        print(f"FAIL: HTTP {exc.code}\n{exc.read().decode('utf-8', errors='replace')}")
        return 1
    print(data["choices"][0]["message"]["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
