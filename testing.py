import os
import requests
from dotenv import load_dotenv

# Load variables from the .env file into the environment
load_dotenv()

# print(os.environ['ANONREQ_API_KEY'])
resp = requests.post(
    "http://127.0.0.1:8080/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {os.environ['ANONREQ_API_KEY']}",
        "Content-Type": "application/json",
        "X-AnonReq-Tenant-ID": os.environ.get("ANONREQ_TENANT_ID", "default"),
    },
    json={
        "model": "fast",
        "messages": [{"role": "user", "content": "My SSN is 123-45-6789"}],
    },
)

print(resp.json())