FROM --platform=linux/amd64 python@sha256:59a32f2866470624edbdde0e3e504bbbf46222fed2d4c2392bef3894e1b6334d

LABEL org.opencontainers.image.title="HSWM pinned development environment" \
      org.opencontainers.image.source="https://github.com/gj3447/HSWM"

# Node's signed 24.13.0 release manifest records this exact archive digest.
ADD --checksum=sha256:6223aad1a81f9d1e7b682c59d12e2de233f7b4c37475cd40d1c89c42b737ffa8 \
    https://nodejs.org/download/release/v24.13.0/node-v24.13.0-linux-x64.tar.gz \
    /tmp/node-v24.13.0-linux-x64.tar.gz
RUN mkdir -p /opt/node \
    && tar -xzf /tmp/node-v24.13.0-linux-x64.tar.gz --strip-components=1 -C /opt/node \
    && rm /tmp/node-v24.13.0-linux-x64.tar.gz \
    && ln -s /opt/node/bin/node /usr/local/bin/node \
    && ln -s /opt/node/bin/npm /usr/local/bin/npm \
    && ln -s /opt/node/bin/npx /usr/local/bin/npx \
    && test "$(node --version)" = "v24.13.0" \
    && test "$(npm --version)" = "11.6.2" \
    && printf '%s  %s\n' \
      '53fb205ae78805130177e24bcb459a69a1518c8d98f8965f31d85aae7ea840fc' \
      /opt/node/bin/node | sha256sum --check --strict

# This is the official astral-sh/uv 0.12.3 GitHub release artifact.
ADD --checksum=sha256:600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101 \
    https://github.com/astral-sh/uv/releases/download/0.12.3/uv-x86_64-unknown-linux-gnu.tar.gz \
    /tmp/uv-x86_64-unknown-linux-gnu.tar.gz
RUN tar -xzf /tmp/uv-x86_64-unknown-linux-gnu.tar.gz -C /tmp \
    && install -m 0755 /tmp/uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/uv \
    && rm -rf /tmp/uv-x86_64-unknown-linux-gnu /tmp/uv-x86_64-unknown-linux-gnu.tar.gz \
    && case "$(uv --version)" in "uv 0.12.3"*) ;; *) exit 1;; esac \
    && groupadd --gid 1000 hswm \
    && useradd --uid 1000 --gid hswm --create-home --shell /bin/bash hswm \
    && mkdir -p /home/hswm/.cache/uv /home/hswm/.cache/npm \
    && chown -R hswm:hswm /home/hswm

ENV PATH="/opt/node/bin:${PATH}" \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

COPY entrypoint.sh /usr/local/bin/hswm-devcontainer-entrypoint
RUN chmod 0755 /usr/local/bin/hswm-devcontainer-entrypoint

# The entrypoint temporarily starts as root only to assign private volume trees
# to hswm. It then drops to hswm before the command.
ENTRYPOINT ["/usr/local/bin/hswm-devcontainer-entrypoint"]
USER root
