# Su-AI Security Audit Report

**Scan Date:** August 11, 2026
**Tool Used:** OWASP ZAP (zaproxy/zap-stable, Docker image)
**Scan Type:** Full Active Scan (Authenticated via Bearer Token, plus unauthenticated Baseline Scan)
**Target:** Development API Backend (`http://su-ai-backend:8000`)

## 1. Scan Overview
A comprehensive two-phase security audit was conducted against the Su-AI backend:
1. **Baseline Passive Scan:** Spidered the application looking for missing headers, information leaks, and misconfigurations.
2. **Full Active Scan:** Performed an authenticated attack (using an admin token) against the API to attempt SQL Injection (SQLi), Cross-Site Scripting (XSS), Path Traversal, and XML External Entity (XXE) attacks, among others.
   *Note: Endpoints triggering external notifications (emails/pushes) were explicitly excluded from the active scan to prevent spam.*

## 2. Findings Summary
The results of both scans were extremely clean, verifying the robust security features provided out-of-the-box by FastAPI, Pydantic (strict typing), and SQLAlchemy (parameterized queries).

- **Total Passive Tests Passed:** 65
- **Total Active Tests Passed:** 141
- **High / Medium Severity (Failures):** 0
- **Low / Informational (Warnings):** 2

### 2.1 Fixed Findings
- **`WARN-NEW: Cross-Origin-Resource-Policy Header Missing [90004]`**:
  - **Status:** Fixed.
  - **Resolution:** We injected `Cross-Origin-Resource-Policy: same-site` into the custom HTTP middleware in `app/main.py`.

### 2.2 Accepted / Documented Risks
- **`WARN-NEW: Storable and Cacheable Content [10049]`**:
  - **Status:** Accepted Risk (Informational).
  - **Resolution:** ZAP warned that HTTP `GET` responses didn't explicitly forbid caching. Because this is a REST API providing time-series data and station configurations, standard client-side/proxy caching is acceptable and sometimes desirable.

## 3. Data Integrity Validation
After the active attack sequence, the database tables (`istasyonlar`, `kullanicilar`, `organizations`) were queried. 
**Result:** `0` garbage rows were created. Pydantic validation (e.g., UUID constraints, Enums) and database schema constraints successfully deflected all fuzzing payloads at the border.

## 4. How to Re-Run the Scan
To reproduce the active scan locally using Docker:

1. Start the Su-AI docker stack (`make up`).
2. Obtain a valid JWT token (e.g., login as `admin@suski.gov.tr`).
3. Run the following command (replace `<TOKEN>` with the JWT):
```bash
docker run --rm -v $(pwd)/zap_report:/zap/wrk/:rw -t --network su-ai_su-ai-network zaproxy/zap-stable zap-full-scan.py -t http://su-ai-backend:8000 -r zap_active_report.html -J zap_active_report.json -z "-config replacer.full_list(0).description=auth -config replacer.full_list(0).enabled=true -config replacer.full_list(0).matchtype=req_header -config replacer.full_list(0).matchstr=Authorization -config replacer.full_list(0).regex=false -config replacer.full_list(0).replacement='Bearer <TOKEN>' -config 'spider.excludeFromScan=.*(/olcumler/|/su-olcumu|/api/sim/tetikle).*' -config 'scanner.excludeFromScan=.*(/olcumler/|/su-olcumu|/api/sim/tetikle).*' -config api.disablekey=true"
```
