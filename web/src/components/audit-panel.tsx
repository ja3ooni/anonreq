"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  AnonymizationEvent,
  ChainVerification,
  ConfigHistoryPage,
} from "@/lib/types";

interface ActivityFilters {
  dateFrom: string;
  dateTo: string;
  entityType: string;
  sort: "timestamp:desc" | "timestamp:asc";
  limit: number;
}

const EMPTY_FILTERS: ActivityFilters = {
  dateFrom: "",
  dateTo: "",
  entityType: "",
  sort: "timestamp:desc",
  limit: 10,
};

const ENTITY_OPTIONS = [
  "PERSON",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "IBAN_CODE",
  "CREDIT_CARD",
  "DATE_TIME",
  "LOCATION",
];

export function AuditPanel() {
  const t = useTranslations("audit");
  const locale = useLocale();
  const [draft, setDraft] = useState<ActivityFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<ActivityFilters>(EMPTY_FILTERS);
  const [items, setItems] = useState<AnonymizationEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [totalExact, setTotalExact] = useState(true);
  const [source, setSource] = useState<"events" | "legacy-export" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [verification, setVerification] = useState<ChainVerification | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  const queryKey = useMemo(() => JSON.stringify(applied), [applied]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetch(`/api/audit/events?${activityParams(applied)}`, { signal: controller.signal })
      .then(async (response) => {
        const body = (await response.json()) as EventsResponse;
        if (response.status === 403) {
          throw new Error(t("tenantForbidden"));
        }
        if (!response.ok) {
          throw new Error(body.error?.message ?? t("loading"));
        }
        setItems(body.items ?? []);
        setNextCursor(body.next_cursor ?? null);
        setTotal(typeof body.total === "number" ? body.total : null);
        setTotalExact(body.totalExact !== false);
        setSource(body.source ?? "events");
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setError(reason instanceof Error ? reason.message : t("loading"));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [queryKey, applied, t]);

  const formatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale === "de" ? "de-DE" : "en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Europe/Berlin",
      }),
    [locale],
  );

  const pageLabel =
    total == null
      ? ""
      : totalExact
        ? t("loaded", { count: items.length, total })
        : t("loadedInexact", { count: items.length, total });

  async function onLoadMore() {
    if (!nextCursor) {
      return;
    }
    setLoadingMore(true);
    setError(null);
    try {
      const response = await fetch(`/api/audit/events?${activityParams(applied, nextCursor)}`);
      const body = (await response.json()) as EventsResponse;
      if (response.status === 403) {
        throw new Error(t("tenantForbidden"));
      }
      if (!response.ok) {
        throw new Error(body.error?.message ?? t("loading"));
      }
      setItems((current) => [...current, ...(body.items ?? [])]);
      setNextCursor(body.next_cursor ?? null);
      setTotal(typeof body.total === "number" ? body.total : total);
      setTotalExact(body.totalExact !== false);
      setSource(body.source ?? source);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("loading"));
    } finally {
      setLoadingMore(false);
    }
  }

  async function onExport() {
    setExporting(true);
    setExportError(null);
    try {
      const response = await fetch(`/api/audit/export?${activityParams(applied)}`);
      if (response.status === 403) {
        throw new Error(t("tenantForbidden"));
      }
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
        throw new Error(body?.error?.message ?? t("exportError"));
      }
      const partial = response.headers.get("x-anonreq-export-status") === "partial";
      if (partial) {
        setExportError(t("exportPartial"));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const disposition = response.headers.get("Content-Disposition") ?? "";
      const match = disposition.match(/filename="([^"]+)"/);
      link.href = url;
      link.download = match?.[1] ?? "anonymization-events.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setExportError(reason instanceof Error ? reason.message : t("exportError"));
    } finally {
      setExporting(false);
    }
  }

  async function onVerify() {
    setVerifying(true);
    setVerifyError(null);
    try {
      const response = await fetch("/api/audit/verify");
      const body = (await response.json()) as ChainVerification & { error?: { message?: string } };
      if (!response.ok) {
        throw new Error(body.error?.message ?? t("verifyTitle"));
      }
      setVerification(body);
    } catch (reason) {
      setVerification(null);
      setVerifyError(reason instanceof Error ? reason.message : t("verifyTitle"));
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="mt-8 space-y-6">
      <form
        className="rounded-xl border border-border bg-card p-4 shadow-sm"
        onSubmit={(event) => {
          event.preventDefault();
          const unchanged = JSON.stringify(draft) === JSON.stringify(applied);
          if (!unchanged) {
            setLoading(true);
          }
          setApplied(draft);
        }}
      >
        <fieldset>
          <legend className="sr-only">{t("filters")}</legend>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <Field label={t("from")} id="date-from">
              <Input
                id="date-from"
                type="datetime-local"
                value={draft.dateFrom}
                onChange={(event) => setDraft({ ...draft, dateFrom: event.target.value })}
              />
            </Field>
            <Field label={t("to")} id="date-to">
              <Input
                id="date-to"
                type="datetime-local"
                value={draft.dateTo}
                onChange={(event) => setDraft({ ...draft, dateTo: event.target.value })}
              />
            </Field>
            <Field label={t("entity")} id="entity-type">
              <Input
                id="entity-type"
                list="entity-types"
                placeholder={t("entityPlaceholder")}
                value={draft.entityType}
                onChange={(event) => setDraft({ ...draft, entityType: event.target.value.toUpperCase() })}
                className="font-mono"
                autoComplete="off"
              />
              <datalist id="entity-types">
                {ENTITY_OPTIONS.map((type) => (
                  <option key={type} value={type} />
                ))}
              </datalist>
            </Field>
            <Field label={t("sort")} id="sort">
              <select
                id="sort"
                value={draft.sort}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    sort: event.target.value === "timestamp:asc" ? "timestamp:asc" : "timestamp:desc",
                  })
                }
                className={selectClass}
              >
                <option value="timestamp:desc">{t("newest")}</option>
                <option value="timestamp:asc">{t("oldest")}</option>
              </select>
            </Field>
            <Field label={t("limit")} id="limit">
              <select
                id="limit"
                value={draft.limit}
                onChange={(event) => setDraft({ ...draft, limit: Number(event.target.value) })}
                className={selectClass}
              >
                {[10, 25, 50, 100].map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="submit">{t("apply")}</Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setDraft(EMPTY_FILTERS);
                setApplied(EMPTY_FILTERS);
                setLoading(true);
              }}
            >
              {t("reset")}
            </Button>
            <Button type="button" variant="outline" onClick={() => void onExport()} disabled={exporting}>
              {exporting ? t("exporting") : t("export")}
            </Button>
          </div>
        </fieldset>
      </form>

      {source === "legacy-export" ? (
        <p role="status" className="rounded-lg border border-dashed border-[#9a3412] bg-[#fbf6ef] p-4 text-sm leading-6">
          {t("fallback")}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm">
          {error}
        </p>
      ) : null}
      {exportError ? (
        <p role="alert" className="text-sm">
          {t("exportError")}: {exportError}
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm" tabIndex={0} aria-label={t("tableScroll")}>
        <table className="w-full min-w-[880px] border-collapse text-left text-sm">
          <caption className="px-4 py-3 text-left font-serif text-xl">{t("caption")}</caption>
          <thead className="border-y border-border bg-secondary/60 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">{t("time")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("request")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("tenant")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("model")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("locale")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("entities")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("tokens")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("decision")}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-muted-foreground">
                  {t("loading")}
                </td>
              </tr>
            ) : null}
            {!loading && items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-muted-foreground">
                  {t("empty")}
                </td>
              </tr>
            ) : null}
            {!loading
              ? items.map((event, index) => (
                  <tr key={`${event.request_id ?? "row"}-${event.timestamp}-${index}`} className="border-b border-border last:border-0">
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      <time dateTime={event.timestamp}>{formatTime(formatter, event.timestamp)}</time>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{event.request_id}</td>
                    <td className="px-3 py-2 font-mono text-xs">{event.tenant_id}</td>
                    <td className="px-3 py-2 font-mono text-xs">{event.model ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs">{event.locale ?? "—"}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {event.entity_types.length === 0 ? "—" : null}
                        {event.entity_types.map((entity) => (
                          <Badge key={`${event.request_id ?? index}-${entity.type}`}>
                            {source === "legacy-export" ? entity.type : `${entity.type} × ${entity.count}`}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2 tabular-nums">{event.token_count ?? "—"}</td>
                    <td className="px-3 py-2">
                      <Badge>{event.decision ?? "—"}</Badge>
                    </td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {loading ? t("loading") : pageLabel}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!nextCursor || loading || loadingMore}
          onClick={() => void onLoadMore()}
        >
          {loadingMore ? t("loadingMore") : t("loadMore")}
        </Button>
      </div>

      <section aria-labelledby="verify-title" className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="verify-title" className="font-serif text-2xl">
            {t("verifyTitle")}
          </h2>
          <Button type="button" variant="outline" onClick={() => void onVerify()} disabled={verifying}>
            {verifying ? t("verifyLoading") : t("verifyAction")}
          </Button>
        </div>
        {verification ? (
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">{t("verifyTitle")}</dt>
              <dd className="font-medium">{verification.is_intact ? t("intact") : t("broken")}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("checked", { count: verification.checked_count })}</dt>
              <dd className="font-mono">{verification.checked_count}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("brokenAt", { id: verification.broken_at ?? "—" })}</dt>
              <dd className="font-mono">{verification.broken_at ?? "—"}</dd>
            </div>
          </dl>
        ) : null}
        {verifyError ? (
          <p role="alert" className="mt-3 text-sm">
            {verifyError}
          </p>
        ) : null}
      </section>

      <details className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <summary className="cursor-pointer font-serif text-2xl">{t("tabsConfig")}</summary>
        <div className="mt-4">
          <ConfigHistory dateFrom={applied.dateFrom} dateTo={applied.dateTo} />
        </div>
      </details>
    </div>
  );
}

function ConfigHistory({ dateFrom, dateTo }: { dateFrom: string; dateTo: string }) {
  const t = useTranslations("audit");
  const locale = useLocale();
  const [changeType, setChangeType] = useState("");
  const [operator, setOperator] = useState("");
  const [tenant, setTenant] = useState("");
  const [applied, setApplied] = useState({ changeType: "", operator: "", tenant: "" });
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<ConfigHistoryPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const limit = 25;

  const queryKey = JSON.stringify({ dateFrom, dateTo, ...applied, offset });

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (applied.tenant) params.set("tenant_id", applied.tenant);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (applied.changeType) params.set("event_type", applied.changeType);
    if (applied.operator) params.set("operator_id", applied.operator);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    fetch(`/api/audit/config-history?${params}`, { signal: controller.signal })
      .then(async (response) => {
        const body = (await response.json()) as ConfigHistoryPage & { error?: { message?: string } };
        if (!response.ok) {
          throw new Error(body.error?.message ?? t("configLoading"));
        }
        setPage(body);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setError(reason instanceof Error ? reason.message : t("configLoading"));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [queryKey, dateFrom, dateTo, applied, offset, t]);

  const formatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale === "de" ? "de-DE" : "en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Europe/Berlin",
      }),
    [locale],
  );

  return (
    <div>
      <form
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
        onSubmit={(event) => {
          event.preventDefault();
          setLoading(true);
          setApplied({ changeType, operator, tenant });
          setOffset(0);
        }}
      >
        <fieldset className="contents">
          <legend className="sr-only sm:col-span-2 lg:col-span-4">{t("configFilters")}</legend>
          <Field label={t("tenant")} id="config-tenant">
            <Input
              id="config-tenant"
              value={tenant}
              placeholder={t("tenantPlaceholder")}
              onChange={(event) => setTenant(event.target.value)}
              className="font-mono"
              autoComplete="off"
            />
          </Field>
          <Field label={t("changeType")} id="change-type">
            <Input
              id="change-type"
              value={changeType}
              onChange={(event) => setChangeType(event.target.value)}
              className="font-mono"
              autoComplete="off"
            />
          </Field>
          <Field label={t("operator")} id="operator">
            <Input
              id="operator"
              value={operator}
              onChange={(event) => setOperator(event.target.value)}
              className="font-mono"
              autoComplete="off"
            />
          </Field>
          <div className="flex items-end">
            <Button type="submit">{t("apply")}</Button>
          </div>
        </fieldset>
      </form>
      {error ? (
        <p role="alert" className="mt-3 text-sm">
          {error}
        </p>
      ) : null}
      <div className="mt-4 overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <caption className="px-4 py-3 text-left font-serif text-xl">{t("configCaption")}</caption>
          <thead className="border-y border-border bg-secondary/60 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">{t("time")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("event")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("tenant")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("change")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("operator")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("prevHash")}</th>
              <th scope="col" className="px-3 py-2 font-medium">{t("newHash")}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-muted-foreground">
                  {t("configLoading")}
                </td>
              </tr>
            ) : null}
            {!loading && page && page.items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-muted-foreground">
                  {t("configEmpty")}
                </td>
              </tr>
            ) : null}
            {!loading && page
              ? page.items.map((item) => (
                  <tr key={item.event_id} className="border-b border-border last:border-0">
                    <td className="whitespace-nowrap px-3 py-2">
                      <time dateTime={item.timestamp}>{formatTime(formatter, item.timestamp)}</time>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{item.event_id}</td>
                    <td className="px-3 py-2 font-mono text-xs">{item.tenant_id}</td>
                    <td className="px-3 py-2">{item.change_type ?? "—"}</td>
                    <td className="px-3 py-2">{item.operator_id ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs" title={item.prev_value_hash ?? undefined}>
                      {shortHash(item.prev_value_hash)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs" title={item.new_value_hash ?? undefined}>
                      {shortHash(item.new_value_hash)}
                    </td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!page || offset === 0}
          onClick={() => {
            setLoading(true);
            setOffset(Math.max(0, offset - limit));
          }}
        >
          {t("previous")}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!page || offset + page.items.length >= page.total}
          onClick={() => {
            setLoading(true);
            setOffset(offset + limit);
          }}
        >
          {t("next")}
        </Button>
      </div>
    </div>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-card px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

interface EventsResponse {
  items?: AnonymizationEvent[];
  total?: number;
  next_cursor?: string | null;
  totalExact?: boolean;
  source?: "events" | "legacy-export";
  error?: { message?: string };
}

function activityParams(filters: ActivityFilters, cursor?: string): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  if (filters.entityType) params.set("entity_type", filters.entityType);
  params.set("sort", filters.sort);
  params.set("limit", String(filters.limit));
  if (cursor) params.set("cursor", cursor);
  return params;
}

function formatTime(formatter: Intl.DateTimeFormat, value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "—";
  }
  return formatter.format(date);
}

function shortHash(value: string | null): string {
  if (!value) {
    return "—";
  }
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}
