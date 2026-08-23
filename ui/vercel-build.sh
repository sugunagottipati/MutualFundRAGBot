#!/bin/sh
set -eu

api_base_url="${PUBLIC_API_BASE_URL:-}"
printf 'window.FUNDFACTS_CONFIG = Object.freeze({ apiBaseUrl: %s });\n' "$(printf '%s' "$api_base_url" | sed 's/\\/\\\\/g; s/"/\\"/g' | sed 's/^/"/; s/$/"/')" > config.js