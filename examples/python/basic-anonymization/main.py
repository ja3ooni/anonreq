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
            "content": "Contact me at jane@example.com or call +1-555-987-6543",
        }
    ],
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

resp = requests.post(API_URL, json=payload, headers=headers)
if resp.status_code != 200:
    print(f"Error: HTTP {resp.status_code}")
    print(resp.text)
    sys.exit(1)

data = resp.json()
content = data["choices"][0]["message"]["content"]
print("Response:", json.dumps(data, indent=2))

assert "[EMAIL_1]" in content, "Missing EMAIL token"
assert "[PHONE_1]" in content, "Missing PHONE token"
print("PASS: Tokens verified in response")
