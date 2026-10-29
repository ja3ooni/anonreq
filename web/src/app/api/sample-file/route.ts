import { createMinimalDocx, createMinimalPdf } from "@/lib/file-extract";
import { BUYER_SCENARIOS } from "@/lib/scenarios";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const scenarioId = url.searchParams.get("scenario") ?? "bank";
  const format = (url.searchParams.get("format") ?? "txt").toLowerCase();
  const lang = url.searchParams.get("lang") === "en" ? "en" : "de";

  const scenario = BUYER_SCENARIOS.find((item) => item.id === scenarioId) ?? BUYER_SCENARIOS[0];
  const copy = lang === "en" ? scenario.en : scenario.de;
  const baseName = `${scenario.sampleFilename}-${lang}`;

  if (format === "pdf") {
    const lines = [
      `AnonReq Demo Sample (${scenario.badge})`,
      ...copy.prompt.split(/\n+/).flatMap((line) => wrapLine(line, 78)),
    ];
    const pdfBytes = createMinimalPdf(lines);
    return new Response(Buffer.from(pdfBytes), {
      status: 200,
      headers: {
        "content-type": "application/pdf",
        "content-disposition": `attachment; filename="${baseName}.pdf"`,
        "cache-control": "no-store",
      },
    });
  }

  if (format === "docx") {
    const paragraphs = [
      `AnonReq Pilot Sample — ${copy.label}`,
      `Persona: ${copy.persona}`,
      ...copy.prompt.split(/\n+/),
    ];
    const docxBytes = createMinimalDocx(paragraphs);
    return new Response(Buffer.from(docxBytes), {
      status: 200,
      headers: {
        "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "content-disposition": `attachment; filename="${baseName}.docx"`,
        "cache-control": "no-store",
      },
    });
  }

  if (format === "json") {
    const payload = JSON.stringify(
      {
        case_id: `DEMO-${scenario.id.toUpperCase()}-2026`,
        category: scenario.badge,
        locale: scenario.recommendedLocale,
        persona: copy.persona,
        content: copy.prompt,
      },
      null,
      2,
    );
    return new Response(payload, {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "content-disposition": `attachment; filename="${baseName}.json"`,
        "cache-control": "no-store",
      },
    });
  }

  if (format === "csv") {
    const escaped = copy.prompt.replace(/"/g, '""');
    const csv = `case_id,category,locale,content\n"DEMO-${scenario.id.toUpperCase()}-01","${scenario.badge}","${scenario.recommendedLocale}","${escaped}"\n`;
    return new Response(csv, {
      status: 200,
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": `attachment; filename="${baseName}.csv"`,
        "cache-control": "no-store",
      },
    });
  }

  return new Response(`${copy.prompt}\n`, {
    status: 200,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "content-disposition": `attachment; filename="${baseName}.txt"`,
      "cache-control": "no-store",
    },
  });
}

function wrapLine(text: string, maxLen: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    if (!current) {
      current = word;
    } else if (current.length + 1 + word.length <= maxLen) {
      current += ` ${word}`;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) {
    lines.push(current);
  }
  return lines;
}

