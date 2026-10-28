import { entityClassName, segmentText, type HighlightSpan } from "@/lib/segments";

export function EntityText({ text, spans }: { text: string; spans: HighlightSpan[] }) {
  const segments = segmentText(text, spans);
  return (
    <p className="whitespace-pre-wrap font-mono text-sm leading-6">
      {segments.map((segment, index) =>
        segment.span ? (
          <mark
            key={`${segment.span.start}-${segment.span.entityType}-${index}`}
            data-entity={segment.span.entityType}
            title={segment.span.entityType}
            className={entityClassName(segment.span.entityType)}
          >
            {segment.text}
            <span className="sr-only"> ({segment.span.entityType})</span>
          </mark>
        ) : (
          <span key={`text-${index}`}>{segment.text}</span>
        ),
      )}
    </p>
  );
}
