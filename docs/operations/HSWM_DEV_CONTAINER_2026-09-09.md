# HSWM Dev Container

2026-09-09 · `SECONDARY_AI / LOCAL_ENGINEERING_GUIDE`.

This optional environment makes the current native TypeScript/Effect route and
scoped Python checks reproducible on Linux `amd64`. It is a developer tool, not
an HSWM canonical state, admission path, causal-credit result, or evidence of
continuous-learning efficacy. The target and claim ceilings remain those of the
[HSWM Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md).

The configuration follows the published [Dev Container JSON reference](https://containers.dev/implementors/json_reference/)
and uses its Dockerfile build form. It deliberately has no Features, extensions,
Docker socket, host network, privileged mode, credential forwarding, or automatic
tool installation beyond the pinned build inputs.

## Pinned inputs and boundary

`.devcontainer/Dockerfile` starts from the Docker Official Image
`python:3.12.13-bookworm` for Linux amd64 at
`sha256:59a32f2866470624edbdde0e3e504bbbf46222fed2d4c2392bef3894e1b6334d`.
It downloads only the official Node `24.13.0` Linux x64 and uv `0.12.3` release
archives, each guarded by Docker `ADD --checksum`. Node's executable also has the
same SHA-256 check used by the current CI, and the Docker build and bootstrap
verify Node, npm, Python, Unicode-data, and uv versions. Exact source URLs,
digests, licenses, and authority classes are in
[`source-pins.v1.json`](../../src/hswm/development/container/source-pins.v1.json).

The base image uses the Python/Debian license notices supplied with that Docker
Official Image. Node is MIT with bundled notices, npm is Artistic-2.0, and uv is
MIT OR Apache-2.0. Package dependencies remain pinned by the existing
`uv.lock`, graph-runtime `uv.lock`, and Effect-runtime `package-lock.json`.

The Docker build context is `.devcontainer`, not the repository root. Its
Dockerfile-specific ignore file further sends only `entrypoint.sh` (plus the
Dockerfile and ignore file that Docker itself needs). Thus `.hswm-local`,
ignored credentials, model caches, dependency trees, and the rest of the
repository are absent from the **build** context. This does not change the
separate runtime bind-mount boundary described below.

The container's command and development terminals run as the unprivileged
`hswm` user. A brief root entrypoint assigns the private volume trees to that
user, then drops privileges. The checkout is a bind mount, so its
arbitrary files—including any ignored credential or model-cache file a user has
put inside the checkout—remain visible. There is no separate host-home, SSH,
credential, model-cache, or Docker-socket mount. Do not use this bind-mounted
configuration with a checkout that contains material that must not enter the
container; use a clean clone for that case.

`.hswm-local`, root `.venv`, graph-runtime `.venv`, Effect-runtime
`node_modules`, and Effect-runtime `dist` are private named volumes with
`volume-nocopy`. They mask the corresponding host paths and prevent Docker from
initializing a new volume from pre-existing content. Setup therefore cannot
overwrite those host paths. `UV_LINK_MODE=copy` prevents uv from linking its
cache into a volume-backed environment.

This exact image is intentionally Linux amd64 only. The base-image pin is
platform-specific and both Node and uv archives are x86_64 releases. An arm64
variant needs separately verified image and archive digests; do not emulate this
configuration under a different architecture and call it the same environment.

## Use

Install a Dev Container client and a compatible Docker daemon under your normal
local administration. From the repository root, open the folder with that client
and select **Reopen in Container**. The post-create command verifies the pinned
toolchain, uses the checkout's `hswm-python` wrapper to create separate core and
graph environments with the base Python and no Python download, and builds the
native runtime. It runs the equivalent of:

```sh
src/hswm/development/bin/hswm-python sync
npm --prefix src/hswm/effect-runtime ci --ignore-scripts --no-audit --no-fund
npm --prefix src/hswm/effect-runtime run build
```

Then use the normal repository-relative commands documented in
[the development environment guide](HSWM_DEVELOPMENT_ENVIRONMENT_2026-09-09.md).
For example:

```sh
src/hswm/effect-runtime/bin/hswm-dev hswm plan --focus runtime
npm --prefix src/hswm/effect-runtime run check
```

The named volumes retain private local state and build/dependency outputs across
a container rebuild. Their names include the standard `${devcontainerId}`, which
is unique to a Dev Container on one Docker host and stable across its rebuilds;
independent checkouts therefore do not share dependency or local-state volumes.
Remove the five volumes associated with this Dev Container through the local
container engine when a deliberately clean container state is needed; this does
not alter the host checkout or its `.hswm-local` state.

## Verification status

On 2026-09-09 this checkout has no `docker`, `podman`, `nerdctl`, `buildah`,
`skopeo`, or Dev Container CLI, and no Docker socket, so no image build or
runtime smoke test was possible without installing or starting a container
service. The host permits unprivileged user namespaces and has subuid/subgid
ranges, but lacks the rootless container helpers (`newuidmap`, `newgidmap`,
`slirp4netns`, and `fuse-overlayfs`); this is insufficient to represent a
rootless engine as ready. JSON, shell syntax, pins, official registry/release
metadata, and the static isolation regression check are verified. An actual
build remains required before representing the container as live-tested.
