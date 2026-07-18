"""Format-specific serializers for eDiscovery exports.

Provides ``to_jsonl``, ``to_pdf_summary``, and ``to_edrm_xml``
functions that convert a list of consolidated records into the
requested output format.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from anonreq.models.ediscovery import EDRMMetadata, ExportFormat


def to_jsonl(
    records: list[dict[str, Any]],
    metadata: EDRMMetadata | None = None,
) -> str:
    """Serialize records to newline-delimited JSON (JSONL).

    Each record is a JSON object on its own line. An optional metadata
    header can be emitted as a comment (``#``) line.

    Args:
        records: List of consolidated record dicts.
        metadata: Optional EDRM metadata (used for header comment).

    Returns:
        A JSONL string where each line is a JSON object.
    """
    lines: list[str] = []

    if metadata:
        lines.append(
            f"# Export: {metadata.case_name} | {metadata.request_name} "
            f"| {datetime.now(UTC).isoformat()}"
        )

    for record in records:
        lines.append(json.dumps(record, default=str))

    return "\n".join(lines) + "\n" if lines else ""


def to_pdf_summary(
    records: list[dict[str, Any]],
    title: str = "eDiscovery Export Summary",
) -> str:
    """Serialize records to a PDF summary report.

    Generates a table-structured PDF using ``reportlab`` with a
    summary header and tabular data rows.

    Args:
        records: List of consolidated record dicts.
        title: Report title (default "eDiscovery Export Summary").

    Returns:
        PDF content as a byte string (decoded to latin-1 for transport).
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF export. "
            "Install with: pip install 'anonreq[exports]'"
        ) from None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )
    styles = getSampleStyleSheet()
    elements: list[Any] = []

    # Title
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 0.15 * inch))

    # Summary line
    summary_style = ParagraphStyle(
        "SummaryInfo", parent=styles["Normal"], fontSize=8,
    )
    elements.append(Paragraph(
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} "
        f"| Records: {len(records)}",
        summary_style,
    ))
    elements.append(Spacer(1, 0.15 * inch))

    if not records:
        elements.append(Paragraph("No records found.", styles["Normal"]))
        doc.build(elements)
        return buf.getvalue().decode("latin-1", errors="replace")

    # Build table
    keys = _select_pdf_columns(records[0])
    header_row = [Paragraph(k.capitalize(), styles["Normal"]) for k in keys]
    data_rows: list[list[Paragraph]] = [header_row]

    for record in records:
        row: list[Paragraph] = []
        for key in keys:
            val = _get_nested(record, key)
            text = str(val)[:40] if val is not None else ""
            row.append(Paragraph(text, styles["Normal"]))
        data_rows.append(row)

    col_count = len(keys)
    avail_width = A4[0] - 1.0 * inch  # page width minus margins
    col_width = max(50, avail_width / max(col_count, 1))

    table = Table(data_rows, colWidths=[col_width] * col_count)
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.86, 0.86, 0.86)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    table.setStyle(TableStyle(style_cmds))
    elements.append(table)

    doc.build(elements)
    return buf.getvalue().decode("latin-1", errors="replace")


def to_edrm_xml(
    records: list[dict[str, Any]],
    metadata: EDRMMetadata | None = None,
) -> str:
    """Serialize records to EDRM XML format.

    Produces an XML document following the EDRM (Electronic Discovery
    Reference Model) structure with ``<Case>``, ``<Request>``,
    ``<Documents>``, and per-record ``<Document>`` elements.

    Args:
        records: List of consolidated record dicts.
        metadata: Optional case/request metadata.

    Returns:
        An XML string with ``<?xml?>`` declaration.
    """
    root = Element("EDRM")
    root.set("xmlns", "http://edrm.net/ns/v1")

    # ── Case ────────────────────────────────────────────────────────
    case_el = SubElement(root, "Case")
    if metadata:
        SubElement(case_el, "CaseID").text = metadata.case_id
        SubElement(case_el, "CaseName").text = metadata.case_name
        SubElement(case_el, "Matter").text = metadata.matter
        SubElement(case_el, "Customer").text = metadata.customer
    else:
        SubElement(case_el, "CaseID").text = ""
        SubElement(case_el, "CaseName").text = "eDiscovery Export"

    # ── Request ─────────────────────────────────────────────────────
    req_el = SubElement(root, "Request")
    if metadata:
        SubElement(req_el, "RequestID").text = metadata.request_id
        SubElement(req_el, "RequestName").text = metadata.request_name
        SubElement(req_el, "RequestType").text = metadata.request_type
        SubElement(req_el, "Notes").text = metadata.notes
    else:
        SubElement(req_el, "RequestID").text = ""
        SubElement(req_el, "RequestName").text = "Export"
        SubElement(req_el, "RequestType").text = "PRODUCTION"

    # ── Custodians ──────────────────────────────────────────────────
    custodians = set()
    for rec in records:
        src = rec.get("source", {})
        tid = src.get("tenant_id", "") or rec.get("tenant_id", "")
        if tid:
            custodians.add(tid)

    cust_el = SubElement(root, "Custodians")
    for cid in sorted(custodians):
        c_el = SubElement(cust_el, "Custodian")
        SubElement(c_el, "CustodianID").text = cid
        SubElement(c_el, "CustodianName").text = cid

    # ── Documents ───────────────────────────────────────────────────
    docs_el = SubElement(root, "Documents")
    for idx, record in enumerate(records, start=1):
        doc_el = SubElement(docs_el, "Document")
        SubElement(doc_el, "DocID").text = str(idx)
        SubElement(doc_el, "RecordID").text = record.get("id", "")

        src = record.get("source", {})
        for k, v in src.items():
            if v is not None:
                el = SubElement(doc_el, _xml_tag(k))
                el.text = str(v)

        # Additional metadata
        meta = record.get("metadata", {})
        if meta:
            meta_el = SubElement(doc_el, "Metadata")
            for mk, mv in meta.items():
                if mv is not None:
                    mel = SubElement(meta_el, _xml_tag(mk))
                    mel.text = str(mv)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
        root, encoding="unicode"
    )


# ── Internal helpers ───────────────────────────────────────────────


def _select_pdf_columns(record: dict[str, Any]) -> list[str]:
    """Select column keys for PDF table display."""
    # Prefer known fields in a logical order
    preferred = [
        "id", "source.tenant_id", "source.provider",
        "source.entity_types", "source.request_timestamp",
        "metadata.request_type", "source.cache_hit",
    ]
    available = []
    for key in preferred:
        val = _get_nested(record, key)
        if val is not None:
            # Shorten display name
            display = key.split(".")[-1]
            available.append(display)
    return available or list(record.keys())


def _get_nested(record: dict[str, Any], key: str) -> Any:
    """Get a dot-delimited nested key from a dict."""
    parts = key.split(".")
    current: Any = record
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _xml_tag(key: str) -> str:
    """Convert a snake_case or dot-separated key to a PascalCase XML tag.

    Strips leading underscores and capitalises the first letter of
    each segment.
    """
    # Replace dots and underscores with spaces, title-case, remove spaces
    name = key.replace(".", " ").replace("_", " ").strip()
    return "".join(word.capitalize() for word in name.split())


def serialize(
    records: list[dict[str, Any]],
    export_format: ExportFormat,
    metadata: EDRMMetadata | None = None,
    title: str = "eDiscovery Export Summary",
) -> str:
    """Serialize records to the requested export format.

    Args:
        records: List of consolidated record dicts.
        export_format: Target format.
        metadata: Optional EDRM metadata for XML/JSONL headers.
        title: Title for PDF summary.

    Returns:
        Formatted content string.

    Raises:
        ValueError: If the format is unsupported.
    """
    if export_format == ExportFormat.JSONL:
        return to_jsonl(records, metadata=metadata)
    elif export_format == ExportFormat.PDF:
        return to_pdf_summary(records, title=title)
    elif export_format == ExportFormat.EDRM_XML:
        return to_edrm_xml(records, metadata=metadata)
    else:
        raise ValueError(
            f"Unsupported export format: {export_format}"
        )
