#!/usr/bin/env bash
# Helpers for scripts/demo.sh (sourced; also exercised by tests/unit/test_demo_env_sh.py).
#
# Every write to .env goes through _env_rewrite (awk, values passed via
# ENVIRON so /, &, =, +, quotes etc. are never interpreted), into a mktemp
# file (mode 600) that is mv'd over the original. awk always ends lines with
# "\n", so a .env without a trailing newline can no longer glue lines
# together (XAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY=... -> 503s).
# Portable: no in-place sed (GNU and BSD/macOS flags differ).

# _env_rewrite FILE MODE KEY [VALUE]
#   MODE=set:     replace the first KEY= line in place (drop later duplicates),
#                 append KEY=VALUE if absent.
#   MODE=comment: prefix every active KEY= line with VALUE (a comment prefix).
_env_rewrite() {
  local file="$1" tmp
  [[ -e "$file" ]] || : > "$file"
  tmp=$(mktemp "${file}.XXXXXX")
  chmod 600 "$tmp"
  ENV_MODE="$2" ENV_KEY="$3" ENV_VAL="${4-}" awk '
    BEGIN { mode = ENVIRON["ENV_MODE"]; k = ENVIRON["ENV_KEY"]; v = ENVIRON["ENV_VAL"]; done = 0 }
    {
      line = $0
      sub(/\r$/, "", line)
      probe = line
      sub(/^[ \t]*/, "", probe)
      if (substr(probe, 1, length(k) + 1) == k "=") {
        if (mode == "set") {
          if (!done) { print k "=" v; done = 1 }
          next
        }
        if (mode == "comment") { print v line; next }
      }
      print line
    }
    END { if (mode == "set" && !done) print k "=" v }
  ' "$file" > "$tmp" || { rm -f "$tmp"; return 1; }
  mv -f "$tmp" "$file"
}

# set_env_var KEY VALUE [FILE]  (FILE defaults to $ENV_FILE, then .env)
set_env_var() {
  _env_rewrite "${3:-${ENV_FILE:-.env}}" set "$1" "$2"
}

# get_env_var KEY [FILE]: last active value of KEY ("" if unset).
get_env_var() {
  local file="${2:-${ENV_FILE:-.env}}"
  [[ -f "$file" ]] || return 0
  ENV_KEY="$1" awk '
    BEGIN { k = ENVIRON["ENV_KEY"]; v = "" }
    { line = $0; sub(/\r$/, "", line); sub(/^[ \t]*/, "", line)
      if (substr(line, 1, length(k) + 1) == k "=") v = substr(line, length(k) + 2) }
    END { print v }
  ' "$file"
}

# repair_glued_env FILE
# Splits lines where a missing newline glued two assignments together, e.g.
# XAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY=xai-... . Only known demo
# variable names are split off, so ordinary values are left alone. Prints
# variable NAMES only (never values) to stderr.
repair_glued_env() {
  local file="$1" tmp
  [[ -f "$file" ]] || return 0
  tmp=$(mktemp "${file}.XXXXXX")
  chmod 600 "$tmp"
  awk '
    function split_line(line,    eq, head, rest, pos, m) {
      eq = index(line, "=")
      if (eq == 0 || line ~ /^[ \t]*#/) { print line; return }
      head = substr(line, 1, eq); rest = substr(line, eq + 1)
      m = match(rest, /(PROVIDER_API_KEY|XAI_[A-Z0-9_]+|ANONREQ_[A-Z0-9_]+|MINIO_[A-Z0-9_]+|POSTGRES_[A-Z0-9_]+)=/)
      if (m == 0) { print line; return }
      print head substr(rest, 1, RSTART - 1)
      fixed[++n] = substr(rest, RSTART, RLENGTH - 1)
      split_line(substr(rest, RSTART))
    }
    { l = $0; sub(/\r$/, "", l); split_line(l) }
    END { for (i = 1; i <= n; i++) printf "WARNING: .env had a glued line; split off %s onto its own line\n", fixed[i] > "/dev/stderr" }
  ' "$file" > "$tmp" || { rm -f "$tmp"; return 1; }
  mv -f "$tmp" "$file"
}

# sanitize_db_url ENV_FILE
# The demo stores SQLite on the anonreq_data volume at /app/data. A sqlite
# ANONREQ_DATABASE_URL pointing anywhere else (e.g. the old .env.example
# default sqlite+aiosqlite:///./anonreq.db) is commented out with a note so
# the compose default is used. Non-sqlite URLs (Postgres) are left alone.
sanitize_db_url() {
  local env_file="$1" url
  url=$(get_env_var ANONREQ_DATABASE_URL "$env_file")
  [[ -z "$url" ]] && return 0
  url="${url%\"}"; url="${url#\"}"; url="${url%\'}"; url="${url#\'}"
  case "$url" in
    sqlite*:////app/data/*) return 0 ;;
    sqlite*)
      _env_rewrite "$env_file" comment ANONREQ_DATABASE_URL "# disabled by make demo (SQLite must live in /app/data): "
      echo "NOTE: commented out ANONREQ_DATABASE_URL=$url in $env_file; the demo uses sqlite+aiosqlite:////app/data/anonreq.db on the anonreq_data volume."
      ;;
  esac
}
