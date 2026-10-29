import { FileExtractError, extractFileText, MAX_UPLOAD_BYTES } from "@/lib/file-extract";
import { GatewayRequestError } from "@/lib/gateway-error";
import { fromGatewayError, jsonError, jsonOk } from "@/lib/http";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const contentType = request.headers.get("content-type") ?? "";
    if (contentType.includes("multipart/form-data")) {
      const formData = await request.formData().catch(() => null);
      if (!formData) {
        throw new GatewayRequestError("Invalid multipart upload payload", 400);
      }
      const file = formData.get("file");
      if (!(file instanceof File)) {
        throw new GatewayRequestError("Missing 'file' field in upload", 400);
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        throw new GatewayRequestError("File exceeds the 5 MB demo upload limit", 400);
      }
      const buffer = await file.arrayBuffer();
      const result = extractFileText(new Uint8Array(buffer), file.name, file.type);
      return jsonOk(result);
    }

    const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
    if (!body || typeof body !== "object") {
      throw new GatewayRequestError("Upload must be multipart/form-data or JSON", 400);
    }
    const filename = typeof body.filename === "string" ? body.filename : "upload.txt";
    const mimeType = typeof body.mimeType === "string" ? body.mimeType : undefined;
    const base64 = typeof body.base64 === "string" ? body.base64 : "";
    if (!base64) {
      throw new GatewayRequestError("Missing file bytes", 400);
    }
    const bytes = new Uint8Array(Buffer.from(base64, "base64"));
    const result = extractFileText(bytes, filename, mimeType);
    return jsonOk(result);
  } catch (error) {
    if (error instanceof FileExtractError) {
      return jsonError(error.message, error.status);
    }
    return fromGatewayError(error);
  }
}
