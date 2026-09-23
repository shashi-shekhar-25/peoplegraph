# Security

PeopleGraph processes employee data, so privacy bugs are security bugs.

## Report privately

Use GitHub's private vulnerability reporting:
**Security → Report a vulnerability** on this repository. Do not open a public
issue, and do not include real employee data in the report.

You should hear back within five working days.

## In scope

- Any path by which loaded data leaves the machine (network calls, telemetry,
  files written outside what the user chose).
- Injection through a crafted CSV (HTML or script reaching the page, SQL
  reaching DuckDB).
- Name masking or HRBP scoping that can be bypassed without it being logged.

## Out of scope

- Attacks that need the attacker already to control the user's machine or
  Python environment.
- Findings in a local Ollama server itself.

## Supported versions

Only the latest commit on `main`.
