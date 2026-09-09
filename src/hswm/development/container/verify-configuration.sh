#!/usr/bin/env bash
# Static regressions for Dev Container isolation and Python-environment selection.
set -euo pipefail

hswm_container_root=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)
hswm_container_config="$hswm_container_root/.devcontainer/devcontainer.json"
hswm_container_bootstrap="$hswm_container_root/src/hswm/development/container/bootstrap.sh"
hswm_container_entrypoint="$hswm_container_root/.devcontainer/entrypoint.sh"
hswm_container_dockerfile="$hswm_container_root/.devcontainer/Dockerfile"
hswm_container_ignore="$hswm_container_root/.devcontainer/Dockerfile.dockerignore"

jq empty "$hswm_container_config"
jq -e '.build.context == "." and .build.dockerfile == "Dockerfile"' "$hswm_container_config" >/dev/null
jq -e '.containerEnv | has("UV_PROJECT_ENVIRONMENT") | not' "$hswm_container_config" >/dev/null
jq -e '.mounts | all(contains("-${devcontainerId},target=") and contains("type=volume") and contains("volume-nocopy"))' \
  "$hswm_container_config" >/dev/null

for hswm_container_target in \
  /workspaces/HSWM/.hswm-local \
  /workspaces/HSWM/.venv \
  /workspaces/HSWM/_research/graph_standards/runtime/.venv \
  /workspaces/HSWM/src/hswm/effect-runtime/node_modules \
  /workspaces/HSWM/src/hswm/effect-runtime/dist
do
  jq -e --arg target "$hswm_container_target" \
    '.mounts | any(contains("target=" + $target) and contains("type=volume") and contains("volume-nocopy"))' \
    "$hswm_container_config" >/dev/null
done

rg -F 'src/hswm/development/bin/hswm-python sync' "$hswm_container_bootstrap" >/dev/null
if rg -F 'uv sync' "$hswm_container_bootstrap" >/dev/null; then
  echo 'bootstrap must delegate Python environment selection to hswm-python.' >&2
  exit 1
fi
rg -F 'chown -R hswm:hswm' "$hswm_container_entrypoint" >/dev/null
rg -F 'exec su -s /bin/sh hswm' "$hswm_container_entrypoint" >/dev/null
rg -F 'ENTRYPOINT ["/usr/local/bin/hswm-devcontainer-entrypoint"]' "$hswm_container_dockerfile" >/dev/null
rg -F 'COPY entrypoint.sh /usr/local/bin/hswm-devcontainer-entrypoint' "$hswm_container_dockerfile" >/dev/null
test "$(rg -v '^#|^$' "$hswm_container_ignore" | wc -l | tr -d ' ')" = "2"
rg -x -F '**' "$hswm_container_ignore" >/dev/null
rg -x -F '!entrypoint.sh' "$hswm_container_ignore" >/dev/null
rg -F "printf '%s  %s\\n'" "$hswm_container_dockerfile" >/dev/null
if rg -F "\\\\n" "$hswm_container_dockerfile" >/dev/null; then
  echo 'Dockerfile SHA-256 printf must contain one newline escape.' >&2
  exit 1
fi
bash -n "$hswm_container_bootstrap"
sh -n "$hswm_container_entrypoint"

echo 'Dev Container static isolation checks passed.'
