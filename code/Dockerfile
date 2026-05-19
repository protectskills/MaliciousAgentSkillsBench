# Claude Skill Sandbox Docker Image
# Used for dynamic execution of skills in isolated environment
#
# BUILD OPTIONS:
#   NOVA_MODE=full  - Install real Nova-tracer plus nova-hunting scanner dependencies
#   NOVA_MODE=lite  - Install real Nova-tracer recording hooks without scanner dependencies
#   NOVA_MODE=none  - Don't install NOVA (default)
#   NODE_MAJOR      - Node.js major version for Claude Code CLI (default: 22)
#   NOVA_TORCH_SPEC / NOVA_TORCH_INDEX_URL - Override torch wheel selection for full mode
#
# Usage:
#   docker build --build-arg NOVA_MODE=full -t claude-skill-sandbox .
#   docker build --build-arg NOVA_MODE=full --build-arg NOVA_TORCH_INDEX_URL= -t claude-skill-sandbox:full-gpu .
#   docker build --build-arg NOVA_MODE=lite -t claude-skill-sandbox .
#   docker build -t claude-skill-sandbox .

FROM python:3.10-slim-bookworm

# Build arguments for NOVA installation
ARG NOVA_MODE=none
ARG NODE_MAJOR=22
ARG NOVA_TORCH_SPEC="torch>=2.5,<3"
ARG NOVA_TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"

# Configure Chinese mirror sources (fix network issues in China)
RUN rm -f /etc/apt/sources.list.d/debian.sources && \
    echo "Types: deb" > /etc/apt/sources.list.d/debian.sources && \
    echo "URIs: https://mirrors.ustc.edu.cn/debian https://repo.huaweicloud.com/debian" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Suites: bookworm bookworm-updates" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Components: main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.sources && \
    echo "" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Types: deb" >> /etc/apt/sources.list.d/debian.sources && \
    echo "URIs: https://mirrors.ustc.edu.cn/debian-security https://repo.huaweicloud.com/debian-security" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Suites: bookworm-security" >> /etc/apt/sources.list.d/debian.sources && \
    echo "Components: main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.sources

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

# Install Node.js (required by Claude Code CLI)
RUN curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI via npm (not pip)
RUN npm install -g @anthropic-ai/claude-code

# Set up working directory
WORKDIR /app

# Install NOVA based on mode
RUN if [ "$NOVA_MODE" != "none" ]; then \
    echo "Installing NOVA (mode: $NOVA_MODE)..."; \
    mkdir -p /opt/nova-tracer; \
    fi

# Copy NOVA requirements (full mode adds nova-hunting; lite keeps recording only)
COPY nova-requirements.txt /tmp/nova-requirements.txt
RUN if [ "$NOVA_MODE" != "none" ]; then \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pyyaml anthropic; \
    fi
RUN if [ "$NOVA_MODE" = "full" ]; then \
    echo "Installing real NOVA scanner dependencies (this may take a while)..."; \
    if [ -n "$NOVA_TORCH_SPEC" ]; then \
        if [ -n "$NOVA_TORCH_INDEX_URL" ]; then \
            pip install --no-cache-dir --index-url "$NOVA_TORCH_INDEX_URL" "$NOVA_TORCH_SPEC"; \
        else \
            pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple "$NOVA_TORCH_SPEC"; \
        fi; \
    fi; \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/nova-requirements.txt; \
    fi

# Copy real Nova-tracer runtime.
COPY executor/nova-tracer/ /opt/nova-tracer/
RUN if [ "$NOVA_MODE" != "none" ]; then \
    chmod +x /opt/nova-tracer/hooks/*.py; \
    echo "$NOVA_MODE" > /opt/nova-tracer/nova_mode; \
    fi

# Setup user and permissions
RUN useradd -m -s /bin/bash appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app && \
    if [ "$NOVA_MODE" != "none" ]; then \
    chown -R appuser:appuser /opt/nova-tracer; \
    fi

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/nova-tracer/hooks:$PATH"

# NOVA mode indicator
ENV NOVA_MODE=${NOVA_MODE}

# Switch to non-root user
USER appuser

# Default command
CMD ["/bin/bash"]
