# Ticketing insert

Jira Automation, Zendesk triggers, or any HTTP webhook can POST a ticket payload here. The script pulls summary + body, calls AnonReq’s OpenAI-compatible API, and prints the restored model answer. Identifiers never go upstream.

```bash
export ANONREQ_URL=http://localhost:8080
export ANONREQ_API_KEY=...   # gateway key, not the model key

python3 forward_ticket.py sample-jira.json
python3 forward_ticket.py sample-zendesk.json
python3 forward_ticket.py sample-generic.json
```

Wire-up:

- **Jira:** Automation → Incoming webhook is not required. Use “Send web request” on issue created, body `{{issue.key}}` plus description, **or** point this script at Jira’s native webhook JSON (`sample-jira.json`).
- **Zendesk:** Trigger → notify webhook with ticket JSON (`sample-zendesk.json`).
- **Generic:** `{"title":"...","body":"..."}`.

The gateway must already hold `PROVIDER_API_KEY`. This adapter does not talk to OpenAI directly.
