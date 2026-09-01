# UrlStr — Spec

## Purpose

Provides a shared URL value type that redacts HTTP(S) userinfo on ordinary
stringification while exposing an explicit accessor for the unredacted URL when
Git or other clients must authenticate.

## ADDED Requirements

### Requirement: Redacting stringification for credential-bearing URLs

The shared library SHALL provide a URL value type for credential-bearing HTTP(S)
URLs. Applying the language's ordinary string conversion to such a value MUST
yield a form in which URL userinfo (username and/or password or token) is
replaced so credentials are not visible, while scheme, host, and path remain
recognizable. The type MUST expose an explicit accessor that returns the full
unredacted URL string for authenticated use.

#### Scenario: Default string form hides userinfo

- **GIVEN** a credential-bearing HTTPS URL value containing oauth2 userinfo
- **WHEN** ordinary string conversion is applied
- **THEN** the result does not contain the token or password
- **AND** the result still identifies the host and repository path

#### Scenario: Explicit accessor returns full URL

- **GIVEN** the same credential-bearing URL value
- **WHEN** the explicit unredacted accessor is called
- **THEN** the returned string equals the original authenticated URL including userinfo

### Requirement: Tokens and passwords remain fully secret

Passwords and standalone auth tokens MUST continue to use a fully opaque secret
string type. The URL value type MUST NOT replace that pattern for non-URL secrets.

#### Scenario: Token field stays fully masked

- **GIVEN** a Git auth token stored as a secret string
- **WHEN** ordinary string conversion is applied to the token
- **THEN** the result does not reveal the token value or URL structure
