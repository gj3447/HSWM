#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  set -- sleep infinity
fi

for hswm_devcontainer_mount in \
  /workspaces/HSWM/.hswm-local \
  /workspaces/HSWM/.venv \
  /workspaces/HSWM/_research/graph_standards/runtime/.venv \
  /workspaces/HSWM/src/hswm/effect-runtime/node_modules \
  /workspaces/HSWM/src/hswm/effect-runtime/dist
do
  mkdir -p "$hswm_devcontainer_mount"
  chown -R hswm:hswm "$hswm_devcontainer_mount"
done

exec su -s /bin/sh hswm -c 'exec "$0" "$@"' "$@"
