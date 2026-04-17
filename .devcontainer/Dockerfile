FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash dev

USER dev

RUN curl -fsSL https://claude.ai/install.sh | bash \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# claude-dev wrapper: claude with --dangerously-skip-permissions
RUN mkdir -p /home/dev/.local/bin \
    && printf '#!/bin/sh\nexec /home/dev/.local/bin/claude --dangerously-skip-permissions "$@"\n' \
       > /home/dev/.local/bin/claude-dev \
    && chmod +x /home/dev/.local/bin/claude-dev \
    && printf 'alias claude=claude-dev\nalias cc=claude-dev\n' \
       > /home/dev/.bash_aliases

ENV PATH="/home/dev/.local/bin:/home/dev/.cargo/bin:$PATH"
