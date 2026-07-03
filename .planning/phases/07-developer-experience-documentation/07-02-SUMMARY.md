# Plan 07-02 — SUMMARY

**Plan:** 07-02-SDK-EXAMPLES
**Phase:** 07-developer-experience-documentation
**Status:** Complete

## Deliverables

- [x] 4 curl example scripts covering:
  - `basic-anonymization.sh` — POST with API key, anonymize
  - `streaming.sh` — SSE streaming example
  - `gdpr-preset.sh` — GDPR compliance preset
  - `locale-de.sh` — German locale detection
- [x] 4 Python projects (`main.py` + `requirements.txt` + `README.md` each):
  - `basic-anonymization/` — OpenAI client with AnonReq proxy
  - `streaming/` — Streaming response handling
  - `gdpr-preset/` — GDPR preset header
  - `locale-de/` — German locale header
- [x] 4 TypeScript projects (`package.json` + `src/index.ts` + `tsconfig.json` + `README.md` each):
  - `basic-anonymization/`, `streaming/`, `gdpr-preset/`, `locale-de/`
- [x] 4 Go projects (`go.mod` + `main.go` + `README.md` each):
  - `basic-anonymization/`, `streaming/`, `gdpr-preset/`, `locale-de/`
- [x] README.md with 13 sections delivered as separate output

## Key Decisions

- All SDKs use the OpenAI-compatible schema (single wire protocol, adapters internal)
- Python examples use `httpx` directly for clarity (no OpenAI SDK dependency)
- TypeScript examples use `node-fetch` (zero-dependency runtime)
- Go examples use standard `net/http` + `encoding/json`
- Every project is standalone runnable (no monorepo build tools required)
