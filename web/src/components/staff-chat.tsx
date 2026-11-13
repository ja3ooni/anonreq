"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { EntityText } from "@/components/entity-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Link } from "@/i18n/navigation";
import { STAFF_DEMO_PROMPTS } from "@/lib/bg-demo-prompts";
import { buildAnswerHighlights } from "@/lib/redact";
import type { HighlightSpan } from "@/lib/segments";
import { staffModelOptions } from "@/lib/staff-config";
import type { AnonymizePreviewResponse, ChatCompletionResult } from "@/lib/types";

type Phase = "idle" | "running" | "done";

type PreviewState =
  | { kind: "ok"; data: AnonymizePreviewResponse }
  | { kind: "disabled" }
  | { kind: "error"; message: string }
  | null;

export interface StaffChatProps {
  bggptAlias: string;
  aliasConfirmed: boolean;
  detectionLocale: string;
  isAdmin: boolean;
  exportHref: string;
}

export function StaffChat({ bggptAlias, aliasConfirmed, detectionLocale, isAdmin, exportHref }: StaffChatProps) {
  const t = useTranslations("staff");
  const uiLocale = useLocale() as "bg" | "en" | "de";
  const [models, setModels] = useState<string[]>(() => staffModelOptions(bggptAlias, []));
  const [model, setModel] = useState(bggptAlias);
  const [exampleId, setExampleId] = useState(STAFF_DEMO_PROMPTS[0]?.id ?? "");
  const [prompt, setPrompt] = useState(STAFF_DEMO_PROMPTS[0]?.prompt ?? "");
  const [submitted, setSubmitted] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [preview, setPreview] = useState<PreviewState>(null);
  const [chat, setChat] = useState<ChatCompletionResult | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/models")
      .then((response) => response.json())
      .then((body: { models?: unknown }) => {
        if (cancelled || !Array.isArray(body.models)) {
          return;
        }
        const list = body.models.filter((item): item is string => typeof item === "string");
        setModels(staffModelOptions(bggptAlias, list));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [bggptAlias]);

  function pickExample(id: string) {
    const found = STAFF_DEMO_PROMPTS.find((item) => item.id === id);
    if (found) {
      setExampleId(found.id);
      setPrompt(found.prompt);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim() || phase === "running") {
      return;
    }
    setPhase("running");
    setSubmitted(prompt);
    setPreview(null);
    setChat(null);
    setChatError(null);
    const payload = { prompt, model, locale: detectionLocale };
    const [previewResult, chatResult] = await Promise.all([
      postJson("/api/preview", payload),
      postJson("/api/chat", payload),
    ]);

    if (previewResult.network) {
      setPreview({ kind: "error", message: t("network") });
    } else if (isPreviewOk(previewResult.body)) {
      setPreview({ kind: "ok", data: previewResult.body.data });
    } else if (isPreviewDisabled(previewResult.body)) {
      setPreview({ kind: "disabled" });
    } else {
      setPreview({ kind: "error", message: messageFrom(previewResult.body) ?? t("previewError") });
    }

    if (chatResult.network) {
      setChatError(t("network"));
    } else if (chatResult.ok && isChatResult(chatResult.body)) {
      setChat(chatResult.body);
    } else {
      setChatError(messageFrom(chatResult.body) ?? t("chatError"));
    }
    setPhase("done");
  }

  const previewData = preview?.kind === "ok" ? preview.data : null;
  const entities = (previewData?.entities ?? []).filter((entity) => entity.message_index == null);
  // UTF-16 offsets from the gateway, so Cyrillic and emoji slice correctly in JavaScript.
  const rawSpans: HighlightSpan[] = entities.map((entity) => ({
    start: entity.start_utf16,
    end: entity.end_utf16,
    entityType: entity.entity_type,
    token: entity.token,
  }));
  const anonSpans: HighlightSpan[] = entities.map((entity) => ({
    start: entity.token_start_utf16,
    end: entity.token_end_utf16,
    entityType: entity.entity_type,
    token: entity.token,
  }));
  const answer = chat ? buildAnswerHighlights(chat.answer, chat.rawAnswer, entities) : null;

  return (
    <div className="mt-6 space-y-6">
      <p className="sr-only" aria-live="polite">
        {phase === "running" ? t("sending") : phase === "done" ? t("done") : ""}
      </p>

      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="grid gap-4 md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
          <div>
            <Label htmlFor="staff-model">{t("model")}</Label>
            <select
              id="staff-model"
              name="model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              aria-describedby="staff-model-help"
              data-testid="staff-model"
              className="mt-1 block w-full rounded-md border border-input bg-background px-3 py-2 text-sm leading-normal"
            >
              {models.map((item) => (
                <option key={item} value={item}>
                  {item === bggptAlias ? `BgGPT (${item})` : item}
                </option>
              ))}
            </select>
            <p id="staff-model-help" className="mt-1 text-xs leading-snug text-muted-foreground">
              {t("modelHelp")}
            </p>
            {!aliasConfirmed ? (
              <p className="mt-1 text-xs leading-snug text-[#9a3412]" data-testid="bggpt-pending">
                {t("bggptPending", { alias: bggptAlias })}
              </p>
            ) : null}
          </div>
          <fieldset>
            <legend className="text-sm font-medium leading-none">{t("examples")}</legend>
            <p className="mt-1 text-xs leading-snug text-muted-foreground">{t("examplesHint")}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {STAFF_DEMO_PROMPTS.map((example) => (
                <button
                  key={example.id}
                  type="button"
                  onClick={() => pickExample(example.id)}
                  aria-pressed={exampleId === example.id}
                  className={`rounded-md border px-3 py-1.5 text-left text-sm leading-snug focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e7a07a] ${
                    exampleId === example.id ? "border-[#1a1814] bg-[#1a1814] text-[#f6f1e8]" : "border-border bg-background"
                  }`}
                >
                  <span lang={uiLocale}>{example.label[uiLocale] ?? example.label.en}</span>
                  {example.synthetic ? (
                    <Badge className="ml-2 bg-[#f3d7a1] align-middle font-mono text-[10px] text-[#1a1814]">
                      {t("syntheticBadge")}
                    </Badge>
                  ) : null}
                </button>
              ))}
            </div>
          </fieldset>
        </div>
        <div>
          <Label htmlFor="staff-prompt">{t("prompt")}</Label>
          <Textarea
            id="staff-prompt"
            name="prompt"
            lang="bg"
            value={prompt}
            onChange={(event) => {
              setPrompt(event.target.value);
              setExampleId("");
            }}
            rows={5}
            className="mt-1 leading-6"
            data-testid="staff-prompt"
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={phase === "running" || !prompt.trim()} data-testid="staff-send">
            {phase === "running" ? t("sending") : t("send")}
          </Button>
          <span className="font-mono text-xs text-muted-foreground">
            {t("detectionLocale", { locale: detectionLocale })}
          </span>
          {previewData ? (
            <Badge className="bg-[#b7e0d6] font-mono text-[#1a1814]">
              {t("maskedCount", { count: entities.length })}
            </Badge>
          ) : null}
        </div>
      </form>

      <section aria-label={`${t("modelSawTitle")} / ${t("youSeeTitle")}`} className="grid gap-4 lg:grid-cols-2" data-testid="masking-view">
        <Column title={t("modelSawTitle")} hint={t("modelSawHint")} tone="dark">
          {phase === "idle" ? (
            <Empty>{t("empty")}</Empty>
          ) : (
            <>
              <Part label={t("requestLabel")}>
                {preview?.kind === "ok" ? (
                  <EntityText text={previewData?.anonymized_text ?? ""} spans={anonSpans} />
                ) : preview?.kind === "disabled" ? (
                  <Empty>{t("previewDisabled")}</Empty>
                ) : preview?.kind === "error" ? (
                  <ErrorText>{preview.message}</ErrorText>
                ) : (
                  <Empty>{t("sending")}</Empty>
                )}
              </Part>
              <Part label={t("replyLabel")}>
                {answer ? (
                  <EntityText text={answer.rawModelText} spans={answer.rawModelSpans} />
                ) : chatError ? (
                  <ErrorText>{chatError}</ErrorText>
                ) : (
                  <Empty>{t("sending")}</Empty>
                )}
              </Part>
            </>
          )}
        </Column>
        <Column title={t("youSeeTitle")} hint={t("youSeeHint")} tone="light">
          {phase === "idle" ? (
            <Empty>{t("empty")}</Empty>
          ) : (
            <>
              <Part label={t("requestLabel")}>
                <div lang="bg">
                  <EntityText text={submitted} spans={rawSpans} />
                </div>
              </Part>
              <Part label={t("replyLabel")}>
                {answer && chat ? (
                  <div lang="bg">
                    <EntityText text={chat.answer} spans={answer.restoredSpans} />
                  </div>
                ) : chatError ? (
                  <ErrorText>{chatError}</ErrorText>
                ) : (
                  <Empty>{t("sending")}</Empty>
                )}
              </Part>
            </>
          )}
        </Column>
      </section>

      {isAdmin ? (
        <section
          aria-labelledby="staff-admin-title"
          data-testid="staff-admin"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed border-[#9a3412] bg-card px-4 py-3"
        >
          <div className="min-w-0">
            <h2 id="staff-admin-title" className="font-serif text-lg leading-tight">
              {t("adminTitle")}
            </h2>
            <p className="text-sm leading-snug text-muted-foreground">{t("exportHint")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href={exportHref}
              download
              data-testid="audit-export-link"
              className="inline-flex items-center rounded-md bg-[#1a1814] px-3 py-2 text-sm font-medium text-[#f6f1e8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e7a07a]"
            >
              {t("exportCsv")}
            </a>
            <Link
              href="/audit"
              className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e7a07a]"
            >
              {t("openAudit")}
            </Link>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function Column({ title, hint, tone, children }: { title: string; hint: string; tone: "dark" | "light"; children: ReactNode }) {
  return (
    <div
      className={`min-w-0 rounded-xl border p-4 shadow-sm ${
        tone === "dark" ? "border-[#2a2622] bg-[#f6efe2]" : "border-border bg-card"
      }`}
    >
      <h2 className="font-serif text-2xl leading-tight">{title}</h2>
      <p className="mt-1 text-sm leading-snug text-muted-foreground">{hint}</p>
      <div className="mt-3 space-y-4">{children}</div>
    </div>
  );
}

function Part({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 font-mono text-[11px] uppercase tracking-[0.08em] text-[#9a3412]">{label}</p>
      <div className="rounded-md border border-border bg-background p-3">{children}</div>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm leading-snug text-muted-foreground">{children}</p>;
}

function ErrorText({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="text-sm leading-snug text-[#991b1b]">
      {children}
    </p>
  );
}

async function postJson(url: string, payload: unknown): Promise<{ ok: boolean; body: unknown; network: boolean }> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = (await response.json().catch(() => null)) as unknown;
    return { ok: response.ok, body, network: false };
  } catch {
    return { ok: false, body: null, network: true };
  }
}

function messageFrom(body: unknown): string | null {
  if (!body || typeof body !== "object") {
    return null;
  }
  const error = (body as { error?: { message?: unknown } }).error;
  if (typeof error?.message === "string") {
    return error.message;
  }
  const message = (body as { message?: unknown }).message;
  return typeof message === "string" ? message : null;
}

function isPreviewOk(body: unknown): body is { ok: true; data: AnonymizePreviewResponse } {
  return Boolean(
    body && typeof body === "object" && (body as { ok?: unknown }).ok === true && typeof (body as { data?: unknown }).data === "object",
  );
}

function isPreviewDisabled(body: unknown): boolean {
  return Boolean(
    body && typeof body === "object" && (body as { ok?: unknown }).ok === false && (body as { reason?: unknown }).reason === "disabled",
  );
}

function isChatResult(body: unknown): body is ChatCompletionResult {
  if (!body || typeof body !== "object") {
    return false;
  }
  const record = body as { answer?: unknown; headers?: unknown };
  return typeof record.answer === "string" && typeof record.headers === "object" && record.headers !== null;
}
