# Shared Dev Container Dockerfile for m4.2 middleware Devinfra + product sync.
# Tool versions come from repo-root versions.env (via docker-compose.yml build args).

ARG DEVCONTAINER_BASE_IMAGE
# hadolint ignore=DL3006
FROM ${DEVCONTAINER_BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG PYTHON_VERSION
ARG UV_VERSION
ARG KUBECTL_VERSION
ARG HELM_VERSION
ARG MINIKUBE_VERSION
ARG SOPS_VERSION
ARG AGE_VERSION
ARG STARSHIP_VERSION
ARG YQ_VERSION
ARG XQ_VERSION
ARG YAMLFMT_VERSION
ARG HADOLINT_VERSION
ARG CST_VERSION
ARG TRIVY_VERSION
ARG RENOVATE_VERSION
ARG NODE_VERSION
ARG OPENSPEC_VERSION
ARG PRETTIER_VERSION
ARG MARKDOWNLINT_CLI2_VERSION

ENV DEBIAN_FRONTEND=noninteractive

# ── Base packages ─────────────────────────────────────────────────────────────
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    wget \
    gnupg \
    lsb-release \
    vim \
    jq \
    bash-completion \
    default-jre-headless \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# ── GitHub CLI (APT repos) ────────────────────────────────────────────────────
# hadolint ignore=DL3008
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | gpg --batch --yes --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends \
        gh \
    && rm -rf /var/lib/apt/lists/*

# ── kubectl (pinned release binary; matches versions.env exactly) ─────────────
RUN curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
        -o /usr/local/bin/kubectl && chmod +x /usr/local/bin/kubectl

# ── Helm ──────────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
        | tar -xz --strip-components=1 -C /usr/local/bin linux-amd64/helm

# ── Minikube ──────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/kubernetes/minikube/releases/download/${MINIKUBE_VERSION}/minikube-linux-amd64" \
        -o /usr/local/bin/minikube && \
    chmod +x /usr/local/bin/minikube

# ── uv (Python package manager) ───────────────────────────────────────────────
RUN curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
        | tar -xz --strip-components=1 -C /usr/local/bin uv-x86_64-unknown-linux-gnu/uv uv-x86_64-unknown-linux-gnu/uvx

# ── yq ────────────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" \
        -o /usr/local/bin/yq && chmod +x /usr/local/bin/yq

# ── xq (XML; sibprogrammer/xq) ────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/sibprogrammer/xq/releases/download/${XQ_VERSION}/xq_${XQ_VERSION#v}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin xq && chmod +x /usr/local/bin/xq

# ── yamlfmt ───────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/google/yamlfmt/releases/download/${YAMLFMT_VERSION}/yamlfmt_${YAMLFMT_VERSION#v}_Linux_x86_64.tar.gz" \
        | tar -xz -C /usr/local/bin yamlfmt

# ── hadolint ──────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/hadolint/hadolint/releases/download/${HADOLINT_VERSION}/hadolint-Linux-x86_64" \
        -o /usr/local/bin/hadolint && chmod +x /usr/local/bin/hadolint

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

# ── Trivy ─────────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/aquasecurity/trivy/releases/download/${TRIVY_VERSION}/trivy_${TRIVY_VERSION#v}_Linux-64bit.tar.gz" \
        | tar -xz -C /usr/local/bin trivy && chmod +x /usr/local/bin/trivy

# ── Node.js (official binary tarball) ─────────────────────────────────────────
RUN curl -fsSL "https://nodejs.org/dist/${NODE_VERSION}/node-${NODE_VERSION}-linux-x64.tar.xz" \
        | tar -xJ --strip-components=1 -C /usr/local \
            "node-${NODE_VERSION}-linux-x64/bin" \
            "node-${NODE_VERSION}-linux-x64/include" \
            "node-${NODE_VERSION}-linux-x64/lib" \
            "node-${NODE_VERSION}-linux-x64/share" && \
    node --version && npm --version

# ── OpenSpec + Markdown + Renovate (global; bind-mount would hide local node_modules)
RUN npm install -g \
        "@fission-ai/openspec@${OPENSPEC_VERSION}" \
        "prettier@${PRETTIER_VERSION}" \
        "markdownlint-cli2@${MARKDOWNLINT_CLI2_VERSION}" \
        "renovate@${RENOVATE_VERSION}" && \
    openspec --version && \
    prettier --version && \
    markdownlint-cli2 --version && \
    renovate --version

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
# Literal $(…) / ${…} must reach bashrc at runtime (not expand at image build).
# hadolint ignore=SC2016
RUN echo 'eval "$(starship init bash)"' >> /etc/bash.bashrc

# ── Shell history persistence (volume-backed; filter agent/bootstrap noise) ──
# Cursor/VS Code agent shells dump dozens of `set +/-o …` lines into HISTFILE.
# With default HISTFILESIZE=500 those crowd out real commands after a restart.
# HISTIGNORE drops that noise; larger size + erasedups keep useful history.
# Avoid Dockerfile heredoc: hadolint 2.12 cannot parse <<EOF (IDE toast: "unexpected…").
# hadolint ignore=SC2016
RUN mkdir -p /commandhistory && \
    touch /commandhistory/.bash_history && \
    chown -R vscode /commandhistory && \
    { \
      echo '# Persistent bash history (/commandhistory volume)'; \
      echo 'export HISTFILE=/commandhistory/.bash_history'; \
      echo 'export HISTSIZE=100000'; \
      echo 'export HISTFILESIZE=100000'; \
      echo 'export HISTCONTROL=ignoreboth:erasedups'; \
      echo "# Ignore IDE/agent shell-option bootstrap (set +/-o …) and trivial builtins"; \
      echo "export HISTIGNORE='set *:unset *:shopt *:history *:exit:clear'"; \
      echo 'shopt -s histappend'; \
      echo '# Append after each command so kill/rebuild does not lose the session'; \
      echo 'PROMPT_COMMAND="history -a${PROMPT_COMMAND:+; ${PROMPT_COMMAND}}"'; \
    } >> /etc/bash.bashrc

# ── Switch to non-root user for uv tool installations
USER vscode

# ── Python (via uv; patch pin from versions.env → PYTHON_VERSION build-arg) ───
RUN uv python install "${PYTHON_VERSION}"
