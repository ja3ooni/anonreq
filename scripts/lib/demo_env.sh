#!/usr/bin/env bash
# Helpers for scripts/demo.sh (sourced; also exercised by tests/unit/test_demo_env_sh.py).

# sanitize_db_url ENV_FILE
# The demo stores SQLite on the anonreq_data volume at /app/data. A sqlite
# ANONREQ_DATABASE_URL pointing anywhere else (e.g. the old .env.example
# default sqlite+aiosqlite:///./anonreq.db) is commented out with a note so
# the compose default is used. Non-sqlite URLs (Postgres) are left alone.
sanitize_db_url() {
  local env_file="$1" line url
  line=$(grep -E '^[[:space:]]*ANONREQ_DATABASE_URL=' "$env_file" | tail -1 || true)
  [[ -z "$line" ]] && return 0
  url="${line#*=}"
  url="${url%\"}"; url="${url#\"}"; url="${url%\'}"; url="${url#\'}"
  case "$url" in
    sqlite*:////app/data/*) return 0 ;;
    sqlite*)
      sed -i.bak -E 's|^([[:space:]]*ANONREQ_DATABASE_URL=.*)$|# disabled by make demo (SQLite must live in /app/data): \1|' "$env_file"
      rm -f "$env_file.bak"
      echo "NOTE: commented out ANONREQ_DATABASE_URL=$url in $env_file; the demo uses sqlite+aiosqlite:////app/data/anonreq.db on the anonreq_data volume."
      ;;
  esac
}
