# CI/CD Workflows

**Scope:** Automated pipelines that validate pull requests, build and publish
Docker images and Helm charts, and scan for security vulnerabilities. All
pipelines run on GitHub Actions.

## Requirements

<!-- Pull Request Validation -->
- [ ] On every pull request targeting `main`, skip all checks when only
      non-code files changed; pass the PR without running CI.
- [ ] On every relevant pull request, verify code quality (formatting, linting,
      type checking, security, tests) and fail the PR if any check fails.
- [ ] On every relevant pull request, build the Docker image and run container
      structure tests; do not push the image to any registry.
- [ ] Cancel any in-progress PR run when a new commit is pushed to the same PR.
- [ ] Publish a job-outcome summary for every PR run.

<!-- Code Quality -->
- [ ] Enforce consistent code formatting; fail when the committed code differs
      from the formatted output.
- [ ] Enforce linting rules; fail on any violation.
- [ ] Enforce a minimum Pylint score; fail when the score falls below the
      configured threshold.
- [ ] Enforce static type correctness; fail on any type error.
- [ ] Scan for security vulnerabilities; fail on medium-severity findings or
      higher; report low-severity findings without failing.
- [ ] Run the full test suite; fail when any test fails.

<!-- Docker Release -->
- [ ] On a manually triggered Docker release, calculate a semantic version from
      Git history and the chosen bump type (`major` / `minor` / `patch`).
- [ ] On `main`, produce a final `MAJOR.MINOR.PATCH` version and create a
      GitHub Release.
- [ ] On a `feature/*` branch, produce a pre-release version; do not create a
      GitHub Release.
- [ ] Run container structure tests before pushing; do not push a broken image.
- [ ] After publishing, scan the released image for vulnerabilities and upload
      results to GitHub Security.

<!-- Helm Chart Release -->
- [ ] On a manually triggered Helm release, calculate a semantic version for
      the chart independently of the Docker image version.
- [ ] Package and publish the Helm chart to the chart repository.
- [ ] Apply the same `main` / `feature/*` version strategy as Docker releases.

<!-- Security Scanning -->
- [ ] Run static security analysis for Python on every push to a `feature/*`
      branch and on a weekly schedule.
- [ ] Upload analysis results to GitHub Security.

## Edge Cases

No relevant files changed in a PR → all checks skipped; PR remains mergeable.

Docker build or container tests fail → image is not pushed to any registry.

Version cannot be calculated from Git history → pipeline fails before build;
no artifact is produced.

Feature branch Docker release → pre-release image published; no GitHub Release
entry created.
