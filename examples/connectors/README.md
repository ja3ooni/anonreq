# Three workflow inserts (Germany close path)

Do not build 80 connectors. These three match the stories that actually close:

| Insert | Path | What the buyer sees |
| --- | --- | --- |
| Ticketing | [`tickets/`](tickets/) | Jira / Zendesk / generic webhook → AnonReq → their model |
| Chat | [`chat/`](chat/) | Slack/Teams (or any OpenAI client): base URL + system prompt |
| Docs | [`docs/`](docs/) | Insurance-claim text through the same `/v1/chat/completions` path |

All three assume the Germany demo is up (`docs/operations/germany-demo.md`) and `X-AnonReq-Locale: de-DE`.
