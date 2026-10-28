import { GatewayRequestError } from "@/lib/gateway-error";

export function jsonOk(data: unknown, status = 200): Response {
  return Response.json(data, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

export function jsonError(message: string, status: number): Response {
  return Response.json(
    { error: { message, status } },
    { status, headers: { "cache-control": "no-store" } },
  );
}

export function fromGatewayError(error: unknown): Response {
  if (error instanceof GatewayRequestError) {
    return jsonError(error.message, error.status);
  }
  return jsonError("Unexpected server error", 500);
}
