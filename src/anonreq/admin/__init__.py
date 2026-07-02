"""Admin API package for custom detection rules hot-reload.

Provides AtomicConfigRegistry for thread-safe config swap with version
tracking, CustomRecognizerRule/ExclusionEntry domain models, and FastAPI
endpoints GET /v1/config/rules and POST /v1/admin/config/rules.
"""