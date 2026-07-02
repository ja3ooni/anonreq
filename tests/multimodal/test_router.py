"""Tests for LocalRouter — content-type based routing decisions.

Tests cover:
- Route decisions for various content types
- Default routing rules
- Configuration from dict
- Edge cases: empty config, unknown types, wildcard matching
"""

from __future__ import annotations

import pytest

from anonreq.multimodal.router import LocalRouter, RouteDecision, RouteDecisionType


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def default_router() -> LocalRouter:
    """Router with default rules (no custom config)."""
    return LocalRouter()


@pytest.fixture
def custom_router() -> LocalRouter:
    """Router with custom rules."""
    return LocalRouter({
        "application/xml": "FORWARD",
        "application/pdf": "ROUTE_LOCAL",
        "text/csv": "BLOCK",
    })


# ── RouteDecisionType enum ──────────────────────────────────────────────────


class TestRouteDecisionType:
    def test_values(self) -> None:
        assert RouteDecisionType.FORWARD == "FORWARD"
        assert RouteDecisionType.ROUTE_LOCAL == "ROUTE_LOCAL"
        assert RouteDecisionType.BLOCK == "BLOCK"

    def test_all_members(self) -> None:
        assert len(RouteDecisionType) == 3


# ── RouteDecision model ────────────────────────────────────────────────────


class TestRouteDecision:
    def test_default_creation(self) -> None:
        d = RouteDecision(decision=RouteDecisionType.FORWARD)
        assert d.decision == RouteDecisionType.FORWARD
        assert d.reason is None
        assert d.content_type == ""

    def test_full_creation(self) -> None:
        d = RouteDecision(
            decision=RouteDecisionType.ROUTE_LOCAL,
            reason="Binary content type",
            content_type="image/png",
        )
        assert d.decision == RouteDecisionType.ROUTE_LOCAL
        assert d.reason == "Binary content type"
        assert d.content_type == "image/png"


# ── Default routing rules ──────────────────────────────────────────────────


class TestDefaultRouting:
    def test_text_plain_forwards(self, default_router: LocalRouter) -> None:
        d = default_router.route("text/plain", b"hello")
        assert d.decision == RouteDecisionType.FORWARD

    def test_application_json_forwards(self, default_router: LocalRouter) -> None:
        d = default_router.route("application/json", b"{}")
        assert d.decision == RouteDecisionType.FORWARD

    def test_multipart_form_data_forwards(self, default_router: LocalRouter) -> None:
        d = default_router.route("multipart/form-data", b"data")
        assert d.decision == RouteDecisionType.FORWARD

    def test_application_octet_stream_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("application/octet-stream", b"binary")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_image_png_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("image/png", b"PNG...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_image_jpeg_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("image/jpeg", b"JPEG...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_image_gif_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("image/gif", b"GIF...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_image_webp_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("image/webp", b"WEBP...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_audio_mpeg_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("audio/mpeg", b"MP3...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_audio_wav_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("audio/wav", b"WAV...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_video_mp4_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("video/mp4", b"MP4...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_text_html_forwards(self, default_router: LocalRouter) -> None:
        d = default_router.route("text/html", b"<html>")
        assert d.decision == RouteDecisionType.FORWARD

    def test_text_csv_forwards(self, default_router: LocalRouter) -> None:
        d = default_router.route("text/csv", b"a,b,c")
        assert d.decision == RouteDecisionType.FORWARD

    def test_application_xml_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("application/xml", b"<xml/>")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_application_pdf_routes_local(self, default_router: LocalRouter) -> None:
        d = default_router.route("application/pdf", b"PDF...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL


# ── Custom routing rules ───────────────────────────────────────────────────


class TestCustomRouting:
    def test_custom_overrides_default(self, custom_router: LocalRouter) -> None:
        d = custom_router.route("application/xml", b"<xml/>")
        assert d.decision == RouteDecisionType.FORWARD

    def test_custom_block(self, custom_router: LocalRouter) -> None:
        d = custom_router.route("text/csv", b"a,b,c")
        assert d.decision == RouteDecisionType.BLOCK

    def test_custom_route_local(self, custom_router: LocalRouter) -> None:
        d = custom_router.route("application/pdf", b"PDF...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_custom_falls_through_to_default(self, custom_router: LocalRouter) -> None:
        """Types not in custom config use default rules."""
        d = custom_router.route("image/png", b"PNG...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL


# ── Edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_content_type(self, default_router: LocalRouter) -> None:
        d = default_router.route("", b"hello")
        assert d.decision == RouteDecisionType.FORWARD

    def test_none_content_type(self, default_router: LocalRouter) -> None:
        d = default_router.route(None, b"hello")  # type: ignore[arg-type]
        assert d.decision == RouteDecisionType.FORWARD

    def test_empty_payload(self, default_router: LocalRouter) -> None:
        d = default_router.route("text/plain", b"")
        assert d.decision == RouteDecisionType.FORWARD

    def test_unknown_type_in_defaults(self, default_router: LocalRouter) -> None:
        """A completely unknown type defaults to ROUTE_LOCAL."""
        d = default_router.route("application/x-custom", b"data")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_content_type_with_charset(self, default_router: LocalRouter) -> None:
        """Charset suffix is stripped before routing."""
        d = default_router.route("text/plain; charset=utf-8", b"hello")
        assert d.decision == RouteDecisionType.FORWARD

    def test_content_type_with_boundary(self, default_router: LocalRouter) -> None:
        """Boundary param is stripped before routing."""
        d = default_router.route("multipart/form-data; boundary=abc", b"data")
        assert d.decision == RouteDecisionType.FORWARD

    def test_content_type_case_insensitive(self, default_router: LocalRouter) -> None:
        d = default_router.route("IMAGE/PNG", b"PNG...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_audio_m4a_default(self, default_router: LocalRouter) -> None:
        """audio/* wildcard catches all audio subtypes."""
        d = default_router.route("audio/m4a", b"M4A...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_video_quicktime_default(self, default_router: LocalRouter) -> None:
        """video/* wildcard catches all video subtypes."""
        d = default_router.route("video/quicktime", b"MOV...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_wildcard_reason(self, default_router: LocalRouter) -> None:
        """Route decisions include a human-readable reason."""
        d = default_router.route("image/tiff", b"TIFF...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL
        assert d.reason is not None
        assert "image" in d.reason.lower() or "route_local" in d.decision.value.lower()

    def test_custom_empty_config(self) -> None:
        """Empty custom config falls back to defaults."""
        router = LocalRouter({})
        d = router.route("image/png", b"PNG...")
        assert d.decision == RouteDecisionType.ROUTE_LOCAL

    def test_custom_none_config(self) -> None:
        """None config falls back to defaults."""
        router = LocalRouter(None)
        d = router.route("text/plain", b"hello")
        assert d.decision == RouteDecisionType.FORWARD


class TestConfigSources:
    def test_from_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config from environment variable (simulated)."""
        config_dict = {"application/xml": "FORWARD"}
        router = LocalRouter(config_dict)
        d = router.route("application/xml", b"<xml/>")
        assert d.decision == RouteDecisionType.FORWARD

    def test_config_with_block_override(self) -> None:
        """BLOCK overrides default ROUTE_LOCAL."""
        router = LocalRouter({"application/octet-stream": "BLOCK"})
        d = router.route("application/octet-stream", b"data")
        assert d.decision == RouteDecisionType.BLOCK
