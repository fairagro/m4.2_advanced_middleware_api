# Design

## Context

See `proposal.md` — Why. Explore lock-in for #617: **A1 + C** — implement on catalog materialize (not extract); set
`url` as `{"@id": text}`; **consume** the Landing Page Comment. Finalize pipeline remains
`extract → materialize → JSON-LD normalize`.

## Goals / Non-Goals

**Goals:**

- Publish Dataset `url` from Comment `Landing Page` when `url` is unset.
- Keep compact output on the `url` term via `@id` IRI shape.
- Align Comment handling with other first-class maps (consume opaque Comment).

**Non-Goals:**

- Changing `extract_catalog_dataset`.
- Overwriting DOI-or-other existing `url`.
- Harvester plugins / CouchDB / per-ARC Git content.

## Decisions

### 1. Materialize hook (not extract)

Extend `_consume_mapped_comment` (or adjacent) in `catalog_materialize.py` for name key `landing page`. Extract stays a
literal Dataset copy; Search Hub only sees post-materialize dumps.

**Alternative:** extract-time rewrite — rejected (wrong layer).

### 2. Consume the Comment (lock-in C)

Return `True` from the consume path after setting `url`, so the Comment is omitted from Dataset `comment` — same as
Keywords / Language. ARC bodies in CouchDB and per-ARC Git are unchanged (materialize copies only).

**Alternative:** keep opaque Comment (issue body) — rejected by lock-in C; Catalog dump should not duplicate the URI as
comment text once `url` is first-class.

### 3. `@id` IRI shape (lock-in A1)

When setting `url`, use `{"@id": text_str}` (non-empty text). Matches Organization `url` compact behaviour.

**Alternative:** plain string — rejected for compact risk (`schema:url`).

### 4. Existing `url` wins; always consume on name match

- Name matches `landing page` (casefold).
- If `url` absent and `text` non-empty → set `url` to `{"@id": text}`.
- If `url` already present → leave `url` unchanged.
- Always consume the Comment when the name matches (including empty `text` or pre-existing `url`), so known Landing Page
  Comments never remain opaque in the catalog dump.

## Risks / Trade-offs

- **[Risk]** ARCs that already put DOI in Dataset `url` will not get the Landing Page as `url` → Mitigation: documented
  in #552/#617; separate DOI vs landing page is harvester/ARC concern.
- **[Trade-off]** Consuming the Comment diverges from the issue body’s “keep comment” line — explicit explore lock-in C.

## Migration Plan

- Pure catalog-shape change on next finalize; re-finalize RDIs to refresh dumps.
- Rollback: revert PR.

## Open Questions

_None — A1+C locked._
