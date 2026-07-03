# Getting Started with AnonReq

## Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- An OpenAI, Anthropic, or Gemini API key

## Quickstart

Run the following scripts from the repository root:

```bash
# Step 1: Start the gateway
./examples/quickstart/01-start-gateway.sh

# Step 2: Send a test request with PII
./examples/quickstart/02-basic-anonymization.sh

# Step 3: Clean up
./examples/quickstart/03-cleanup.sh
```

The quickstart scripts handle all setup, verification, and cleanup automatically. Each script exits 0 on success or 1 on failure with diagnostic output.

## Next Steps

- See `docs/en/installation.md` for detailed installation instructions
- See `examples/curl/`, `examples/python/`, `examples/typescript/`, and `examples/go/` for SDK examples in your language
- See `docs/en/deployment.md` for production deployment guidance
- See `docs/en/compliance.md` for compliance preset configuration
- See the project README for a complete overview
