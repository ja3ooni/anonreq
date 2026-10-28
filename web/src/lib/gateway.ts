import { GatewayRequestError } from "@/lib/gateway-error";
import { DemoPolicyError, resolveMockMode } from "@/lib/runtime-policy";

export function isMockMode(): boolean {
  try {
    return resolveMockMode(process.env.ANONREQ_MOCK, process.env.NODE_ENV);
  } catch (error) {
    if (error instanceof DemoPolicyError) {
      throw new GatewayRequestError(error.message, 500);
    }
    throw error;
  }
}

/** Exercise the 404 placeholder while mock mode is on. */
export function mockPreviewDisabled(): boolean {
  const flag = process.env.ANONREQ_MOCK_PREVIEW?.trim().toLowerCase();
  return flag === "404" || flag === "off" || flag === "disabled";
}

function origin(): string {
  const raw = process.env.ANONREQ_GATEWAY_URL?.trim();
  if (!raw) {
    throw new GatewayRequestError(
      "ANONREQ_GATEWAY_URL is not set. Mock mode stays off unless ANONREQ_MOCK=true, and that flag is refused when NODE_ENV=production.",
      500,
    );
  }
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new GatewayRequestError("ANONREQ_GATEWAY_URL is not a valid URL", 500);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new GatewayRequestError("ANONREQ_GATEWAY_URL must be http or https", 500);
  }
  const path = url.pathname.replace(/\/$/, "");
  return `${url.origin}${path === "/" ? "" : path}`;
}

function apiKey(kind: "user" | "admin"): string {
  if (kind === "admin") {
    const admin = process.env.ANONREQ_ADMIN_API_KEY?.trim();
    if (!admin) {
      throw new GatewayRequestError("ANONREQ_ADMIN_API_KEY is not set", 500);
    }
    return admin;
  }
  const key = process.env.ANONREQ_API_KEY?.trim();
  if (!key) {
    throw new GatewayRequestError("ANONREQ_API_KEY is not set", 500);
  }
  return key;
}

export interface GatewayCall {
  path: string;
  method?: "GET" | "POST";
  query?: Record<string, string | undefined>;
  jsonBody?: unknown;
  auth: "user" | "admin";
  tenantId: string;
  locale?: string;
  timeoutMs?: number;
  accept?: string;
}

/**
 * Server-side proxy call. The browser never sees gateway URLs or keys.
 * Paths are chosen by our route handlers, not taken from the client.
 */
export async function gatewayRequest(options: GatewayCall): Promise<Response> {
  const url = new URL(origin());
  const extra = options.path.startsWith("/") ? options.path : `/${options.path}`;
  url.pathname = `${url.pathname.replace(/\/$/, "")}${extra}`;
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${apiKey(options.auth)}`);
  headers.set("X-AnonReq-Tenant-ID", options.tenantId);
  if (options.locale) {
    headers.set("X-AnonReq-Locale", options.locale);
  }
  headers.set("Accept", options.accept ?? "application/json");
  if (options.jsonBody !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 30_000);
  try {
    const response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.jsonBody !== undefined ? JSON.stringify(options.jsonBody) : undefined,
      signal: controller.signal,
      cache: "no-store",
      redirect: "manual",
    });
    if (response.status >= 300 && response.status < 400) {
      throw new GatewayRequestError("Gateway redirected the request", 502);
    }
    return response;
  } catch (error) {
    if (error instanceof GatewayRequestError) {
      throw error;
    }
    if (error instanceof Error && error.name === "AbortError") {
      throw new GatewayRequestError("Gateway request timed out", 504);
    }
    throw new GatewayRequestError("Gateway is unreachable", 503);
  } finally {
    clearTimeout(timeout);
  }
}

export async function readGatewayJson(
  response: Response,
): Promise<{ status: number; json: unknown }> {
  const text = await response.text();
  if (!text) {
    return { status: response.status, json: null };
  }
  try {
    return { status: response.status, json: JSON.parse(text) as unknown };
  } catch {
    return { status: response.status, json: null };
  }
}

/** Safe message only. Never forwards a raw body that might echo a prompt. */
export function gatewayErrorMessage(status: number, json: unknown): string {
  if (!json || typeof json !== "object") {
    return `Gateway returned HTTP ${status}`;
  }
  const record = json as Record<string, unknown>;
  const nested = record.error;
  let message = "";
  if (typeof nested === "object" && nested && "message" in nested) {
    const value = (nested as { message?: unknown }).message;
    if (typeof value === "string") {
      message = value;
    }
  } else if (typeof record.detail === "string") {
    message = record.detail;
  } else if (typeof record.message === "string") {
    message = record.message;
  }
  message = message.replace(/\s+/g, " ").trim().slice(0, 400);
  if (!message) {
    return `Gateway returned HTTP ${status}`;
  }
  const block = record.block_detail;
  if (block && typeof block === "object" && "entities_detected" in block) {
    const types = (block as { entities_detected?: unknown }).entities_detected;
    if (Array.isArray(types) && types.every((item) => typeof item === "string")) {
      message = `${message} (${types.join(", ")})`;
    }
  }
  return message;
}

export function headerOrNull(headers: Headers, name: string): string | null {
  const value = headers.get(name);
  if (value == null || value.trim() === "") {
    return null;
  }
  return value.trim();
}
