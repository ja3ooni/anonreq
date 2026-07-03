#!/usr/bin/env python3
"""Export OpenAPI schema from the FastAPI application.

Usage: python scripts/export_openapi.py > docs/openapi.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app

schema = app.openapi()
json.dump(schema, sys.stdout, indent=2)
