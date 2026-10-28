"""Container healthcheck: language=de must actually analyze text.

GET /health stays green on the stock English-only image. This probe posts a
fixed sentence and requires a PERSON span so a missing German model keeps
the container unhealthy. The sentence is a constant, not customer data.
"""

from __future__ import annotations

import json
import urllib.request

PROBE = "Hans Müller wohnt in Berlin."
PAYLOAD = json.dumps(
    {
        "text": PROBE,
        "language": "de",
        "score_threshold": 0.4,
    }
).encode()


def main() -> None:
    request = urllib.request.Request(
        "http://127.0.0.1:3000/analyze",
        data=PAYLOAD,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read().decode())
    if not isinstance(body, list) or not any(
        isinstance(item, dict) and item.get("entity_type") == "PERSON"
        for item in body
    ):
        raise SystemExit("language=de did not return PERSON; German model is not loaded")


if __name__ == "__main__":
    main()
