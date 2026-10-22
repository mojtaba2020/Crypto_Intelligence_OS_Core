# Security Policy

## Public repository rules

- Never commit API keys, access tokens, passwords, private keys, seed phrases, cookies, or private credentials.
- Keep runtime credentials in GitHub encrypted secrets or local environment variables.
- Do not commit local SQLite databases or generated research artifacts unless they are intentionally reviewed for public release.
- Treat workflow artifacts as public when produced by this public repository; upload only reproducible research outputs that contain no credentials or personal data.
- If a secret is ever committed, removing it in a later commit is not sufficient. Revoke/rotate the credential immediately and then clean repository history if necessary.

## Research integrity

Security fixes must not silently alter preregistered model parameters, datasets, thresholds, statistical gates, or confirmatory decisions. Scientific changes require an explicit research record separate from security maintenance.
