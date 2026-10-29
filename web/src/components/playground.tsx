"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent, type ReactNode } from "react";
import { EntityText } from "@/components/entity-text";
import { SponsorPilotPanel } from "@/components/sponsor-pilot-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ExtractedFileResult } from "@/lib/file-extract";
import { buildGlassFlowBundle, type GlassFlowBundle } from "@/lib/glassflow";
import { buildAnswerHighlights } from "@/lib/redact";
import {
  BUYER_SCENARIOS,
  TASK_PRESETS,
  evaluateComplianceVerdict,
  type ComplianceVerdict,
  type ScenarioId,
  type TaskPresetId,
} from "@/lib/scenarios";
import { LEGEND_TYPES, entityClassName, type HighlightSpan } from "@/lib/segments";
import type { AnonymizePreviewResponse, ChatCompletionResult } from "@/lib/types";

const DETECTION_LOCALES = [
  ["de-DE", "Deutsch"],
  ["en", "English"],
  ["fr-FR", "Français"],
  ["es", "Español"],
  ["it-IT", "Italiano"],
  ["nl-NL", "Nederlands"],
  ["pt-BR", "Português"],
  ["ar", "العربية"],
] as const;

type PreviewPayload =
  | { ok: true; data: AnonymizePreviewResponse }
  | { ok: false; reason: "disabled" | "rate_limited" | "invalid" | "error"; status: number; message: string };

type Phase = "idle" | "running" | "done";
type RunMode = "scan_only" | "full_chat";

export function Playground() {
  const t = useTranslations("playground");
  const headers = useTranslations("headers");
  const uiLocale = useLocale();
  const isDe = uiLocale === "de";

  const initialScenario = BUYER_SCENARIOS[0];
  const [selectedScenarioId, setSelectedScenarioId] = useState<ScenarioId>(initialScenario.id);
  const [prompt, setPrompt] = useState(isDe ? initialScenario.de.prompt : initialScenario.en.prompt);
  const [taskPreset, setTaskPreset] = useState<TaskPresetId>("as_is");
  const [model, setModel] = useState("grok-4");
  const [pinnedTenant, setPinnedTenant] = useState("default");
  const [detectionLocale, setDetectionLocale] = useState("de-DE");
  const [models, setModels] = useState<string[]>(["grok-4", "grok", "grok-3"]);

  const [phase, setPhase] = useState<Phase>("idle");
  const [runMode, setRunMode] = useState<RunMode>("full_chat");
  const [submitted, setSubmitted] = useState("");
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [chat, setChat] = useState<ChatCompletionResult | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [lastErrorStatus, setLastErrorStatus] = useState<number | null>(null);

  // File upload state
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<ExtractedFileResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // Session counters & GlassFlow bundle
  const [sessionStats, setSessionStats] = useState({ runs: 0, entities: 0, secrets: 0 });
  const [glassflowBundle, setGlassflowBundle] = useState<GlassFlowBundle | null>(null);
  const [copiedSanitized, setCopiedSanitized] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/models")
      .then((response) => response.json())
      .then((body: { models?: string[] }) => {
        if (!cancelled && Array.isArray(body.models) && body.models.length > 0) {
          setModels(body.models);
        }
      })
      .catch(() => undefined);
    fetch("/api/status")
      .then((response) => response.json())
      .then((body: { defaultTenant?: string }) => {
        if (!cancelled && typeof body.defaultTenant === "string" && body.defaultTenant) {
          setPinnedTenant(body.defaultTenant);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const currentScenario =
    BUYER_SCENARIOS.find((item) => item.id === selectedScenarioId) ?? BUYER_SCENARIOS[0];
  const scenarioCopy = isDe ? currentScenario.de : currentScenario.en;

  function selectScenario(id: ScenarioId) {
    const found = BUYER_SCENARIOS.find((item) => item.id === id);
    if (!found) return;
    setSelectedScenarioId(id);
    setDetectionLocale(found.recommendedLocale);
    setPrompt(isDe ? found.de.prompt : found.en.prompt);
    setUploadedFile(null);
    setUploadError(null);
  }

  async function handleFileSelected(file: File) {
    setUploadingFile(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch("/api/extract", {
        method: "POST",
        body: formData,
      });
      const body = (await response.json().catch(() => null)) as
        | (ExtractedFileResult & { error?: { message?: string } })
        | null;
      if (!response.ok || !body || typeof body.text !== "string") {
        setUploadError(body?.error?.message ?? "Could not extract text from file");
        return;
      }
      setUploadedFile(body);
      setPrompt(body.text);
      // Automatically trigger a "Scan Only" check so the user immediately sees if the uploaded file is OK!
      await executePipeline("scan_only", body.text, body.filename);
    } catch {
      setUploadError(t("network"));
    } finally {
      setUploadingFile(false);
    }
  }

  function onFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      void handleFileSelected(file);
    }
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      void handleFileSelected(file);
    }
  }

  async function executePipeline(mode: RunMode, overridePrompt?: string, overrideFilename?: string | null) {
    const rawPrompt = overridePrompt ?? prompt;
    if (!rawPrompt.trim()) return;

    const presetPrefix =
      mode === "full_chat" && taskPreset !== "as_is"
        ? isDe
          ? TASK_PRESETS[taskPreset].de.prefix
          : TASK_PRESETS[taskPreset].en.prefix
        : "";
    const effectiveChatPrompt = `${presetPrefix}${rawPrompt}`.slice(0, 8000);

    const startTime = performance.now();
    setPhase("running");
    setRunMode(mode);
    setSubmitted(rawPrompt);
    setPreview(null);
    setChat(null);
    setChatError(null);
    setLastErrorStatus(null);

    const previewPayload = {
      prompt: rawPrompt,
      model,
      locale: detectionLocale,
    };
    const chatPayload = {
      prompt: effectiveChatPrompt,
      model,
      locale: detectionLocale,
    };

    const [previewResult, chatResult] = await Promise.all([
      postJson("/api/preview", previewPayload),
      mode === "full_chat" ? postJson("/api/chat", chatPayload) : Promise.resolve(null),
    ]);

    let resolvedPreviewData: AnonymizePreviewResponse | null = null;
    let resolvedChat: ChatCompletionResult | null = null;
    let errorStatus: number | null = null;

    if (!previewResult.ok && previewResult.message === "network") {
      setPreview({ ok: false, reason: "error", status: 0, message: t("network") });
      errorStatus = 503;
    } else if (!previewResult.ok) {
      setPreview({
        ok: false,
        reason: "error",
        status: previewResult.status,
        message: messageFrom(previewResult.body) ?? t("previewError"),
      });
      errorStatus = previewResult.status;
    } else if (isPreviewPayload(previewResult.body)) {
      setPreview(previewResult.body);
      if (previewResult.body.ok) {
        resolvedPreviewData = previewResult.body.data;
      } else if (previewResult.body.status >= 500) {
        errorStatus = previewResult.body.status;
      }
    } else {
      setPreview({
        ok: false,
        reason: "error",
        status: previewResult.status,
        message: messageFrom(previewResult.body) ?? t("previewError"),
      });
      errorStatus = previewResult.status;
    }

    if (mode === "full_chat" && chatResult) {
      if (!chatResult.ok) {
        setChatError(
          chatResult.message === "network" ? t("network") : (messageFrom(chatResult.body) ?? t("chatError")),
        );
        if (chatResult.status >= 500 || chatResult.message === "network") {
          errorStatus = chatResult.status || 503;
        }
      } else if (isChatResult(chatResult.body)) {
        resolvedChat = chatResult.body;
        setChat(chatResult.body);
      } else {
        setChatError(t("chatError"));
      }
    }

    setLastErrorStatus(errorStatus);
    setPhase("done");

    const latencyMs = Math.round(performance.now() - startTime);
    const entities = resolvedPreviewData?.entities ?? [];
    const secretCount = entities.filter(
      (e) => e.entity_type === "API_KEY" || e.entity_type === "SECRET",
    ).length;

    setSessionStats((prev) => ({
      runs: prev.runs + 1,
      entities: prev.entities + entities.length,
      secrets: prev.secrets + secretCount,
    }));

    setGlassflowBundle(
      buildGlassFlowBundle({
        mode,
        scenarioId: selectedScenarioId,
        filename: overrideFilename !== undefined ? overrideFilename : (uploadedFile?.filename ?? null),
        tenantId: pinnedTenant || "default",
        locale: detectionLocale,
        model,
        latencyMs,
        preview: resolvedPreviewData,
        chat: resolvedChat,
        errorStatus,
      }),
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await executePipeline("full_chat");
  }

  async function handleExportDpoCsv() {
    setExportingCsv(true);
    try {
      const response = await fetch("/api/audit/export?sort=timestamp:desc&limit=50");
      if (!response.ok) return;
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "dpo-anonymization-audit.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } finally {
      setExportingCsv(false);
    }
  }

  function downloadSanitizedText(text: string) {
    const base = uploadedFile?.filename
      ? uploadedFile.filename.replace(/\.[^.]+$/, "")
      : currentScenario.sampleFilename;
    const blob = new Blob([`${text}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${base}.sanitized.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function copySanitizedText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSanitized(true);
      setTimeout(() => setCopiedSanitized(false), 1800);
    } catch {
      // ignore clipboard errors
    }
  }

  const previewData = preview?.ok ? preview.data : null;
  const promptEntities = (previewData?.entities ?? []).filter((entity) => entity.message_index == null);
  const rawSpans: HighlightSpan[] = promptEntities.map((entity) => ({
    start: entity.start_utf16,
    end: entity.end_utf16,
    entityType: entity.entity_type,
    token: entity.token,
  }));
  const anonymizedText = previewData?.anonymized_text ?? "";
  const anonSpans: HighlightSpan[] = promptEntities.map((entity) => ({
    start: entity.token_start_utf16,
    end: entity.token_end_utf16,
    entityType: entity.entity_type,
    token: entity.token,
  }));

  const answerPair =
    chat != null
      ? buildAnswerHighlights(chat.answer, chat.rawAnswer, promptEntities)
      : null;

  const verdict: ComplianceVerdict | null =
    phase === "done" && (previewData || lastErrorStatus)
      ? evaluateComplianceVerdict(previewData, lastErrorStatus)
      : null;

  return (
    <div className="mt-6">
      <p className="sr-only" aria-live="polite">
        {phase === "running" ? t("sending") : phase === "done" ? t("done") : ""}
      </p>

      {/* Live Session Stats + Quick DPO CSV Export */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-[#1a1814] px-4 py-3 text-[#f6f1e8]">
        <div className="flex flex-wrap items-center gap-5 text-xs">
          <div>
            <span className="font-mono uppercase text-[#d9d0c3]">{t("sessionRequests")}: </span>
            <span className="font-mono text-sm font-semibold text-[#f6f1e8]">{sessionStats.runs}</span>
          </div>
          <div>
            <span className="font-mono uppercase text-[#d9d0c3]">{t("sessionEntities")}: </span>
            <span className="font-mono text-sm font-semibold text-[#f3d7a1]">{sessionStats.entities}</span>
          </div>
          <div>
            <span className="font-mono uppercase text-[#d9d0c3]">{t("sessionSecrets")}: </span>
            <span className="font-mono text-sm font-semibold text-[#fca5a5]">{sessionStats.secrets}</span>
          </div>
          <Badge className="bg-[#b7e0d6] text-[#1a1814] font-mono">
            {detectionLocale} · Fail-Closed
          </Badge>
        </div>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => void handleExportDpoCsv()}
          disabled={exportingCsv}
        >
          {exportingCsv ? "…" : t("exportDpoCsv")}
        </Button>
      </div>

      {/* 5 EU Buyer Scenarios + Clean Baseline */}
      <section aria-labelledby="scenarios-heading" className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="scenarios-heading" className="font-serif text-xl">
            {t("scenariosTitle")}
          </h2>
          <p className="text-xs text-muted-foreground">{t("scenariosHint")}</p>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {BUYER_SCENARIOS.map((scenario) => {
            const label = isDe ? scenario.de.label : scenario.en.label;
            const active = scenario.id === selectedScenarioId && !uploadedFile;
            return (
              <button
                key={scenario.id}
                type="button"
                onClick={() => selectScenario(scenario.id)}
                className={`rounded-lg border px-3 py-1.5 text-left text-xs font-medium transition-colors ${
                  active
                    ? "border-[#9a3412] bg-[#1a1814] text-[#f6f1e8]"
                    : "border-border bg-secondary/50 text-foreground hover:bg-secondary"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Active Scenario Buyer Context Strip */}
        <div className="mt-3 grid gap-3 rounded-lg border border-border bg-secondary/25 p-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="font-mono text-[11px] uppercase text-[#9a3412]">{t("personaLabel")}</p>
            <p className="mt-0.5 font-medium">{scenarioCopy.persona}</p>
          </div>
          <div>
            <p className="font-mono text-[11px] uppercase text-[#9a3412]">{t("painLabel")}</p>
            <p className="mt-0.5 text-muted-foreground">{scenarioCopy.pain}</p>
          </div>
          <div>
            <p className="font-mono text-[11px] uppercase text-[#9a3412]">{t("valueLabel")}</p>
            <p className="mt-0.5 text-muted-foreground">{scenarioCopy.value}</p>
          </div>
          <div>
            <p className="font-mono text-[11px] uppercase text-[#9a3412]">{t("buyerLineLabel")}</p>
            <p className="mt-0.5 font-serif text-sm font-medium text-foreground">“{scenarioCopy.buyerLine}”</p>
          </div>
        </div>

        {/* Downloadable Sample Files for Live Upload Testing */}
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">{t("downloadSample")}</span>
          {(["pdf", "docx", "txt", "json", "csv"] as const).map((fmt) => (
            <a
              key={fmt}
              href={`/api/sample-file?scenario=${selectedScenarioId}&format=${fmt}&lang=${isDe ? "de" : "en"}`}
              download
              className="rounded border border-border bg-card px-2 py-0.5 font-mono text-[11px] uppercase hover:bg-secondary"
            >
              .{fmt}
            </a>
          ))}
        </div>
      </section>

      {/* File Upload Dropzone + Prompt Form */}
      <form onSubmit={onSubmit} className="mt-4 rounded-xl border border-border bg-card p-4 shadow-sm">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
          className={`rounded-lg border-2 border-dashed p-3 transition-colors ${
            dragActive ? "border-[#9a3412] bg-[#fbf6ef]" : "border-border bg-secondary/20"
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">{t("uploadTitle")}</p>
              <p className="text-xs text-muted-foreground">
                {uploadingFile ? t("uploading") : t("uploadSub")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.markdown,.csv,.tsv,.json,.log,.eml,.pdf,.docx"
                onChange={onFileInputChange}
                className="sr-only"
                aria-label={t("uploadTitle")}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={uploadingFile}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploadingFile ? t("uploading") : t("uploadDrop")}
              </Button>
              {uploadedFile ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setUploadedFile(null);
                    setUploadError(null);
                  }}
                >
                  {t("clearFile")}
                </Button>
              ) : null}
            </div>
          </div>

          {uploadedFile ? (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
              <Badge className="bg-[#b7e0d6] text-[#1a1814] font-mono">
                {t("uploadedBadge")}: {uploadedFile.filename}
              </Badge>
              <span className="font-mono text-muted-foreground">
                {uploadedFile.format.toUpperCase()} · {uploadedFile.byteSize.toLocaleString()} bytes ·{" "}
                {uploadedFile.charCount.toLocaleString()} chars
                {uploadedFile.truncated ? " (truncated to 7,200 chars)" : ""}
              </span>
            </div>
          ) : null}

          {uploadError ? (
            <p role="alert" className="mt-2 text-xs font-medium text-[#991b1b]">
              {uploadError}
            </p>
          ) : null}
        </div>

        <div className="mt-4">
          <Label htmlFor="prompt">{t("prompt")}</Label>
          <Textarea
            id="prompt"
            name="prompt"
            required
            maxLength={8000}
            spellCheck={false}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            aria-describedby="prompt-hint"
            className="mt-1.5 min-h-32 font-mono text-sm"
          />
          <p id="prompt-hint" className="mt-1 text-xs text-muted-foreground">
            {t("shortcut")}
          </p>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Label htmlFor="task-preset">{t("taskLabel")}</Label>
            <select
              id="task-preset"
              value={taskPreset}
              onChange={(event) => setTaskPreset(event.target.value as TaskPresetId)}
              className="mt-1.5 flex h-10 w-full rounded-md border border-input bg-card px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {(Object.keys(TASK_PRESETS) as TaskPresetId[]).map((key) => (
                <option key={key} value={key}>
                  {isDe ? TASK_PRESETS[key].de.label : TASK_PRESETS[key].en.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="model">{t("model")}</Label>
            <Input
              id="model"
              name="model"
              list="model-aliases"
              required
              value={model}
              onChange={(event) => setModel(event.target.value)}
              className="mt-1.5 font-mono"
              aria-describedby="model-hint"
              autoComplete="off"
            />
            <datalist id="model-aliases">
              {models.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
            <p id="model-hint" className="mt-1 text-xs text-muted-foreground">
              {t("modelHelp")}
            </p>
          </div>
          <div>
            <Label htmlFor="pinned-tenant">{t("pinnedTenant")}</Label>
            <p id="pinned-tenant" className="mt-1.5 font-mono text-sm">
              {pinnedTenant || "…"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{t("pinnedTenantHelp")}</p>
          </div>
          <div>
            <Label htmlFor="detection-locale">{t("locale")}</Label>
            <select
              id="detection-locale"
              name="locale"
              value={detectionLocale}
              onChange={(event) => setDetectionLocale(event.target.value)}
              aria-describedby="locale-hint"
              className="mt-1.5 flex h-10 w-full rounded-md border border-input bg-card px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {DETECTION_LOCALES.map(([code, label]) => (
                <option key={code} value={code}>
                  {label} ({code})
                </option>
              ))}
            </select>
            <p id="locale-hint" className="mt-1 text-xs text-muted-foreground">
              {t("localeHelp")}
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            disabled={phase === "running" || !prompt.trim()}
            onClick={() => void executePipeline("scan_only")}
          >
            {phase === "running" && runMode === "scan_only" ? t("scanning") : t("scanOnly")}
          </Button>
          <Button type="submit" disabled={phase === "running" || !prompt.trim()}>
            {phase === "running" && runMode === "full_chat" ? t("sending") : t("sendWithGrok")}
          </Button>
        </div>
      </form>

      {/* "Is This File / Prompt OK?" Compliance Verdict Card */}
      {verdict ? (
        <section
          aria-labelledby="verdict-title"
          className={`mt-6 rounded-xl border-2 p-4 shadow-sm ${
            verdict.state === "clean"
              ? "border-[#166534]/40 bg-[#f0fdf4]"
              : verdict.state === "governed"
                ? "border-[#9a3412]/50 bg-[#fbf6ef]"
                : "border-[#991b1b]/60 bg-[#fef2f2]"
          }`}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <p className="font-mono text-xs uppercase tracking-wider text-[#9a3412]">
                {t("verdictHeading")}
              </p>
              <h2 id="verdict-title" className="mt-1 font-serif text-2xl">
                {verdict.state === "clean"
                  ? t("verdictCleanTitle")
                  : verdict.state === "governed"
                    ? t("verdictGovernedTitle")
                    : verdict.state === "credential_risk"
                      ? t("verdictSecretTitle")
                      : t("verdictFailClosedTitle")}
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {verdict.state === "clean"
                  ? t("verdictCleanBody")
                  : verdict.state === "governed"
                    ? t("verdictGovernedBody", {
                        count: verdict.totalEntities,
                        classification: verdict.classification,
                      })
                    : verdict.state === "credential_risk"
                      ? t("verdictSecretBody", {
                          secretCount: verdict.nonReversibleCount,
                          total: verdict.totalEntities,
                        })
                      : t("verdictFailClosedBody")}
              </p>
            </div>

            {/* Side-by-side Gate Comparison Badges */}
            <div className="flex flex-wrap gap-2 text-xs">
              <div className="rounded-lg border border-border bg-card px-3 py-2">
                <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("cleartextStatus")}</p>
                <p
                  className={`mt-1 font-mono font-semibold ${
                    verdict.okForCleartextAi ? "text-[#166534]" : "text-[#991b1b]"
                  }`}
                >
                  {verdict.okForCleartextAi ? t("cleartextSafe") : t("cleartextUnsafe")}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-card px-3 py-2">
                <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("gatewayStatus")}</p>
                <p
                  className={`mt-1 font-mono font-semibold ${
                    verdict.okViaAnonReq ? "text-[#166534]" : "text-[#991b1b]"
                  }`}
                >
                  {verdict.okViaAnonReq ? t("gatewaySafe") : t("gatewayBlocked")}
                </p>
              </div>
            </div>
          </div>

          {/* Detected Entity Summary + Download/Copy Sanitized Buttons */}
          {verdict.groups.length > 0 ? (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-3">
              <div className="flex flex-wrap gap-2">
                {verdict.groups.map((group) => (
                  <Badge
                    key={group.entityType}
                    className={`${entityClassName(group.entityType)} flex items-center gap-1.5 px-2.5 py-1 text-xs`}
                  >
                    <span className="font-mono font-semibold">
                      {group.entityType} × {group.count}
                    </span>
                    <span className="rounded bg-black/10 px-1.5 py-0.5 font-mono text-[10px] font-medium">
                      {group.reversible ? t("reversibleBadge") : t("nonReversibleBadge")}
                    </span>
                  </Badge>
                ))}
              </div>
              {anonymizedText ? (
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => void copySanitizedText(anonymizedText)}
                  >
                    {copiedSanitized ? t("copied") : t("copySanitized")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => downloadSanitizedText(anonymizedText)}
                  >
                    {t("downloadSanitized")}
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* Four Columns: 01 Raw · 02 Anonymized · 03 Raw Model Reply · 04 Re-identified Answer */}
      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-busy={phase === "running"}>
        <Column step="01" title={t("rawTitle")} hint={t("rawHint")}>
          {phase === "idle" ? <p className="text-sm text-muted-foreground">{t("empty")}</p> : null}
          {phase === "running" ? <Skeleton /> : null}
          {phase === "done" ? (
            <>
              {previewData ? (
                <EntityText text={submitted} spans={rawSpans} />
              ) : (
                <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] font-mono text-[13px] leading-6">
                  {submitted}
                </p>
              )}
              {preview && !preview.ok ? (
                <p className="mt-3 text-xs text-muted-foreground">{t("spansMissing")}</p>
              ) : null}
            </>
          ) : null}
        </Column>

        <Column step="02" title={t("anonTitle")} hint={t("anonHint")}>
          {phase === "idle" ? <p className="text-sm text-muted-foreground">{t("empty")}</p> : null}
          {phase === "running" ? <Skeleton /> : null}
          {phase === "done" && previewData ? (
            <>
              <EntityText text={anonymizedText} spans={anonSpans} />
              {previewData.entities.length === 0 ? (
                <p className="mt-3 text-xs text-muted-foreground">{t("noEntities")}</p>
              ) : null}
            </>
          ) : null}
          {phase === "done" && preview && !preview.ok && preview.reason === "disabled" ? (
            <div className="rounded-lg border border-dashed border-[#9a3412] bg-[#fbf6ef] p-4">
              <p className="font-serif text-lg leading-snug">{t("previewDisabledTitle")}</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("previewDisabledBody")}</p>
            </div>
          ) : null}
          {phase === "done" && preview && !preview.ok && preview.reason === "rate_limited" ? (
            <p role="alert" className="text-sm leading-6">
              {t("rateLimited")}
            </p>
          ) : null}
          {phase === "done" &&
          preview &&
          !preview.ok &&
          preview.reason !== "disabled" &&
          preview.reason !== "rate_limited" ? (
            <p role="alert" className="text-sm leading-6">
              {t("previewError")}: {preview.message}
            </p>
          ) : null}
        </Column>

        <Column step="03" title={t("modelRawTitle")} hint={t("modelRawHint")}>
          {phase === "idle" ? <p className="text-sm text-muted-foreground">{t("empty")}</p> : null}
          {phase === "running" && runMode === "full_chat" ? <Skeleton /> : null}
          {phase === "done" && runMode === "scan_only" ? (
            <div className="rounded-lg border border-dashed border-border bg-secondary/30 p-3 text-xs leading-5 text-muted-foreground">
              <p className="font-medium text-foreground">
                {isDe
                  ? "Nur Vorab-Prüfung ausgeführt (kein Modellaufruf)."
                  : "Pre-flight scan only (model not called)."}
              </p>
            </div>
          ) : null}
          {phase === "done" && answerPair ? (
            <EntityText text={answerPair.rawModelText} spans={answerPair.rawModelSpans} />
          ) : null}
          {phase === "done" && chatError ? (
            <p role="alert" className="text-sm leading-6">
              {t("chatError")}: {chatError}
            </p>
          ) : null}
        </Column>

        <Column step="04" title={t("answerTitle")} hint={t("answerHint")}>
          {phase === "idle" ? <p className="text-sm text-muted-foreground">{t("empty")}</p> : null}
          {phase === "running" && runMode === "full_chat" ? <Skeleton /> : null}
          {phase === "done" && runMode === "scan_only" ? (
            <div className="rounded-lg border border-dashed border-border bg-secondary/30 p-3 text-xs leading-5 text-muted-foreground">
              <p className="font-medium text-foreground">
                {isDe
                  ? "Nur Vorab-Prüfung ausgeführt (0 LLM-Tokens verbraucht)."
                  : "Pre-flight scan only (0 LLM tokens spent)."}
              </p>
              <p className="mt-1">
                {isDe
                  ? "Klicke auf »Anonymisieren & Grok fragen«, um den maskierten Text aus Spalte 02 an xAI Grok zu senden und Modellantwort (03) sowie Re-Identifizierung (04) zu sehen."
                  : "Click 'Anonymize & Ask Grok' to send the tokenized text from Column 02 to xAI Grok and see both the raw model reply (03) and restored answer (04)."}
              </p>
            </div>
          ) : null}
          {phase === "done" && chat && answerPair ? (
            <EntityText text={chat.answer} spans={answerPair.restoredSpans} />
          ) : null}
          {phase === "done" && chatError ? (
            <p role="alert" className="text-sm leading-6">
              {t("chatError")}: {chatError}
            </p>
          ) : null}
        </Column>
      </div>

      {/* Completion Response Headers */}
      <section aria-labelledby="headers-title" className="mt-6">
        <h2 id="headers-title" className="font-serif text-2xl">
          {t("headersTitle")}
        </h2>
        {chat ? (
          <>
            <dl className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <HeaderCell name={headers("requestId")} value={chat.headers.requestId} />
              <HeaderCell name={headers("entityCount")} value={chat.headers.entityCount} />
              <HeaderCell name={headers("classification")} value={chat.headers.classification} badge />
              <HeaderCell name={headers("highestEntity")} value={chat.headers.highestEntity} />
              <HeaderCell name={headers("processed")} value={chat.headers.processed} />
            </dl>
            {previewData ? (
              <p className="mt-3 font-mono text-xs text-muted-foreground">
                {t("previewRequestId")}: {previewData.request_id}. {t("separateCalls")}
              </p>
            ) : null}
          </>
        ) : previewData ? (
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <HeaderCell name="Preview Request ID" value={previewData.request_id} />
            <HeaderCell name={headers("entityCount")} value={String(previewData.entities.length)} />
            <HeaderCell name={headers("classification")} value={previewData.classification} badge />
            <HeaderCell name={headers("highestEntity")} value={previewData.highest_entity || "—"} />
          </dl>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">{t("headersEmpty")}</p>
        )}
      </section>

      {/* Entity Legend */}
      <ul aria-label={t("legend")} className="mt-4 flex flex-wrap gap-2">
        {LEGEND_TYPES.map((type) => (
          <li key={type}>
            <Badge className={entityClassName(type)}>
              <span aria-hidden className="mr-1 inline-block h-2 w-2 rounded-full bg-[#1a1814]/70" />
              {type}
            </Badge>
          </li>
        ))}
      </ul>

      {/* GlassFlow (Rius + Tares) & Pilot PoC Panel */}
      <SponsorPilotPanel
        uiLocale={uiLocale}
        bundle={glassflowBundle}
        onExportCsv={() => void handleExportDpoCsv()}
        exportingCsv={exportingCsv}
      />
    </div>
  );
}

function Column({
  step,
  title,
  hint,
  children,
}: {
  step: string;
  title: string;
  hint: string;
  children: ReactNode;
}) {
  const headingId = `column-${step}`;
  return (
    <section
      aria-labelledby={headingId}
      className="flex min-h-80 min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card p-4 shadow-sm"
    >
      <div className="border-b border-border/60 pb-3 xl:min-h-[6.75rem]">
        <p className="font-mono text-xs font-semibold text-[#9a3412]">{step}</p>
        <h2 id={headingId} className="mt-1 font-serif text-xl leading-snug">
          {title}
        </h2>
        <p className="mt-1 text-xs leading-4 text-muted-foreground">{hint}</p>
      </div>
      <div className="mt-3 min-w-0 flex-1 overflow-x-auto">{children}</div>
    </section>
  );
}

function HeaderCell({ name, value, badge = false }: { name: string; value: string | null; badge?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2">
      <dt className="break-all font-mono text-[11px] text-muted-foreground">{name}</dt>
      <dd className="mt-1 break-all font-mono text-sm">
        {value ? badge ? <Badge>{value}</Badge> : value : "—"}
      </dd>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      <div className="h-3 rounded bg-secondary" />
      <div className="h-3 w-11/12 rounded bg-secondary" />
      <div className="h-3 w-4/5 rounded bg-secondary" />
      <div className="h-3 w-2/3 rounded bg-secondary" />
    </div>
  );
}

async function postJson(
  url: string,
  payload: unknown,
): Promise<{ ok: boolean; status: number; body: unknown; message?: string }> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = (await response.json().catch(() => null)) as unknown;
    return { ok: response.ok, status: response.status, body };
  } catch {
    return { ok: false, status: 0, body: null, message: "network" };
  }
}

function messageFrom(body: unknown): string | null {
  if (!body || typeof body !== "object" || !("error" in body)) {
    return null;
  }
  const error = (body as { error?: { message?: unknown } }).error;
  return typeof error?.message === "string" ? error.message : null;
}

function isPreviewPayload(body: unknown): body is PreviewPayload {
  if (!body || typeof body !== "object" || !("ok" in body)) {
    return false;
  }
  const record = body as { ok?: unknown; data?: unknown; reason?: unknown; message?: unknown };
  if (record.ok === true) {
    return typeof record.data === "object" && record.data !== null;
  }
  return record.ok === false && typeof record.reason === "string" && typeof record.message === "string";
}

function isChatResult(body: unknown): body is ChatCompletionResult {
  if (!body || typeof body !== "object") {
    return false;
  }
  const record = body as { answer?: unknown; headers?: unknown };
  return typeof record.answer === "string" && typeof record.headers === "object" && record.headers !== null;
}
