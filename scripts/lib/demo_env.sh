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
      prefix = ""
      if (probe ~ /^export[ \t]+/) { prefix = "export "; sub(/^export[ \t]+/, "", probe) }
      if (substr(probe, 1, length(k) + 1) == k "=") {
        if (mode == "set") {
          if (!done) { print prefix k "=" v; done = 1 }
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
    { line = $0; sub(/\r$/, "", line); sub(/^[ \t]*/, "", line); sub(/^export[ \t]+/, "", line)
      if (substr(line, 1, length(k) + 1) == k "=") v = substr(line, length(k) + 2) }
    END { print v }
  ' "$file"
}

# Keys scripts/demo.sh writes to .env (the only names repair_glued_env splits on).
DEMO_MANAGED_KEYS="ANONREQ_API_KEY ANONREQ_ADMIN_API_KEY ANONREQ_ADMIN_TENANT_ID ANONREQ_KMS_MASTER_KEY ANONREQ_ANCHOR_SIGNING_KEY POSTGRES_USER POSTGRES_PASSWORD MINIO_ROOT_USER MINIO_ROOT_PASSWORD ANONREQ_DEMO_MODEL XAI_API_KEY PROVIDER_API_KEY"

# repair_glued_env FILE
# Splits lines where a missing newline glued an assignment of a key this
# script writes onto the previous line, e.g.
#   XAI_BASE_URL=https://api.x.aiPROVIDER_API_KEY=xai-...
# Conservative, so valid values are never corrupted: only exact names from
# DEMO_MANAGED_KEYS, never when the name follows ?, &, ; or _ (URL query /
# longer identifier), never inside a quoted value, never on comment lines.
# Prints variable NAMES only (never values) to stderr.
repair_glued_env() {
  local file="$1" tmp
  [[ -f "$file" ]] || return 0
  tmp=$(mktemp "${file}.XXXXXX")
  chmod 600 "$tmp"
  KEYS="$DEMO_MANAGED_KEYS" awk '
    BEGIN { nk = split(ENVIRON["KEYS"], keys, " ") }
    # first position in s (after index 1) where a managed KEY= starts, or 0
    function find_glue(s,    i, p, best, from, prev, cut) {
      best = 0
      for (i = 1; i <= nk; i++) {
        from = 1
        while ((p = index(substr(s, from), keys[i] "=")) > 0) {
          p += from - 1
          prev = (p > 1) ? substr(s, p - 1, 1) : ""
          if (p > 1 && prev !~ /[?&;_]/) { if (best == 0 || p < best) { best = p; blen[0] = length(keys[i]) } ; break }
          from = p + 1
        }
      }
      return best
    }
    function split_line(line,    eq, head, rest, p, probe) {
      probe = line
      sub(/^[ \t]*/, "", probe)
      if (probe ~ /^#/) { print line; return }
      eq = index(line, "=")
      if (eq == 0) { print line; return }
      head = substr(line, 1, eq); rest = substr(line, eq + 1)
      if (rest ~ /^["\047]/) { print line; return }
      p = find_glue(rest)
      if (p == 0) { print line; return }
      print head substr(rest, 1, p - 1)
      fixed[++n] = substr(rest, p, blen[0])
      split_line(substr(rest, p))
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
