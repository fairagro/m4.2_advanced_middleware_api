<!-- ccr-overview-v2 -->

## Copilot review overview

### 🔵 Needs a closer look

The updated MyCoRe Solr spec and the example YAML contain documentation inconsistencies that should be corrected to
avoid misleading operators and to keep the spec internally consistent.

**Review effort:** Lite **Findings:** None

<details>
<summary><strong>Resolved since last review (1)</strong></summary>

- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture>
  [DCAT-AP parsing ignores configured JSON-LD threshold](#discussion_r4154872341)

</details>

<details>
<summary><strong>Previously missed (2)</strong></summary>

In code that hasn't changed since last review

<details>
<summary><picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.png" alt="Low severity" width="62" height="18" align="texttop"></picture> Misindented MyCoRe Solr example places parser/mapper under generic</summary>

`dev_environment/​config_example.yaml:48`

In the commented MyCoRe Solr example, `parser:` and `mapper:` are indented under `generic:`. In the actual config
schema, `parser`/`mapper` are repository-level siblings of `generic` (as shown in the `edal` example above), so this
example would mislead operators when they copy/paste it.
</details>

<details>
<summary><picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.png" alt="Low severity" width="62" height="18" align="texttop"></picture> Spec still refers to sitemap_url after renaming canonical field to entry_url</summary>

`openspec/​specs/​sitemap-mycore-solr/​spec.md:15`

This spec now states that the canonical configuration is `generic.protocol.mycore_solr.entry_url`, but the remaining
requirements below still describe behavior in terms of `sitemap_url` (e.g., “Accept … in sitemap_url”, “When sitemap_url
has no query string”, etc.). That makes the spec internally inconsistent after this update; please update the remaining
requirement titles/text to refer to `entry_url` (with `sitemap_url` only mentioned as the deprecated lifted alias where
applicable).
</details>
</details>
