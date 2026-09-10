# Adopt Devinfra Wave C — Tasks

## 1. Planning

- [x] 1.1 OpenSpec change `adopt-devinfra-wave-c` (`skip_specs: true`)
- [x] 1.2 Issue branch `issue-368-adopt-devinfra-wave-c` from `main`

## 2. Bake product-app layout

- [x] 2.1 Keep/verify `docker/Dockerfile.product-app.base` verbatim (synced; no hand-edits)
- [x] 2.2 Add root `docker-bake.hcl` (target `api` + `api-wheels` / `api-base`)
- [x] 2.3 Replace `docker/Dockerfile.api` with thin Alpine last stage (runtime apk +
      git config + HEALTHCHECK; COPY from `export_bins`)
- [x] 2.4 Smoke `docker buildx bake api` (pins from `versions.env`)
- [x] 2.5 Wire CST: `CST_BAKE_TARGET=api`; remove Wave B `load-env` CST `SKIP` block

## 3. CI callers → Devinfra

- [x] 3.1 Add TEMP `.github/workflows/reusable-check-local.yml` (omit licence; #74)
- [x] 3.2 Update `feature-pull-request.yml` (keep detect-changes; CQ SHA-pin #72;
      build/release `@main`; check → local)
- [x] 3.3 Update `pre-release.yml` / `release.yml` same overlays + `image_base_name`
- [x] 3.4 Thin `helm-pre-release.yml` / `helm-release.yml` → Devinfra helm reusables
- [x] 3.5 Delete local `reusable-{code-quality,check,build,release}.yml`

## 4. Docs / agents

- [x] 4.1 Update `AGENTS.md` for Bake / Devinfra callers / TEMP check / drop CST SKIP note

## 5. Verify / PR

- [x] 5.1 Focused smoke (bake + CST on `middleware-api:wave-c-test`); pause for user commit/push
- [ ] 5.2 Draft PR `Fixes #368` after real commits
