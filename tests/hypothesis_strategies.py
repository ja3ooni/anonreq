"""Shared Hypothesis strategies for property-based testing.

These strategies are provided in a separate module (not conftest.py) to
avoid the ~40s FastAPI/pydantic import overhead that conftest.py incurs.
"""

from __future__ import annotations

from hypothesis import strategies as st

# Entity types used in test strategies
ENTITY_TYPES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "URL",
    "US_SSN",
    "PERSON",
    "LOCATION",
    "ORGANIZATION",
]

entity_types_st = st.sampled_from(ENTITY_TYPES)


@st.composite
def detection_span(draw, text: str = ""):
    """Generate a valid detection span with entity_type, start, end, score."""
    entity_type = draw(st.sampled_from(ENTITY_TYPES))
    if text:
        max_pos = len(text)
        if max_pos < 2:
            return None  # type: ignore[return-value]
        start = draw(st.integers(min_value=0, max_value=max_pos - 1))
        end = draw(
            st.integers(min_value=start + 1, max_value=min(start + 30, max_pos))
        )
    else:
        start = draw(st.integers(min_value=0, max_value=100))
        end = draw(st.integers(min_value=start + 1, max_value=start + 30))
    return {
        "entity_type": entity_type,
        "start": start,
        "end": end,
        "score": draw(st.floats(min_value=0.5, max_value=1.0)),
        "source": draw(st.sampled_from(["regex", "ner"])),
    }


@st.composite
def detection_list(draw, text: str = ""):
    """Generate a non-overlapping list of detection spans."""
    spans = []
    used_positions = set()
    for _ in range(draw(st.integers(min_value=0, max_value=5))):
        span = draw(detection_span(text))
        if span is None:
            continue
        # Ensure no overlap
        span_positions = set(range(span["start"], span["end"]))
        if not span_positions.intersection(used_positions):
            spans.append(span)
            used_positions.update(span_positions)
    return spans


@st.composite
def pii_text_with_spans(draw):
    """Generate text containing embedded PII with known span positions."""
    pii_values = {
        "EMAIL_ADDRESS": draw(st.emails()),
        "PHONE_NUMBER": (
            f"+1-{draw(st.integers(min_value=200, max_value=999))}"
            f"-{draw(st.integers(min_value=1000, max_value=9999))}"
        ),
        "IP_ADDRESS": (
            f"{draw(st.integers(1, 255))}."
            f"{draw(st.integers(0, 255))}."
            f"{draw(st.integers(0, 255))}."
            f"{draw(st.integers(1, 255))}"
        ),
        "URL": (
            f"https://{draw(st.text(min_size=4, max_size=12, alphabet=st.characters(whitelist_categories=('L',))))}.com"
        ),
    }
    entity_type = draw(st.sampled_from(list(pii_values.keys())))
    value = pii_values[entity_type]
    prefix = draw(
        st.text(
            min_size=0,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L",), whitelist_characters=" "
            ),
        )
    )
    suffix = draw(
        st.text(
            min_size=0,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L",), whitelist_characters=" "
            ),
        )
    )
    text = prefix + value + suffix
    span = {
        "entity_type": entity_type,
        "start": len(prefix),
        "end": len(prefix) + len(value),
        "score": 1.0,
        "source": "regex",
    }
    return text, [span]
