"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { EntityText } from "@/components/entity-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { LEGEND_TYPES, entityClassName, type HighlightSpan } from "@/lib/segments";
import type { AnonymizePreviewResponse, ChatCompletionResult } from "@/lib/types";

const DETECTION_LOCALES = [
  ["en", "English"],
  ["de-DE", "Deutsch"],
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

export function Playground() {
  const t = useTranslations("playground");
  const headers = useTranslations("headers");
  const samples = useTranslations("samples");
  const uiLocale = useLocale();
  const [prompt, setPrompt] = useState(samples("pii"));
  const [model, setModel] = useState("grok");
  const [tenant, setTenant] = useState("");
  const [detectionLocale, setDetectionLocale] = useState(uiLocale === "de" ? "de-DE" : "en");
  const [models, setModels] = useState<string[]>(["grok", "grok-4", "grok-3"]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [submitted, setSubmitted] = useState("");
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [chat, setChat] = useState<ChatCompletionResult | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

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
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextPrompt = prompt;
    setPhase("running");
    setSubmitted(nextPrompt);
    setPreview(null);
    setChat(null);
    setChatError(null);
    const payload = {
      prompt: nextPrompt,
      model,
      tenantId: tenant.trim(),
      locale: detectionLocale,
    };

    const [previewResult, chatResult] = await Promise.all([
      postJson("/api/preview", payload),
      postJson("/api/chat", payload),
    ]);

    if (!previewResult.ok && previewResult.message === "network") {
      setPreview({ ok: false, reason: "error", status: 0, message: t("network") });
    } else if (!previewResult.ok) {
      setPreview({
        ok: false,
        reason: "error",
        status: previewResult.status,
        message: messageFrom(previewResult.body) ?? t("previewError"),
      });
    } else if (isPreviewPayload(previewResult.body)) {
      setPreview(previewResult.body);
    } else {
      setPreview({
        ok: false,
        reason: "error",
        status: previewResult.status,
        message: messageFrom(previewResult.body) ?? t("previewError"),
      });
    }

    if (!chatResult.ok) {
      setChatError(chatResult.message === "network" ? t("network") : (messageFrom(chatResult.body) ?? t("chatError")));
    } else if (isChatResult(chatResult.body)) {
      setChat(chatResult.body);
    } else {
      setChatError(t("chatError"));
    }
    setPhase("done");
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

  return (
    <div className="mt-8">
      <p className="sr-only" aria-live="polite">
        {phase === "running" ? t("sending") : phase === "done" ? t("done") : ""}
      </p>
      <form onSubmit={onSubmit} className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={() => setPrompt(samples("pii"))}>
            {t("samplePii")}
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => setPrompt(samples("clean"))}>
            {t("sampleClean")}
          </Button>
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
            className="mt-1.5 font-mono"
          />
          <p id="prompt-hint" className="mt-1 text-xs text-muted-foreground">
            {t("shortcut")}
          </p>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
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
            <Label htmlFor="tenant">{t("tenant")}</Label>
            <Input
              id="tenant"
              name="tenant"
              value={tenant}
              placeholder={t("tenantPlaceholder")}
              onChange={(event) => setTenant(event.target.value)}
              className="mt-1.5 font-mono"
              autoComplete="off"
            />
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
        <div className="mt-4">
          <Button type="submit" disabled={phase === "running"}>
            {phase === "running" ? t("sending") : t("send")}
          </Button>
        </div>
      </form>

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
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">{t("headersEmpty")}</p>
        )}
      </section>

      <div className="mt-6 grid gap-4 lg:grid-cols-3" aria-busy={phase === "running"}>
        <Column step="01" title={t("rawTitle")} hint={t("rawHint")}>
          {phase === "idle" ? <p className="text-sm text-muted-foreground">{t("empty")}</p> : null}
          {phase === "running" ? <Skeleton /> : null}
          {phase === "done" ? (
            <>
              {previewData ? (
                <EntityText text={submitted} spans={rawSpans} />
              ) : (
                <p className="whitespace-pre-wrap font-mono text-sm leading-6">{submitted}</p>
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
          {phase === "done" && preview && !preview.ok && preview.reason !== "disabled" && preview.reason !== "rate_limited" ? (
            <p role="alert" className="text-sm leading-6">
              {t("previewError")}: {preview.message}
            </p>
          ) : null}
        </Column>
        <Column step="03" title={t("answerTitle")} hint={t("answerHint")}>
          {phase === "idle" ? <p className="text-sm text-muted-foreground">{t("empty")}</p> : null}
          {phase === "running" ? <Skeleton /> : null}
          {phase === "done" && chat ? (
            <p className="whitespace-pre-wrap text-sm leading-6">{chat.answer}</p>
          ) : null}
          {phase === "done" && chatError ? (
            <p role="alert" className="text-sm leading-6">
              {t("chatError")}: {chatError}
            </p>
          ) : null}
        </Column>
      </div>

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
    <section aria-labelledby={headingId} className="flex min-h-72 flex-col rounded-xl border border-border bg-card p-4 shadow-sm">
      <p className="font-mono text-xs text-[#9a3412]">{step}</p>
      <h2 id={headingId} className="mt-1 font-serif text-2xl">
        {title}
      </h2>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">{hint}</p>
      <div className="mt-4 flex-1">{children}</div>
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

async function postJson(url: string, payload: unknown): Promise<{ ok: boolean; status: number; body: unknown; message?: string }> {
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
