# CI/CD Workflows — Design

## Workflow Overview

```text
On PR → main:
    pull-request-tests.yml
        ├─→ python-quality.yml    (reusable)
        └─→ docker-build.yml      (reusable, push=false)

On workflow_dispatch (Docker release):
    docker-release.yml
        ├─→ docker-build.yml      (reusable, push=true)
        └─→ Trivy scan → SARIF upload

On workflow_dispatch (Helm release):
    helm-release.yml
        └─→ package + publish chart

On push feature/* or schedule:
    codeql.yml
        └─→ CodeQL Python analysis
```

## Reusable Workflows

`python-quality.yml` and `docker-build.yml` are defined as `workflow_call`
workflows. They accept a `run_tests` boolean so the PR orchestrator can skip
them without duplicating the skip logic inside each workflow.

## Key Decisions

1. **Change detection before running jobs**
   — The PR workflow uses `dorny/paths-filter` to detect whether any relevant
   files changed. If only docs or config unrelated to code changed, all jobs
   are skipped. This avoids unnecessary CI minutes and keeps PRs for
   documentation fast.

2. **Reusable workflows for quality and build**
   — `python-quality.yml` and `docker-build.yml` are called both from the PR
   workflow and from `docker-release.yml`. Keeping them as separate reusable
   workflows avoids duplication and ensures the same checks run in PR and
   release pipelines.

3. **GitVersion for semantic versioning**
   — Versions are derived automatically from Git tags using GitVersion
   (`ContinuousDeployment` mode). The tag prefix differs between Docker
   (`.*-docker-v`) and Helm (`.*-chart-v`) releases so each artifact has an
   independent version history.

4. **Branch strategy: `main` = final release, `feature/*` = pre-release**
   — Releases from `main` produce `MAJOR.MINOR.PATCH` versions and create
   GitHub Releases. Releases from `feature/*` branches produce semver
   pre-release versions (label = branch suffix) and do not create a GitHub
   Release. This allows testing release artifacts from feature branches
   without polluting the release history.

5. **Container structure tests before push**
   — The Docker image is built and tested with `container-structure-test`
   before any push to the registry. A broken image is never published.

6. **Trivy scan after push**
   — Trivy runs against the pushed image (by digest) rather than the local
   build artifact. This catches vulnerabilities in the final published layer
   and uploads SARIF results to GitHub Security for tracking over time.

7. **Bandit low-severity findings do not block the build**
   — Low-severity findings are reported in the job summary but do not fail the
   workflow. Medium and higher findings fail the build. This matches the
   `--ll` flag used in local development (`bandit -ll`).

8. **CodeQL runs on feature branches and weekly**
   — Running on every `feature/*` push catches vulnerabilities early in the
   development cycle. The weekly schedule catches newly published CVEs even
   when the codebase has not changed.
