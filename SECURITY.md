# RevMatrix Security Policy

## Reporting Vulnerabilities

Please **do not** open public issues for security vulnerabilities.

Email: revmatrixai@gmail.com with subject: `[SECURITY] Your finding`

We respond within 48 hours.

## Security Practices in This Repo

- No API keys, tokens, or secrets in code — environment variables only
- All inputs sanitized before processing
- Rate limiting on all endpoints
- Non-root Docker containers
- Automated Trivy scanning on every PR
- Gitleaks scans for accidental secret commits
- Read-only root filesystem in containers
- Network policies restrict inter-pod traffic

## Demo Safety Boundaries

The cybersecurity scanner demo is **restricted to localhost/private networks only**.
Scanning external hosts without permission is illegal. This code includes guards
to prevent accidental misuse.

## Responsible Disclosure

If you find a security issue in any of our demos, we appreciate responsible disclosure.
We will acknowledge and credit you (if desired) after patching.
