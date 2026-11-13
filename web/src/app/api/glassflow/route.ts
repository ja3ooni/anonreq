import { resolveGlassFlowConfig } from "@/lib/glassflow-config";
import { forwardToGlassFlow } from "@/lib/glassflow-forward";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Forwards the sanitized GlassFlow bundle to the env-configured Rius/Tares targets.
 * Returns delivered flags, statuses and the target host only (see glassflow-forward.ts).
 */
export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as unknown;
  try {
    const result = await forwardToGlassFlow(body, resolveGlassFlowConfig(process.env));
    return Response.json(result.body, { status: result.status, headers: { "cache-control": "no-store" } });
  } catch {
    return Response.json(
      { error: { message: "GlassFlow forwarding failed", status: 500 } },
      { status: 500, headers: { "cache-control": "no-store" } },
    );
  }
}
