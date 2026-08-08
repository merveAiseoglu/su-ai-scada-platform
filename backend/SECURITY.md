# Security Policy

This document outlines the security mechanisms implemented in the Su-AI backend to protect the API, data, and users.

## 1. Secret Management
- **No Hardcoded Secrets**: All sensitive configurations (JWT secret keys, OpenAI API keys, database URLs) MUST be loaded from environment variables (e.g., via a `.env` file in development).
- **Git Ignore**: The `.env` file is explicitly ignored in `.gitignore`. A `.env.example` file is provided with placeholder values to safely share the required configuration keys with new developers.

## 2. Authentication & Authorization (RBAC)
- **JWT (JSON Web Tokens)**: Authentication is handled via short-lived access tokens (default 30 mins) and long-lived refresh tokens (default 7 days).
- **Token Revocation (Blocklisting)**: Logging out adds the token's unique ID (`jti`) to a PostgreSQL database table (`TokenBlocklist`), rendering it invalid immediately. The same is done for refresh tokens upon rotation.
- **Roles**:
  - `saha_personeli`: Can read/write telemetry data, create measurements, and view dashboard read-only endpoints.
  - `yonetici` (Admin): Has full access, including managing stations, viewing system-wide audit logs, and triggering simulations.

## 3. Rate Limiting
To prevent abuse, resource exhaustion (DoS), and brute-force attacks, the backend uses `slowapi`:
- **Global API Rate Limit**: Default `100/minute` (configurable via `GLOBAL_RATE_LIMIT`).
- **Auth/Login Endpoints**: Stricter limit of `5/minute` (configurable via `AUTH_RATE_LIMIT`) applied to `/token` and `/refresh` to thwart credential stuffing and brute force attempts.

## 4. Middleware & Headers
- **CORS (Cross-Origin Resource Sharing)**: Allowed origins are strictly read from the `ALLOWED_ORIGINS` environment variable. The wild-card `*` origin is disabled in production to mitigate CSRF-style cross-origin attacks.
- **Security Headers**: Standard headers are injected into every response:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`

## 5. Input Validation
- **Defense in Depth**: Pydantic schemas enforce bounds on all numerical telemetry inputs (e.g., pH is bounded between 0 and 14). This prevents massive anomalous payloads from being parsed and processed by the rule engine.

## 6. Audit Logging
- **Append-Only**: All critical operations (Login, creating stations, modifying rules, submitting telemetry) log an entry to the `audit_logs` table.
- **Retention**: Audit logs are retained for 2 years as per KVKK requirements and cannot be deleted or modified through the API.

## 7. Responsible Disclosure
If you discover a security vulnerability in this project, please report it privately. Do NOT file a public issue.
- **Contact**: security@suski.gov.tr
