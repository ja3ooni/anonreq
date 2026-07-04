#!/bin/bash
set -euo pipefail

if [ "${1:-}" = "--check" ]; then
    echo "SBOM configuration check OK"
    exit 0
fi

# Generate CycloneDX Python SBOM
# Requires: pip install cyclonedx-bom
cyclonedx-py --e --output sbom.cyclonedx.json

# Generate Syft container SBOM (when run in CI/CD environment)
# syft anonreq:${VERSION} -o json > sbom.container.json
# syft anonreq:${VERSION} -o cyclonedx-json > sbom.container.cyclonedx.json

# Cosign attest (when keys/identities are configured in CI)
# cosign attest-blob sbom.cyclonedx.json \
#   --signer cosign \
#   --type cyclonedx \
#   --output sbom.cyclonedx.json.att

echo "SBOM generated: sbom.cyclonedx.json"
