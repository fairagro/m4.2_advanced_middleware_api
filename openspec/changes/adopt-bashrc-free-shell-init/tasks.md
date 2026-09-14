## 1. Product env overlay

- [ ] 1.1 Add `.devcontainer/product.env` with `MYPYPATH` (same colon list as former `load-env.sh` / CQ `mypy_path`) and `CST_BAKE_TARGET=api`
- [ ] 1.2 Confirm file is listed under `overlays` / `exclude` in `docs/synced-paths.yaml` (no sync overwrite)

## 2. Drop load-env

- [ ] 2.1 Delete `scripts/load-env.sh`
- [ ] 2.2 Grep for `load-env.sh` / `setup-bashrc-load-env` outside `openspec/changes/archive/` and fix remaining product references

## 3. Product docs

- [ ] 3.1 Update `AGENTS.md`: remove bashrc/postStart/load-env structure and hook docs; point at `product.env` + `scripts/bin` + postCreate decrypt
- [ ] 3.2 Update `README.md` (and `docs/python_related.md` / brief code comments) to stop telling users to source `load-env.sh`

## 4. Verify

- [ ] 4.1 Spot-check: synced `devcontainer.json` has `.venv/bin` + `scripts/bin` on `remoteEnv.PATH` and no `postStartCommand`
- [ ] 4.2 Spot-check: `scripts/bin/{k,d}` exist; postCreate still documents decrypt of `.env.integration.enc`
- [ ] 4.3 Do **not** hand-edit allowlisted synced paths (`.devcontainer/devcontainer.json`, Compose, `docs/devcontainer.md`, etc.)
