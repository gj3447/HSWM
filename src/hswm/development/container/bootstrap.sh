#!/usr/bin/env bash
# Recreate only the locked development environments inside Dev Container volumes.
set -euo pipefail

test "$(node --version)" = "v24.13.0"
test "$(npm --version)" = "11.6.2"
printf '%s  %s\n' \
  '53fb205ae78805130177e24bcb459a69a1518c8d98f8965f31d85aae7ea840fc' \
  "$(command -v node)" | sha256sum --check --strict
test "$(python --version)" = "Python 3.12.13"
test "$(python -c 'import unicodedata; print(unicodedata.unidata_version)')" = "15.0.0"
case "$(uv --version)" in
  "uv 0.12.3"*) ;;
  *) echo 'This Dev Container requires uv 0.12.3.' >&2; exit 2 ;;
esac

src/hswm/development/bin/hswm-python sync
npm --prefix src/hswm/effect-runtime ci --ignore-scripts --no-audit --no-fund
npm --prefix src/hswm/effect-runtime run build
