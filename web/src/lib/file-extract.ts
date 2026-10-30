import { inflateRawSync, inflateSync } from "node:zlib";

export class FileExtractError extends Error {
  readonly status: number;

  constructor(message: string, status = 400) {
    super(message);
    this.name = "FileExtractError";
    this.status = status;
  }
}

export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MiB
export const DEFAULT_MAX_EXTRACT_CHARS = 7_200; // Leave headroom under 8,000 prompt limit for task instructions

export type SupportedFileFormat = "txt" | "md" | "csv" | "json" | "log" | "eml" | "docx" | "pdf";

export interface ExtractedFileResult {
  filename: string;
  format: SupportedFileFormat;
  byteSize: number;
  charCount: number;
  truncated: boolean;
  text: string;
}

const EXTENSION_MAP: Record<string, SupportedFileFormat> = {
  ".txt": "txt",
  ".md": "md",
  ".markdown": "md",
  ".csv": "csv",
  ".tsv": "csv",
  ".json": "json",
  ".log": "log",
  ".eml": "eml",
  ".docx": "docx",
  ".pdf": "pdf",
};

export function detectFileFormat(filename: string, mimeType?: string): SupportedFileFormat {
  const lower = filename.trim().toLowerCase();
  for (const [ext, format] of Object.entries(EXTENSION_MAP)) {
    if (lower.endsWith(ext)) {
      return format;
    }
  }
  const mime = (mimeType ?? "").toLowerCase();
  if (mime.includes("pdf")) return "pdf";
  if (mime.includes("wordprocessingml") || mime.includes("docx")) return "docx";
  if (mime.includes("json")) return "json";
  if (mime.includes("csv")) return "csv";
  if (mime.includes("markdown")) return "md";
  if (mime.includes("message/rfc822")) return "eml";
  if (mime.startsWith("text/")) return "txt";
  throw new FileExtractError(
    "Unsupported file format. Supported: .txt, .md, .csv, .json, .log, .eml, .pdf, .docx",
    400,
  );
}

export function extractFileText(
  bytes: Uint8Array,
  filename: string,
  mimeType?: string,
  maxChars: number = DEFAULT_MAX_EXTRACT_CHARS,
): ExtractedFileResult {
  if (bytes.byteLength === 0) {
    throw new FileExtractError("Uploaded file is empty", 400);
  }
  if (bytes.byteLength > MAX_UPLOAD_BYTES) {
    throw new FileExtractError("File exceeds the 5 MB demo upload limit", 400);
  }

  const format = detectFileFormat(filename, mimeType);
  let rawText = "";

  if (format === "docx") {
    rawText = extractDocxText(bytes);
  } else if (format === "pdf") {
    rawText = extractPdfText(bytes);
  } else if (format === "json") {
    rawText = extractJsonText(bytes);
  } else {
    rawText = decodeUtf8(bytes);
  }

  const normalized = normalizeWhitespace(rawText);
  if (!normalized) {
    throw new FileExtractError(
      `No readable text could be extracted from ${filename || format.toUpperCase()}`,
      400,
    );
  }

  const truncated = normalized.length > maxChars;
  const text = truncated ? normalized.slice(0, maxChars) : normalized;

  return {
    filename: filename || `upload.${format}`,
    format,
    byteSize: bytes.byteLength,
    charCount: text.length,
    truncated,
    text,
  };
}

function decodeUtf8(bytes: Uint8Array): string {
  const decoder = new TextDecoder("utf-8", { fatal: false });
  return decoder.decode(bytes);
}

function normalizeWhitespace(input: string): string {
  return input
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\u0000/g, "")
    .replace(/[^\S\n]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function extractJsonText(bytes: Uint8Array): string {
  const raw = decodeUtf8(bytes);
  try {
    const parsed = JSON.parse(raw) as unknown;
    return JSON.stringify(parsed, null, 2);
  } catch {
    return raw;
  }
}

/**
 * Extracts text from a .docx (OOXML ZIP) archive by reading word/document.xml.
 * Supports ZIP local file headers and central directory entries (Store = 0, Deflate = 8).
 */
export function extractDocxText(bytes: Uint8Array): string {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes.byteLength < 4 || view.getUint32(0, true) !== 0x04034b50) {
    throw new FileExtractError("File is not a valid .docx archive", 400);
  }

  const xml = readZipEntry(bytes, view, "word/document.xml");
  if (!xml) {
    throw new FileExtractError("word/document.xml not found in .docx file", 400);
  }

  const withBreaks = xml
    .replace(/<w:tab\b[^>]*\/>/g, "\t")
    .replace(/<w:(?:br|cr)\b[^>]*\/>/g, "\n")
    .replace(/<\/w:p>/g, "\n")
    .replace(/<\/w:tr>/g, "\n")
    .replace(/<\/w:tc>/g, "\t");

  const stripped = withBreaks.replace(/<[^>]+>/g, "");
  return decodeXmlEntities(stripped);
}

function readZipEntry(bytes: Uint8Array, view: DataView, targetName: string): string | null {
  // 1. Try Central Directory at the end of the archive first (handles data descriptors cleanly)
  const eocdOffset = findEndOfCentralDirectory(bytes, view);
  if (eocdOffset !== -1) {
    const cdSize = view.getUint32(eocdOffset + 12, true);
    const cdOffset = view.getUint32(eocdOffset + 16, true);
    let ptr = cdOffset;
    const end = Math.min(bytes.byteLength, cdOffset + cdSize);
    while (ptr + 46 <= end && view.getUint32(ptr, true) === 0x02014b50) {
      const method = view.getUint16(ptr + 10, true);
      const compSize = view.getUint32(ptr + 20, true);
      const nameLen = view.getUint16(ptr + 28, true);
      const extraLen = view.getUint16(ptr + 30, true);
      const commentLen = view.getUint16(ptr + 32, true);
      const localHeaderOffset = view.getUint32(ptr + 42, true);
      const name = decodeUtf8(bytes.subarray(ptr + 46, ptr + 46 + nameLen));
      if (name === targetName && localHeaderOffset + 30 <= bytes.byteLength) {
        const localNameLen = view.getUint16(localHeaderOffset + 26, true);
        const localExtraLen = view.getUint16(localHeaderOffset + 28, true);
        const dataStart = localHeaderOffset + 30 + localNameLen + localExtraLen;
        const compressed = bytes.subarray(dataStart, dataStart + compSize);
        return decompressZipSlice(compressed, method);
      }
      ptr += 46 + nameLen + extraLen + commentLen;
    }
  }

  // 2. Fallback: scan local file headers sequentially
  let offset = 0;
  while (offset + 30 <= bytes.byteLength && view.getUint32(offset, true) === 0x04034b50) {
    const method = view.getUint16(offset + 8, true);
    const compSize = view.getUint32(offset + 18, true);
    const nameLen = view.getUint16(offset + 26, true);
    const extraLen = view.getUint16(offset + 28, true);
    const name = decodeUtf8(bytes.subarray(offset + 30, offset + 30 + nameLen));
    const dataStart = offset + 30 + nameLen + extraLen;
    if (name === targetName && compSize > 0 && dataStart + compSize <= bytes.byteLength) {
      return decompressZipSlice(bytes.subarray(dataStart, dataStart + compSize), method);
    }
    if (compSize === 0) {
      break;
    }
    offset = dataStart + compSize;
  }
  return null;
}

function findEndOfCentralDirectory(bytes: Uint8Array, view: DataView): number {
  const minOffset = Math.max(0, bytes.byteLength - 65557);
  for (let i = bytes.byteLength - 22; i >= minOffset; i -= 1) {
    if (view.getUint32(i, true) === 0x06054b50) {
      return i;
    }
  }
  return -1;
}

function decompressZipSlice(slice: Uint8Array, method: number): string {
  if (method === 0) {
    return decodeUtf8(slice);
  }
  if (method === 8) {
    const inflated = inflateRawSync(slice);
    return decodeUtf8(inflated);
  }
  throw new FileExtractError(`Unsupported ZIP compression method ${method} in .docx`, 400);
}

function decodeXmlEntities(text: string): string {
  return text
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex: string) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec: string) => String.fromCodePoint(parseInt(dec, 10)))
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

/**
 * Extracts text from a PDF file by scanning uncompressed and FlateDecode-compressed
 * content streams for PDF text operators (Tj, TJ, ', ").
 */
export function extractPdfText(bytes: Uint8Array): string {
  const latin1 = new TextDecoder("latin1").decode(bytes);
  if (!latin1.startsWith("%PDF-")) {
    throw new FileExtractError("File is not a valid PDF document", 400);
  }

  const chunks: string[] = [];
  const streamRegex = /stream(?:\r\n|\n)([\s\S]*?)(?:\r\n|\n)?endstream/g;
  for (const match of latin1.matchAll(streamRegex)) {
    const matchIndex = match.index ?? 0;
    const headerWindow = latin1.slice(Math.max(0, matchIndex - 320), matchIndex);
    const streamBody = match[1] ?? "";
    const startOffset = matchIndex + match[0].indexOf(streamBody);
    const rawSlice = bytes.subarray(startOffset, startOffset + streamBody.length);

    let decodedContent = "";
    if (/\/FlateDecode\b/.test(headerWindow)) {
      decodedContent = tryInflatePdfStream(rawSlice);
    } else if (!/\/(?:DCTDecode|JPXDecode|JBIG2Decode|CCITTFaxDecode)\b/.test(headerWindow)) {
      decodedContent = streamBody;
    }

    if (decodedContent && /\bBT\b/.test(decodedContent)) {
      const extracted = parsePdfTextBlocks(decodedContent);
      if (extracted) {
        chunks.push(extracted);
      }
    }
  }

  return chunks.join("\n\n");
}

function tryInflatePdfStream(slice: Uint8Array): string {
  // Trim trailing CR/LF if captured before endstream
  let end = slice.byteLength;
  while (end > 0 && (slice[end - 1] === 0x0a || slice[end - 1] === 0x0d)) {
    end -= 1;
  }
  const candidates = [slice, slice.subarray(0, end)];
  for (const candidate of candidates) {
    try {
      return new TextDecoder("latin1").decode(inflateSync(candidate));
    } catch {
      try {
        return new TextDecoder("latin1").decode(inflateRawSync(candidate));
      } catch {
        // continue
      }
    }
  }
  return "";
}

function parsePdfTextBlocks(content: string): string {
  const lines: string[] = [];
  const btEtRegex = /\bBT\b([\s\S]*?)\bET\b/g;
  for (const blockMatch of content.matchAll(btEtRegex)) {
    const block = blockMatch[1] ?? "";
    let currentLine = "";
    const tokenRegex =
      /\[((?:[^[\]]|\((?:\\.|[^\\()])*\))*)\]\s*TJ|\((?:\\.|[^\\()])*\)\s*(?:Tj|'|")|<([0-9A-Fa-f\s]+)>\s*Tj|(T\*|\b(?:TD|Td|Tm)\b)/g;
    for (const token of block.matchAll(tokenRegex)) {
      const full = token[0];
      if (token[1] !== undefined) {
        // TJ array
        const inner = token[1];
        for (const sub of inner.matchAll(/\((?:\\.|[^\\()])*\)|<([0-9A-Fa-f\s]+)>|(-?\d+(?:\.\d+)?)/g)) {
          if (sub[0].startsWith("(")) {
            currentLine += decodePdfLiteralString(sub[0].slice(1, -1));
          } else if (sub[1] !== undefined) {
            currentLine += decodePdfHexString(sub[1]);
          } else if (sub[2] !== undefined && Number(sub[2]) < -120) {
            currentLine += " ";
          }
        }
      } else if (token[2] !== undefined) {
        currentLine += decodePdfHexString(token[2]);
      } else if (token[3] !== undefined) {
        if (currentLine.trim()) {
          lines.push(currentLine.trim());
          currentLine = "";
        }
      } else if (full.startsWith("(")) {
        const closeIdx = full.lastIndexOf(")");
        const strPart = full.slice(1, closeIdx);
        const op = full.slice(closeIdx + 1).trim();
        if ((op === "'" || op === '"') && currentLine.trim()) {
          lines.push(currentLine.trim());
          currentLine = "";
        }
        currentLine += decodePdfLiteralString(strPart);
      }
    }
    if (currentLine.trim()) {
      lines.push(currentLine.trim());
    }
  }
  return lines.join("\n");
}

function decodePdfLiteralString(raw: string): string {
  let out = "";
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    if (ch !== "\\") {
      out += ch;
      continue;
    }
    i += 1;
    if (i >= raw.length) break;
    const next = raw[i];
    if (next === "n") out += "\n";
    else if (next === "r") out += "\r";
    else if (next === "t") out += "\t";
    else if (next === "b") out += "\b";
    else if (next === "f") out += "\f";
    else if (next === "(" || next === ")" || next === "\\") out += next;
    else if (next === "\n" || next === "\r") {
      if (next === "\r" && raw[i + 1] === "\n") i += 1;
    } else if (next >= "0" && next <= "7") {
      let oct = next;
      if (raw[i + 1] && raw[i + 1] >= "0" && raw[i + 1] <= "7") {
        oct += raw[i + 1];
        i += 1;
        if (raw[i + 1] && raw[i + 1] >= "0" && raw[i + 1] <= "7") {
          oct += raw[i + 1];
          i += 1;
        }
      }
      out += String.fromCharCode(parseInt(oct, 8));
    } else {
      out += next;
    }
  }
  return out;
}

function decodePdfHexString(hexInput: string): string {
  const clean = hexInput.replace(/\s+/g, "");
  const padded = clean.length % 2 === 1 ? `${clean}0` : clean;
  const bytes = new Uint8Array(padded.length / 2);
  for (let i = 0; i < padded.length; i += 2) {
    bytes[i / 2] = parseInt(padded.slice(i, i + 2), 16);
  }
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    return new TextDecoder("utf-16be").decode(bytes.subarray(2));
  }
  return new TextDecoder("latin1").decode(bytes);
}

/**
 * Builds a valid minimal PDF containing the given text lines (used for tests and
 * downloadable sample PDF generation).
 */
export function createMinimalPdf(lines: string[]): Uint8Array {
  const escapePdf = (line: string) =>
    line
      .replace(/\\/g, "\\\\")
      .replace(/\(/g, "\\(")
      .replace(/\)/g, "\\)");

  const ops = ["BT", "/F1 11 Tf", "50 760 Td", "15 TL"];
  lines.forEach((line, index) => {
    if (index === 0) {
      ops.push(`(${escapePdf(line)}) Tj`);
    } else {
      ops.push(`T* (${escapePdf(line)}) Tj`);
    }
  });
  ops.push("ET");
  const stream = ops.join("\n");

  const objects = [
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
    `4 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}\nendstream\nendobj\n`,
    "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n",
  ];

  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (const obj of objects) {
    offsets.push(pdf.length);
    pdf += obj;
  }
  const xrefStart = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) {
    pdf += `${String(off).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`;

  const out = new Uint8Array(pdf.length);
  for (let i = 0; i < pdf.length; i += 1) {
    out[i] = pdf.charCodeAt(i) & 0xff;
  }
  return out;
}

/**
 * Builds a valid minimal .docx archive (Store method 0) containing the given paragraphs.
 */
export function createMinimalDocx(paragraphs: string[]): Uint8Array {
  const escapeXml = (value: string) =>
    value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  const bodyXml = paragraphs
    .map((para) => `<w:p><w:r><w:t>${escapeXml(para)}</w:t></w:r></w:p>`)
    .join("");
  const docXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${bodyXml}</w:body></w:document>`;

  const encoder = new TextEncoder();
  const fileNameBytes = encoder.encode("word/document.xml");
  const dataBytes = encoder.encode(docXml);

  const localHeaderLen = 30 + fileNameBytes.length;
  const cdHeaderLen = 46 + fileNameBytes.length;
  const eocdLen = 22;
  const totalLen = localHeaderLen + dataBytes.length + cdHeaderLen + eocdLen;

  const buffer = new Uint8Array(totalLen);
  const view = new DataView(buffer.buffer);

  // Local file header
  view.setUint32(0, 0x04034b50, true);
  view.setUint16(4, 20, true);
  view.setUint16(8, 0, true); // method 0 = Store
  view.setUint32(18, dataBytes.length, true);
  view.setUint32(22, dataBytes.length, true);
  view.setUint16(26, fileNameBytes.length, true);
  buffer.set(fileNameBytes, 30);
  buffer.set(dataBytes, localHeaderLen);

  // Central directory header
  const cdOffset = localHeaderLen + dataBytes.length;
  view.setUint32(cdOffset, 0x02014b50, true);
  view.setUint16(cdOffset + 4, 20, true);
  view.setUint16(cdOffset + 6, 20, true);
  view.setUint16(cdOffset + 10, 0, true);
  view.setUint32(cdOffset + 20, dataBytes.length, true);
  view.setUint32(cdOffset + 24, dataBytes.length, true);
  view.setUint16(cdOffset + 28, fileNameBytes.length, true);
  view.setUint32(cdOffset + 42, 0, true);
  buffer.set(fileNameBytes, cdOffset + 46);

  // End of central directory
  const eocdOffset = cdOffset + cdHeaderLen;
  view.setUint32(eocdOffset, 0x06054b50, true);
  view.setUint16(eocdOffset + 8, 1, true);
  view.setUint16(eocdOffset + 10, 1, true);
  view.setUint32(eocdOffset + 12, cdHeaderLen, true);
  view.setUint32(eocdOffset + 16, cdOffset, true);

  return buffer;
}
