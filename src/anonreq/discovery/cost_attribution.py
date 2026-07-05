"""Cost attribution service for AI service usage.

Provides:
- PROVIDER_PRICING: Per-model pricing tables ($/1M tokens)
- CostAttributionService: Estimates costs from token volumes
"""

from __future__ import annotations

from typing import Any

# Pricing in $ per 1M tokens (input/output)
PROVIDER_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "o1": {"input": 15.0, "output": 60.0},
        "o3": {"input": 10.0, "output": 40.0},
        "dall-e-3": {"input": 0.0, "output": 0.040},
        "whisper-1": {"input": 0.006, "output": 0.0},
        "tts-1": {"input": 0.0, "output": 0.015},
        "embedding-3-small": {"input": 0.00002, "output": 0.0},
        "embedding-3-large": {"input": 0.00013, "output": 0.0},
    },
    "anthropic": {
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-4": {"input": 15.0, "output": 75.0},
    },
    "google": {
        "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.0-pro": {"input": 2.0, "output": 8.0},
    },
    "amazon": {
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "llama-3.1-70b": {"input": 0.99, "output": 0.99},
        "llama-3.1-8b": {"input": 0.22, "output": 0.22},
        "mistral-large": {"input": 4.0, "output": 4.0},
    },
    "meta": {
        "llama-3.1-405b": {"input": 2.80, "output": 2.80},
        "llama-3.1-70b": {"input": 0.99, "output": 0.99},
        "llama-3.1-8b": {"input": 0.22, "output": 0.22},
    },
    "mistral": {
        "mistral-large": {"input": 4.0, "output": 12.0},
        "mistral-small": {"input": 1.0, "output": 3.0},
    },
    "cohere": {
        "command-r-plus": {"input": 3.0, "output": 15.0},
        "command-r": {"input": 0.50, "output": 1.50},
        "embed-english-v3": {"input": 0.0001, "output": 0.0},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.14, "output": 0.28},
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    },
}

# Average pricing fallback per provider (when model unknown)
_AVERAGE_PRICING: dict[str, float] = {
    "openai": 15.0,
    "anthropic": 20.0,
    "google": 2.0,
    "amazon": 3.0,
    "meta": 1.5,
    "mistral": 5.0,
    "cohere": 5.0,
    "deepseek": 0.5,
    "unknown": 10.0,
}


class CostAttributionService:
    """Estimates AI service costs from provider pricing tables.

    Args:
        pricing: Optional custom pricing table override.
    """

    def __init__(
        self,
        pricing: dict[str, dict[str, dict[str, float]]] | None = None,
    ) -> None:
        self._pricing = dict(pricing) if pricing else dict(PROVIDER_PRICING)

    def estimate(
        self,
        provider: str,
        model: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> float:
        """Estimate cost for a single request.

        Args:
            provider: Provider name (e.g. openai).
            model: Model name (e.g. gpt-4). Uses provider average if None.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        provider_pricing = self._pricing.get(provider.lower(), {})
        model_pricing: dict[str, float] | None = None

        if model:
            model_pricing = provider_pricing.get(model.lower())
            if model_pricing is None:
                # Try case-insensitive matching
                for m_key, m_val in provider_pricing.items():
                    if m_key.lower() == model.lower():
                        model_pricing = m_val
                        break

        if model_pricing:
            input_cost = (input_tokens / 1_000_000) * model_pricing.get("input", 0)
            output_cost = (output_tokens / 1_000_000) * model_pricing.get("output", 0)
            return round(input_cost + output_cost, 6)

        # Fallback: use provider average
        avg_price = _AVERAGE_PRICING.get(provider.lower(), 10.0)
        total_tokens = input_tokens + output_tokens
        return round((total_tokens / 1_000_000) * avg_price, 6)

    def estimate_from_volume(
        self,
        provider: str,
        total_tokens: int,
    ) -> float:
        """Estimate cost using provider average pricing.

        Args:
            provider: Provider name.
            total_tokens: Total token count.

        Returns:
            Estimated cost in USD.
        """
        avg_price = _AVERAGE_PRICING.get(provider.lower(), 10.0)
        return round((total_tokens / 1_000_000) * avg_price, 6)

    def get_breakdowns(
        self,
        records: list[Any],
    ) -> dict[str, Any]:
        """Get cost breakdowns from a list of inventory-like records.

        Args:
            records: List of objects with provider, model, estimated_cost attrs.

        Returns:
            Dict with by_provider, by_model, by_business_unit.
        """
        by_provider: dict[str, float] = {}
        by_model: dict[str, float] = {}
        by_bu: dict[str, float] = {}

        for record in records:
            prov = getattr(record, "provider", None) or "unknown"
            model = getattr(record, "model", None) or "unknown"
            cost = getattr(record, "estimated_cost", 0.0) or 0.0
            bu = getattr(record, "business_unit", None) or "unknown"

            by_provider[prov] = by_provider.get(prov, 0.0) + cost
            model_key = f"{prov}/{model}"
            by_model[model_key] = by_model.get(model_key, 0.0) + cost
            by_bu[bu] = by_bu.get(bu, 0.0) + cost

        return {
            "by_provider": {k: round(v, 2) for k, v in sorted(by_provider.items())},
            "by_model": {k: round(v, 2) for k, v in sorted(by_model.items())},
            "by_business_unit": {k: round(v, 2) for k, v in sorted(by_bu.items())},
        }

    def set_pricing(
        self,
        provider: str,
        model: str,
        input_price: float,
        output_price: float,
    ) -> None:
        """Update pricing table at runtime.

        Args:
            provider: Provider name.
            model: Model name.
            input_price: Price per 1M input tokens.
            output_price: Price per 1M output tokens.
        """
        if provider not in self._pricing:
            self._pricing[provider] = {}
        self._pricing[provider][model] = {
            "input": input_price,
            "output": output_price,
        }
