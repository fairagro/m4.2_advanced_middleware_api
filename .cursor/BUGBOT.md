# Bugbot

You are the **Finder** in
[docs/ai_review_policy.md](../docs/ai_review_policy.md). Follow that file
(Finder instructions, severity table, types). `.cursor/rules/` do not apply.

Report only reachable bugs. Each comment: severity + path sentence. Skip
style, `None`-guards, type widening, and helpers with one call site.
