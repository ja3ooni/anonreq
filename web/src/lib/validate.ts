import { GatewayRequestError } from "@/lib/gateway-error";

const TENANT = /^[A-Za-z0-9._-]{1,64}$/;
const LOCALE = /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$/;
const MODEL = /^[\w.:-]{1,128}$/;
const ENTITY = /^[A-Z][A-Z0-9_]{0,63}$/;
const DATE =
  /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?)?$/;
const TOKEN = /^[\w.:@-]{1,128}$/;

export const MAX_PROMPT_CHARS = 8_000;

export function defaultTenant(): string {
  const configured =
    process.env.ANONREQ_TENANT_ID?.trim() ||
    process.env.ANONREQ_DEFAULT_TENANT?.trim() ||
    "default";
  if (!TENANT.test(configured)) {
    return "default";
  }
  return configured;
}

export function requireTenant(value: unknown): string {
  const tenant = typeof value === "string" && value.trim() ? value.trim() : defaultTenant();
  if (!TENANT.test(tenant)) {
    throw new GatewayRequestError("Tenant id is not valid", 400);
  }
  return tenant;
}

export function optionalTenant(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) {
    return undefined;
  }
  if (!TENANT.test(value.trim())) {
    throw new GatewayRequestError("Tenant id is not valid", 400);
  }
  return value.trim();
}

export function requireLocale(value: unknown, fallback: string): string {
  const locale = typeof value === "string" && value.trim() ? value.trim() : fallback;
  if (!LOCALE.test(locale)) {
    throw new GatewayRequestError("Locale is not valid", 400);
  }
  return locale;
}

export function requireModel(value: unknown): string {
  if (typeof value !== "string" || !MODEL.test(value.trim())) {
    throw new GatewayRequestError("Model alias is not valid", 400);
  }
  return value.trim();
}

export function requirePrompt(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new GatewayRequestError("Prompt is empty", 400);
  }
  if (value.length > MAX_PROMPT_CHARS) {
    throw new GatewayRequestError("Prompt is too long", 400);
  }
  return value;
}

export function optionalEntityType(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) {
    return undefined;
  }
  const entity = value.trim();
  if (!ENTITY.test(entity)) {
    throw new GatewayRequestError("Entity type is not valid", 400);
  }
  return entity;
}

export function optionalDate(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) {
    return undefined;
  }
  let date = value.trim();
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(date)) {
    date = `${date}:00`;
  }
  if (!DATE.test(date) || Number.isNaN(Date.parse(date))) {
    throw new GatewayRequestError("Date filter is not valid", 400);
  }
  return date;
}

export function optionalToken(value: unknown, label: string): string | undefined {
  if (typeof value !== "string" || !value.trim()) {
    return undefined;
  }
  if (!TOKEN.test(value.trim())) {
    throw new GatewayRequestError(`${label} is not valid`, 400);
  }
  return value.trim();
}

export function queryInt(
  value: string | null,
  fallback: number,
  max: number,
): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > max) {
    throw new GatewayRequestError("Paging parameter is not valid", 400);
  }
  return parsed;
}

export function querySort(value: string | null): "timestamp:desc" | "timestamp:asc" {
  if (!value || value === "timestamp:desc") {
    return "timestamp:desc";
  }
  if (value === "timestamp:asc") {
    return "timestamp:asc";
  }
  throw new GatewayRequestError("Sort is not valid", 400);
}
