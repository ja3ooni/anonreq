/**
 * Process-wide demo policy. No Next.js or path-alias imports, so tests can load it.
 */

const TENANT = /^[A-Za-z0-9._-]{1,64}$/;

export class DemoPolicyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DemoPolicyError";
  }
}

/**
 * Mock fixtures run only when ANONREQ_MOCK is explicitly true.
 * An empty gateway URL does not turn mock on. Production refuses the flag.
 */
export function resolveMockMode(mockFlag: string | undefined, nodeEnv: string | undefined): boolean {
  const flag = mockFlag?.trim().toLowerCase();
  const enabled = flag === "1" || flag === "true" || flag === "yes";
  if (!enabled) {
    return false;
  }
  if (nodeEnv === "production") {
    throw new DemoPolicyError(
      "ANONREQ_MOCK=true is refused when NODE_ENV=production. This demo has no login and must not serve fixtures in production.",
    );
  }
  return true;
}

/** Tenant is pinned on the server. Client-supplied tenant ids are ignored. */
export function resolveServerTenant(tenantId: string | undefined): string {
  const configured = tenantId?.trim() ?? "";
  if (!TENANT.test(configured)) {
    throw new DemoPolicyError(
      "ANONREQ_TENANT_ID is not set or is not a valid tenant id. The browser cannot choose the tenant.",
    );
  }
  return configured;
}
