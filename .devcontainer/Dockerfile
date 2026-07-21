# Dev Container Dockerfile for advanced-middleware-api
# Replaces devcontainer feature-based installation with a reproducible Dockerfile.
#
# All tool versions are pinned for reproducibility.

FROM mcr.microsoft.com/devcontainers/base:2.1.11-trixie

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG KUBECTL_VERSION=v1.36.1
ARG HELM_VERSION=v4.2.0
ARG UV_VERSION=0.11.19
ARG SOPS_VERSION=v3.10.2
ARG AGE_VERSION=v1.3.1
ARG STARSHIP_VERSION=v1.25.1
ARG DIFFTASTIC_VERSION=0.69.0
ARG PRECOMMIT_VERSION=4.6.0
ARG YQ_VERSION=v4.48.1
ARG YAMLFMT_VERSION=v0.14.0
ARG HADOLINT_VERSION=v2.12.0
ARG CST_VERSION=v1.19.1
ARG MINIKUBE_VERSION=v1.37.0

ENV DEBIAN_FRONTEND=noninteractive

# ── Base packages ─────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    wget \
    gnupg \
    lsb-release \
    vim \
    git-lfs \
    jq \
    bash-completion \
    default-jre-headless \
    graphviz \
    && git lfs install --system \
    && rm -rf /var/lib/apt/lists/*

# ── GitHub CLI (APT repos) ─────────────────────────────────────
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | gpg --batch --yes --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends \
        gh \
    && rm -rf /var/lib/apt/lists/*

# ── kubectl (Kubernetes APT repo) ────────────────────────────────────────────
RUN KUBECTL_MINOR=$(echo "${KUBECTL_VERSION}" | grep -oP 'v\d+\.\d+') && \
    curl -fsSL "https://pkgs.k8s.io/core:/stable:/${KUBECTL_MINOR}/deb/Release.key" \
        | gpg --batch --yes --dearmor -o /usr/share/keyrings/kubernetes-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${KUBECTL_MINOR}/deb/ /" \
        > /etc/apt/sources.list.d/kubernetes.list && \
    apt-get update && apt-get install -y --no-install-recommends kubectl \
    && rm -rf /var/lib/apt/lists/*

# ── Helm ──────────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
        | tar -xz --strip-components=1 -C /usr/local/bin linux-amd64/helm

# ── Minikube ─────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/kubernetes/minikube/releases/download/${MINIKUBE_VERSION}/minikube-linux-amd64" \
        -o /usr/local/bin/minikube && \
    chmod +x /usr/local/bin/minikube

# ── uv (Python package manager) ──────────────────────────────────────────────
RUN curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
        | tar -xz --strip-components=1 -C /usr/local/bin uv-x86_64-unknown-linux-gnu/uv uv-x86_64-unknown-linux-gnu/uvx

# ── yq ────────────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" \
        -o /usr/local/bin/yq && chmod +x /usr/local/bin/yq

# ── yamlfmt ───────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/google/yamlfmt/releases/download/${YAMLFMT_VERSION}/yamlfmt_${YAMLFMT_VERSION#v}_Linux_x86_64.tar.gz" \
        | tar -xz -C /usr/local/bin yamlfmt

# ── hadolint ──────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/hadolint/hadolint/releases/download/${HADOLINT_VERSION}/hadolint-Linux-x86_64" \
        -o /usr/local/bin/hadolint && chmod +x /usr/local/bin/hadolint

# ── difftastic ────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/Wilfred/difftastic/releases/download/${DIFFTASTIC_VERSION}/difft-x86_64-unknown-linux-gnu.tar.gz" \
        | tar -xz -C /usr/local/bin

# ── SOPS ──────────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/getsops/sops/releases/download/${SOPS_VERSION}/sops-${SOPS_VERSION}.linux.amd64" \
        -o /usr/local/bin/sops && chmod +x /usr/local/bin/sops

# ── age ───────────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/FiloSottile/age/releases/download/${AGE_VERSION}/age-${AGE_VERSION}-linux-amd64.tar.gz" \
        | tar -xz --strip-components=1 -C /usr/local/bin age/age age/age-keygen

# ── Starship prompt ───────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/starship/starship/releases/download/${STARSHIP_VERSION}/starship-x86_64-unknown-linux-gnu.tar.gz" \
        | tar -xz -C /usr/local/bin

# ── container-structure-test ──────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/GoogleContainerTools/container-structure-test/releases/download/${CST_VERSION}/container-structure-test-linux-amd64" \
        -o /usr/local/bin/container-structure-test && \
    chmod +x /usr/local/bin/container-structure-test && \
    ln -sf /usr/local/bin/container-structure-test /usr/local/bin/cst

# ── Bash completions (build-time, lazy-loaded via bash-completion) ───────────
RUN mkdir -p /usr/share/bash-completion/completions && \
    gh completion -s bash > /usr/share/bash-completion/completions/gh && \
    kubectl completion bash > /usr/share/bash-completion/completions/kubectl && \
    helm completion bash > /usr/share/bash-completion/completions/helm && \
    minikube completion bash > /usr/share/bash-completion/completions/minikube && \
    uv generate-shell-completion bash > /usr/share/bash-completion/completions/uv && \
    ln -sf /usr/share/bash-completion/completions/uv /usr/share/bash-completion/completions/uvx && \
    yq shell-completion bash > /usr/share/bash-completion/completions/yq && \
    starship completions bash > /usr/share/bash-completion/completions/starship

# ── Shell init (must run each session; not installable as static completions) ─
RUN echo 'eval "$(starship init bash)"' >> /etc/bash.bashrc

# ── Shell history persistence helper (stuartleeks pattern) ───────────────────
RUN echo 'export HISTFILE=/commandhistory/.bash_history' >> /etc/bash.bashrc && \
    echo 'PROMPT_COMMAND="history -a; $PROMPT_COMMAND"' >> /etc/bash.bashrc && \
    mkdir -p /commandhistory && \
    touch /commandhistory/.bash_history && \
    chown -R vscode /commandhistory

# ── Switch to non-root user for uv tool installations
USER vscode

# ── Python (via uv) ──────────────────────────────────────────────────────────
RUN uv python install 3.12
