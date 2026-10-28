/** Detect the gateway's mid-stream CSV failure trailer and drop it. */

export interface ExportInspection {
  csv: string;
  failed: boolean;
  dataRows: number;
}

const ERROR_REQUEST_ID = "#error";
const ERROR_DECISION = "export_failed";

export function inspectExportCsv(text: string): ExportInspection {
  const table = parseCsv(text);
  if (table.length === 0) {
    return { csv: text, failed: false, dataRows: 0 };
  }
  const header = table[0] ?? [];
  const requestIndex = header.indexOf("request_id");
  const decisionIndex = header.indexOf("decision");
  const failedAt = table.findIndex((row, index) => index > 0 && isFailureRow(row, requestIndex, decisionIndex));
  if (failedAt === -1) {
    return { csv: text.endsWith("\n") ? text : `${text}\n`, failed: false, dataRows: Math.max(0, table.length - 1) };
  }
  const kept = table.slice(0, failedAt);
  return {
    csv: serializeCsv(kept),
    failed: true,
    dataRows: Math.max(0, kept.length - 1),
  };
}

function isFailureRow(row: string[], requestIndex: number, decisionIndex: number): boolean {
  const requestId = (row[requestIndex] ?? "").replace(/^'/, "");
  const decision = row[decisionIndex] ?? "";
  return requestId === ERROR_REQUEST_ID && decision === ERROR_DECISION;
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  const source = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (quoted) {
      if (char === '"') {
        if (source[index + 1] === '"') {
          cell += '"';
          index += 1;
        } else {
          quoted = false;
        }
      } else {
        cell += char;
      }
      continue;
    }
    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(cell);
      cell = "";
    } else if (char === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else if (char !== "\r") {
      cell += char;
    }
  }
  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows.filter((item) => item.some((value) => value.length > 0));
}

function serializeCsv(rows: string[][]): string {
  return `${rows.map((row) => row.map(csvCell).join(",")).join("\n")}\n`;
}

function csvCell(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
