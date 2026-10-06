# Sandbox for testing Claude Code hooks against real git commands without touching the
# host. Everything is downloaded here, at build time; at run time init-firewall.sh
# leaves only the Anthropic API reachable.
FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl dnsutils git iproute2 ipset iptables sudo \
  && rm -rf /var/lib/apt/lists/*

# Same versions as CI.
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /usr/local/bin/
ARG CHEZMOI_VERSION=v2.70.0
RUN sh -c "$(curl -fsLS get.chezmoi.io)" -- -b /usr/local/bin -t "$CHEZMOI_VERSION"

ARG USERNAME=sandbox
RUN useradd -m -s /bin/bash "$USERNAME"
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod 0755 /usr/local/bin/init-firewall.sh \
  && echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/firewall \
  && chmod 0440 /etc/sudoers.d/firewall

USER $USERNAME
WORKDIR /home/$USERNAME
# workspaceFolder, which lifecycle commands start in; post-create.sh clones into it.
RUN mkdir work
ENV PATH=/home/$USERNAME/.local/bin:$PATH

RUN curl -fsSL https://claude.ai/install.sh | bash

# The repo is bind-mounted from the host, so its owner differs from this user.
RUN git config --global user.name sandbox \
  && git config --global user.email sandbox@example.invalid \
  && git config --global commit.gpgsign false \
  && git config --global init.defaultBranch main \
  && git config --global --add safe.directory '*'

# Fill the uv cache so `uv run --with pytest` works offline.
RUN uv run --no-project --with pytest --with hypothesis python -c "import pytest, hypothesis"
