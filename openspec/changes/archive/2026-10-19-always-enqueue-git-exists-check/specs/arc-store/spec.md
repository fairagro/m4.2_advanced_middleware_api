# Spec Delta

## ADDED Requirements

### Requirement: Lightweight GitLab project existence probe

The GitLab-backed remote provider used by the per-ARC store MUST expose a read-only check that reports whether a project
for a given `arc_id` exists under the configured group and is usable (not pending deletion / not renamed for deletion).
The check MUST use the GitLab HTTP API and MUST NOT run git CLI commands. The check MUST NOT create or modify projects.

#### Scenario: Existing project reports present

- **GIVEN** a GitLab project whose path equals the ARC id under the configured group
- **WHEN** the existence probe runs
- **THEN** it reports that the project exists

#### Scenario: Missing or pending-deletion reports absent

- **GIVEN** no project for the ARC id, or a project marked for deletion / deletion-scheduled path rewrite
- **WHEN** the existence probe runs
- **THEN** it reports that the project does not exist (usable)
