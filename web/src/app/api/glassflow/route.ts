import { resolveGlassFlowConfig } from "@/lib/glassflow-config";
import { forwardToGlassFlow } from "@/lib/glassflow-forward";
import { parseGlassFlowBundle, readCappedBody } from "@/lib/glassflow-payload";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const NO_STORE = { "cache-control": "no-store" };

function error(message: string, status: number) {
  return Response.json({ error: { message, status } }, { status, headers: NO_STORE });
}

export async function POST(request: Request) {
  try {
    // Body capped at 64 KB (413), then rebuilt from an allowlist (400 on any invalid field).
    const read = await readCappedBody(request);
    if (!read.ok) return error(read.message, read.status);
    const parsed = parseGlassFlowBundle(read.text);
    if (!parsed.ok) return error(parsed.message, parsed.status);
    const result = await forwardToGlassFlow(parsed.bundle, resolveGlassFlowConfig(process.env));
    return Response.json(result.body, { status: result.status, headers: NO_STORE });
  } catch {
    return error("GlassFlow forwarding failed", 500);
  }
}
