# ARC Store — Delta

## ADDED Requirements

### Requirement: Carry authenticated Git remotes as redacting URL values

When the ArcStore Git backends produce or hold an authenticated HTTP(S) remote
URL (token embedded in userinfo), that value MUST be represented as the shared
redacting URL type. Ordinary string conversion of that value MUST NOT expose
userinfo. Passing the URL to Git CLI / GitPython MUST use the explicit
unredacted accessor. Plain authenticated remote URLs as bare strings MUST NOT be
the default hand-off into logging, tracing attributes, or similar diagnostic
surfaces owned by the store.

#### Scenario: Authenticated remote stringifies without credentials

- **GIVEN** an ArcStore Git backend has built an authenticated HTTPS remote
- **WHEN** that remote is converted with ordinary string conversion for a
  diagnostic attribute or log argument
- **THEN** userinfo credentials are not present in the resulting text

#### Scenario: Git operations receive the unredacted remote

- **GIVEN** an authenticated remote URL value
- **WHEN** a clone, fetch, push, or ls-remote is invoked against that remote
- **THEN** Git receives the full URL including credentials via the explicit
  unredacted accessor
