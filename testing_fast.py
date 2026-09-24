import time, http.client, json, os
from dotenv import load_dotenv

t0 = time.monotonic()
load_dotenv()
t1 = time.monotonic()

conn = http.client.HTTPConnection("127.0.0.1", 8080, timeout=10)
conn.request(
    "POST",
    "/v1/chat/completions",
    body=json.dumps({
        "model": "fast",
        "messages": [{"role": "user", "content": "My SSN is 123-45-6789"}],
    }),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['ANONREQ_API_KEY']}",
        "X-AnonReq-Tenant-ID": "default",
    },
)
t2 = time.monotonic()
r = conn.getresponse()
data = r.read().decode()
t3 = time.monotonic()

print(f"connect+send: {t2-t1:.3f}s")
print(f"recv: {t3-t2:.3f}s")
print(f"total: {t3-t0:.3f}s")
print(json.loads(data))
