# Chat insert

Do not build a Slack or Teams app for v1. Point the client at the gateway.

## Slack / Teams / Cursor / any OpenAI SDK

```
OPENAI_BASE_URL=http://localhost:8080/v1
OPENAI_API_KEY=<ANONREQ_API_KEY>
```

Add header `X-AnonReq-Locale: de-DE` (Slack custom headers via the enterprise gateway, or a tiny bot that sets it). Paste [`SYSTEM_PROMPT.de.md`](SYSTEM_PROMPT.de.md) as the system prompt.

Users keep using Claude/GPT. Legal unfreezes because identifiers are tokens on the wire to the vendor.

## curl

```bash
curl -s "$ANONREQ_URL/v1/chat/completions" \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-AnonReq-Locale: de-DE" \
  -d @- <<'EOF'
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "Du siehst maskierte Tokens wie [KVNR_0]. Frage nicht nach den Klarwerten."},
    {"role": "user", "content": "Ist KVNR A123456780 plausibel?"}
  ]
}
EOF
```
