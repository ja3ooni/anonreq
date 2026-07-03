import json
import os
import sys

import requests

API_KEY = os.environ.get("ANONREQ_API_KEY", "test-key-0123456789abcdef")
API_URL = "http://localhost:8000/v1/chat/completions"

payload = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Tell me a short story"}],
    "stream": True,
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

resp = requests.post(API_URL, json=payload, headers=headers, stream=True)
if resp.status_code != 200:
    print(f"Error: HTTP {resp.status_code}")
    print(resp.text)
    sys.exit(1)

found_done = False
for line in resp.iter_lines():
    if line:
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            data_str = decoded[6:]
            if data_str == "[DONE]":
                found_done = True
                print("data: [DONE]")
            else:
                print(decoded)

if not found_done:
    print("FAIL: Missing [DONE] event")
    sys.exit(1)

print("\nPASS: Streaming completed")
