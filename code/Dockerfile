# Claude Skill Sandbox Docker Image
# Used for dynamic execution of skills in isolated environment
#
# BUILD OPTIONS:
#   NOVA_MODE=full  - Install NOVA with full ML dependencies (torch, transformers, etc.)
#   NOVA_MODE=lite  - Install NOVA hooks without ML dependencies (pattern matching only)
#   NOVA_MODE=none  - Don't install NOVA (default)
#
# Usage:
#   docker build --build-arg NOVA_MODE=full -t claude-skill-sandbox .
#   docker build --build-arg NOVA_MODE=lite -t claude-skill-sandbox .
#   docker build -t claude-skill-sandbox .

FROM python:3.10-slim

# Build arguments for NOVA installation
ARG NOVA_MODE=none

# Install system dependencies (merged layers for faster build)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        strace \
        tcpdump \
        curl \
        wget \
        git \
        sudo \
        file \
        procps \
        iputils-ping \
        net-tools \
        jq \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Install Node.js 18.x (required by Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI via npm (not pip)
RUN npm install -g @anthropic-ai/claude-code

# Set up working directory
WORKDIR /app

# Install NOVA based on mode
RUN if [ "$NOVA_MODE" != "none" ]; then \
    echo "Installing NOVA (mode: $NOVA_MODE)..."; \
    mkdir -p /opt/nova-protector/nova_hooks; \
    fi

# Copy NOVA requirements (only used in full mode)
COPY nova-requirements.txt /tmp/nova-requirements.txt
RUN if [ "$NOVA_MODE" = "full" ]; then \
    echo "Installing NOVA ML dependencies (this may take a while)..."; \
    pip install --no-cache-dir -i https://pypi.org/simple -r /tmp/nova-requirements.txt; \
    fi

# Copy NOVA hooks (installed in lite and full modes)
COPY executor/nova-hooks/ /opt/nova-protector/nova_hooks/
RUN if [ "$NOVA_MODE" != "none" ]; then \
    chmod +x /opt/nova-protector/nova_hooks/*.py; \
    echo "$NOVA_MODE" > /opt/nova-protector/nova_mode; \
    fi

# Copy local NOVA package if exists (optional, for development)
# COPY executor/nova-package/ /opt/nova-protector/nova/

# Setup user and permissions
RUN useradd -m -s /bin/bash appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app && \
    if [ "$NOVA_MODE" != "none" ]; then \
    chown -R appuser:appuser /opt/nova-protector; \
    fi

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/nova-protector/nova_hooks:$PATH"

# NOVA mode indicator
ENV NOVA_MODE=${NOVA_MODE}

# Switch to non-root user
USER appuser

# Default command
CMD ["/bin/bash"]
