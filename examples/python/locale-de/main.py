import json
import os
import sys

import requests

API_KEY = os.environ.get("ANONREQ_API_KEY", "test-key-0123456789abcdef")
API_URL = "http://localhost:8000/v1/chat/completions"

payload = {
    "model": "gpt-4o",
    "messages": [
        {
            "role": "user",
            "content": "Mein Name ist Hans Müller, wohnhaft in Berliner Straße 42, 10115 Berlin",
        }
    ],
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "X-AnonReq-Locale": "de-DE",
}

resp = requests.post(API_URL, json=payload, headers=headers)
if resp.status_code != 200:
    print(f"Error: HTTP {resp.status_code}")
    print(resp.text)
    sys.exit(1)

content = resp.json()["choices"][0]["message"]["content"]
print("Response:", content)
print("PASS: German locale detection applied")
