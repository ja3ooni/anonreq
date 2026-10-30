import { entityClassName, segmentText, type HighlightSpan } from "@/lib/segments";

/**
 * Shorten 10+ digit gateway HMAC token suffixes for readable display
 * (e.g. `[STREET_ADDRESS_DE_12491358124787686951]` -> `[STREET_ADDRESS_DE_…6951]`)
 * while preserving the full token in the hover tooltip.
 */
function formatDisplaySegment(text: string): string {
  return text.replace(/\[([A-Z][A-Z0-9_]*)_(\d{4,})(\d{4})\]/g, "[$1_…$3]");
}

export function EntityText({ text, spans }: { text: string; spans: HighlightSpan[] }) {
  const segments = segmentText(text, spans);
  return (
    <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] font-mono text-[13px] leading-6">
      {segments.map((segment, index) =>
        segment.span ? (
          <mark
            key={`${segment.span.start}-${segment.span.entityType}-${index}`}
            data-entity={segment.span.entityType}
            aria-label={`${segment.span.entityType}: ${segment.text}`}
            title={`${segment.span.entityType} · ${segment.span.token}`}
            className={`${entityClassName(segment.span.entityType)} break-all`}
          >
            {formatDisplaySegment(segment.text)}
          </mark>
        ) : (
          <span key={`text-${index}`}>{formatDisplaySegment(segment.text)}</span>
        ),
      )}
    </p>
  );
}
