"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { GlassFlowBundle } from "@/lib/glassflow";

interface SponsorPilotPanelProps {
  uiLocale: string;
  bundle: GlassFlowBundle | null;
  onExportCsv: () => void;
  exportingCsv: boolean;
}

type ActiveTab = "glassflow" | "pilot" | "script";

export function SponsorPilotPanel({
  uiLocale,
  bundle,
  onExportCsv,
  exportingCsv,
}: SponsorPilotPanelProps) {
  const isDe = uiLocale === "de";
  const [tab, setTab] = useState<ActiveTab>("glassflow");
  const [gfView, setGfView] = useState<"rius" | "tares">("rius");
  const [pushState, setPushState] = useState<{
    status: "idle" | "sending" | "done" | "error";
    detail?: string;
  }>({ status: "idle" });

  async function emitToGlassFlow() {
    if (!bundle) return;
    setPushState({ status: "sending" });
    try {
      const res = await fetch("/api/glassflow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bundle),
      });
      const data = (await res.json().catch(() => null)) as {
        mode?: string;
        riusDelivered?: boolean;
        taresDelivered?: boolean;
      } | null;
      if (!res.ok) {
        setPushState({
          status: "error",
          detail: isDe ? "Senden fehlgeschlagen" : "Telemetry emit failed",
        });
        return;
      }
      if (data?.mode === "live_webhook") {
        setPushState({
          status: "done",
          detail: isDe
            ? `Live gesendet (Rius: ${data.riusDelivered ? "OK" : "—"}, Tares: ${data.taresDelivered ? "OK" : "—"})`
            : `Delivered live (Rius: ${data.riusDelivered ? "OK" : "—"}, Tares: ${data.taresDelivered ? "OK" : "—"})`,
        });
      } else {
        setPushState({
          status: "done",
          detail: isDe
            ? "Lokal validiert (setze GLASSFLOW_RIUS_OTLP_ENDPOINT oder GLASSFLOW_TARES_WEBHOOK_URL in .env für Live-Push)"
            : "Validated locally (set GLASSFLOW_RIUS_OTLP_ENDPOINT or GLASSFLOW_TARES_WEBHOOK_URL in .env for live push)",
        });
      }
    } catch {
      setPushState({
        status: "error",
        detail: isDe ? "Netzwerkfehler" : "Network error",
      });
    }
  }

  return (
    <section
      aria-labelledby="sponsor-pilot-heading"
      className="mt-8 rounded-xl border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-[#9a3412]">
            Frankfurt AI Week · Build Days @ The Squaire
          </p>
          <h2 id="sponsor-pilot-heading" className="mt-1 font-serif text-2xl">
            {isDe
              ? "GlassFlow-Integration · Pilot-PoC · 90s-Demo-Leitfaden"
              : "GlassFlow Integration · Pilot PoC · 90s Demo Guide"}
          </h2>
        </div>
        <div role="tablist" className="flex flex-wrap gap-1.5">
          <TabButton active={tab === "glassflow"} onClick={() => setTab("glassflow")}>
            {isDe ? "1. GlassFlow (Rius & Tares)" : "1. GlassFlow (Rius & Tares)"}
          </TabButton>
          <TabButton active={tab === "pilot"} onClick={() => setTab("pilot")}>
            {isDe ? "2. Pilot- & DPO-Übergabe" : "2. Pilot & DPO Handshake"}
          </TabButton>
          <TabButton active={tab === "script"} onClick={() => setTab("script")}>
            {isDe ? "3. 90s-Pitch & Fail-Closed" : "3. 90s Pitch & Fail-Closed"}
          </TabButton>
        </div>
      </div>

      {tab === "glassflow" ? (
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-secondary/30 p-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-serif text-lg">GlassFlow Rius (OTEL Observability)</h3>
                <Badge className="bg-[#b7e0d6] text-[#1a1814]">Zero-PII Traces</Badge>
              </div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                {isDe
                  ? "Wie Rius AnonReq hilft: Normale LLM-Tracing-Tools loggen versehentlich Klartext-IBANs im Prompt. AnonReq sendet OTLP-Spans mit Entitätszählern, Klassifizierung, Latenz und Fail-Closed-Status an Rius — so finden Coding-Agents Fehler ohne DSGVO-Verstoß."
                  : "How Rius helps AnonReq: Standard LLM tracing accidentally logs raw IBANs in prompts. AnonReq emits OTLP spans with entity counts, classification, latency, and fail-closed status into Rius — so debugging agents diagnose issues with zero GDPR leakage."}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-secondary/30 p-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-serif text-lg">GlassFlow Tares (Context & Triggers)</h3>
                <Badge className="bg-[#f3d7a1] text-[#1a1814]">Sanitized Timeline</Badge>
              </div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                {isDe
                  ? "Wie Tares AnonReq hilft: Tares korreliert Events (Tickets, Schäden, KRITIS-Meldungen) pro Fall-ID und weckt Agenten. Mit AnonReq davor speichert Tares nur tokenisierte Kontexte ([IBAN_DE_1], [KVNR_1]) und prüft agent_wake_allowed."
                  : "How Tares helps AnonReq: Tares correlates multi-source events (tickets, claims, grid logs) into per-entity timelines and wakes agents. With AnonReq in front, Tares stores pre-tokenized context ([IBAN_DE_1], [KVNR_1]) and enforces agent_wake_allowed."}
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-[#1a1814] p-4 text-[#f6f1e8]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setGfView("rius")}
                  className={`rounded px-2.5 py-1 font-mono text-xs ${
                    gfView === "rius" ? "bg-[#e7a07a] text-[#1a1814] font-semibold" : "bg-[#2a2622] text-[#d9d0c3]"
                  }`}
                >
                  Rius OTLP Trace (3 Spans)
                </button>
                <button
                  type="button"
                  onClick={() => setGfView("tares")}
                  className={`rounded px-2.5 py-1 font-mono text-xs ${
                    gfView === "tares" ? "bg-[#e7a07a] text-[#1a1814] font-semibold" : "bg-[#2a2622] text-[#d9d0c3]"
                  }`}
                >
                  Tares Correlated Event (CloudEvent 1.0)
                </button>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={!bundle || pushState.status === "sending"}
                  onClick={() => void emitToGlassFlow()}
                >
                  {pushState.status === "sending"
                    ? isDe
                      ? "Sende…"
                      : "Emitting…"
                    : isDe
                      ? "An GlassFlow senden"
                      : "Emit to GlassFlow"}
                </Button>
              </div>
            </div>
            {pushState.detail ? (
              <p className="mt-2 font-mono text-xs text-[#b7e0d6]">{pushState.detail}</p>
            ) : null}
            {bundle ? (
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-[#12110e] p-3 font-mono text-xs leading-5 text-[#f3efe6]">
                {JSON.stringify(gfView === "rius" ? bundle.rius : bundle.tares, null, 2)}
              </pre>
            ) : (
              <p className="mt-3 font-mono text-xs text-[#d9d0c3]">
                {isDe
                  ? "Führe oben »Nur prüfen« oder »Anonymisieren & Grok fragen« aus, um den Live-Rius-Trace und das Tares-Event zu erzeugen."
                  : "Run 'Scan Only' or 'Anonymize & Ask Grok' above to generate the live Rius OTLP trace and Tares event."}
              </p>
            )}
          </div>
        </div>
      ) : null}

      {tab === "pilot" ? (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-border bg-secondary/20 p-4">
            <p className="font-mono text-xs uppercase text-[#9a3412]">
              {isDe ? "Schritt 1 · Bereitstellung" : "Step 1 · Deployment"}
            </p>
            <h3 className="mt-1 font-serif text-lg">
              {isDe ? "In 15 Min. vor Ihrem Modell-Key" : "15-Min Drop-In Gateway"}
            </h3>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {isDe
                ? "Läuft als Docker Compose oder Helm-Chart in Ihrem eigenen Cluster/VPC. OpenAI-kompatibler Endpunkt (/v1/chat/completions) vor xAI Grok, OpenAI, Claude oder Gemini."
                : "Runs via Docker Compose or Helm in your VPC/cluster. OpenAI-compatible endpoint (/v1/chat/completions) in front of your own xAI Grok, OpenAI, Claude, or Gemini key."}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-secondary/20 p-4">
            <p className="font-mono text-xs uppercase text-[#9a3412]">
              {isDe ? "Schritt 2 · DPO & Betriebsrat" : "Step 2 · DPO & Works Council"}
            </p>
            <h3 className="mt-1 font-serif text-lg">
              {isDe ? "Metadaten-Audit ohne Roh-PII" : "Metadata-Only Audit Trail"}
            </h3>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {isDe
                ? "Das Audit-Log speichert Request-ID, Zeitstempel, Modell, Locale und Entitätstypen (z. B. IBAN_DE, KVNR) mit SHA-256-Hash-Kette — niemals den Klartext."
                : "Audit log records request ID, timestamp, model, locale, and entity types (e.g. IBAN_DE, KVNR) with a SHA-256 hash chain — never raw values."}
            </p>
            <div className="mt-3">
              <Button type="button" size="sm" variant="outline" onClick={onExportCsv} disabled={exportingCsv}>
                {exportingCsv
                  ? isDe
                    ? "Export läuft…"
                    : "Exporting…"
                  : isDe
                    ? "DPO-Audit-CSV herunterladen"
                    : "Download DPO Audit CSV"}
              </Button>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-secondary/20 p-4">
            <p className="font-mono text-xs uppercase text-[#9a3412]">
              {isDe ? "Schritt 3 · Frankfurt Pilot-PoC" : "Step 3 · Frankfurt Pilot PoC"}
            </p>
            <h3 className="mt-1 font-serif text-lg">
              {isDe ? "Eigenes Dokument live testen" : "Test Your Own Sample Document"}
            </h3>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {isDe
                ? "Laden Sie oben ein synthetisches Ticket (.pdf, .docx, .csv, .txt) hoch: Prüfen Sie sofort, welche Entitäten erkannt werden, und laden Sie die bereinigte Datei herunter."
                : "Upload a synthetic ticket (.pdf, .docx, .csv, .txt) above: see every detected span, verify non-reversible secret masking, and download the sanitized file."}
            </p>
          </div>
        </div>
      ) : null}

      {tab === "script" ? (
        <div className="mt-4 space-y-3 text-xs leading-5">
          <div className="grid gap-3 md:grid-cols-5">
            <ScriptStep
              time="0–10s"
              title={isDe ? "1. Hook" : "1. Hook"}
              body={
                isDe
                  ? "»EU-Teams wollen Grok und ChatGPT auf Bank-Tickets und Schäden nutzen — Compliance sagt Nein. AnonReq sitzt davor und blockiert Fail-Closed.«"
                  : "'EU teams want Grok and ChatGPT on bank tickets & claims — compliance says no. AnonReq sits in front and fails closed.'"
              }
            />
            <ScriptStep
              time="10–35s"
              title={isDe ? "2. Datei-Check" : "2. File Check"}
              body={
                isDe
                  ? "Kfz-Schaden oder Bank-Ticket (.pdf / .docx) hochladen → »Nur prüfen« klicken. Das Urteil zeigt sofort: Unsicher im Klartext → Sicher über AnonReq."
                  : "Upload a claim or bank ticket (.pdf / .docx) → click 'Scan Only'. The Verdict banner immediately shows: Unsafe in Cleartext → Safe via AnonReq."
              }
            />
            <ScriptStep
              time="35–55s"
              title={isDe ? "3. Grok + Restore" : "3. Grok + Restore"}
              body={
                isDe
                  ? "»Anonymisieren & Grok fragen« klicken. Spalte 2 zeigt [IBAN_DE_1], Spalte 3 zeigt die re-identifizierte Antwort von xAI Grok (API-Keys bleiben maskiert!)."
                  : "Click 'Anonymize & Ask Grok'. Column 2 shows [IBAN_DE_1] leaving the boundary; Column 3 shows xAI Grok's restored reply (while API_KEY stays masked!)."
              }
            />
            <ScriptStep
              time="55–75s"
              title={isDe ? "4. GlassFlow" : "4. GlassFlow"}
              body={
                isDe
                  ? "Tab »GlassFlow« zeigen: OTLP-Trace für Rius (0 Klartext-PII) und korreliertes Tares-Event für Agent-Workflows."
                  : "Show the GlassFlow tab: zero-PII OTLP trace for Rius observability + sanitized CloudEvent for Tares agent timelines."
              }
            />
            <ScriptStep
              time="75–90s"
              title={isDe ? "5. Fail-Closed & CSV" : "5. Fail-Closed & CSV"}
              body={
                isDe
                  ? "DPO-CSV exportieren (nur Entitätstypen). Optional Presidio stoppen → HTTP 503 Fail-Closed: »Wir leiten niemals Klartext weiter.«"
                  : "Export DPO CSV (entity types only). Optionally stop Presidio → HTTP 503 Fail-Closed: 'We never forward cleartext.'"
              }
            />
          </div>
          <div className="rounded-lg border border-border bg-[#1a1814] p-3 font-mono text-xs text-[#f3efe6]">
            <p className="text-[#e7a07a]">
              {isDe
                ? "# Live Fail-Closed-Beweis im Terminal (Presidio kurz pausieren → 503 zeigen → wieder starten):"
                : "# Live Fail-Closed proof in terminal (pause Presidio → show HTTP 503 block → unpause):"}
            </p>
            <p className="mt-1">
              docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml stop presidio-analyzer
            </p>
            <p className="mt-1 text-[#b7e0d6]">
              docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml start presidio-analyzer
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
        active
          ? "bg-[#1a1814] text-[#f6f1e8]"
          : "bg-secondary text-foreground hover:bg-secondary/80"
      }`}
    >
      {children}
    </button>
  );
}

function ScriptStep({ time, title, body }: { time: string; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-border bg-secondary/20 p-3">
      <span className="font-mono text-[11px] font-semibold text-[#9a3412]">{time}</span>
      <p className="mt-0.5 font-serif text-base">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{body}</p>
    </div>
  );
}

