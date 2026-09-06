# FinSight Authentication & Authorization (Phase 12.2)

## Overview

FinSight implements a secure, self-hosted **Google OAuth 2.0 / OpenID Connect (OIDC)** authentication architecture backed by **PostgreSQL server-side sessions** and an **HttpOnly session cookie**.

No external authentication SaaS providers (such as Clerk, Auth0, Supabase Auth, or Firebase Auth) are used. The backend owns user resolution, session lifecycle, and strict multi-tenant authorization.

---

## 1. Authentication Architecture

```text
Browser
   │
   │ 1. GET /api/v1/auth/google/login
   ▼
FastAPI Backend ──(Generates cryptographically signed HMAC OAuth state)──► Google Accounts
   │                                                                             │
   │ 2. Redirect with authorization code + state                                 │
   ▼                                                                             │
FastAPI Callback ◄───────────────────────────────────────────────────────────────┘
   │
   ├─► Validates OAuth state (signature, freshness <= 5 min, single-use)
   ├─► Exchanges code for OIDC ID Token & UserInfo via Authlib
   ├─► Resolves user via canonical identity: `provider="google"`, `provider_sub=sub`
   ├─► Generates 32-byte opaque session token (secrets.token_urlsafe)
   ├─► Persists SHA-256 hash in PostgreSQL `user_sessions`
   └─► Sets HttpOnly Cookie: `finsight_session=<raw_token>` (SameSite=Lax, Path=/)
   │
   │ 3. 302 Redirect to FRONTEND_URL
   ▼
Browser (authenticated session established)
```

---

## 2. Server-Side Session Security

1. **Opaque Tokens**: Raw session tokens are unpredictable random strings generated using Python's `secrets.token_urlsafe(32)`.
2. **Hashed Persistence**: Only the **SHA-256 hash** (`session_token_hash`) of the token is stored in the database. The raw token is never persisted.
3. **No Frontend Storage**: The raw token is never returned in JSON payloads, never logged, and never stored in `localStorage`, `sessionStorage`, or Zustand. The browser automatically carries it in the `HttpOnly` cookie.
4. **Cookie Attributes**:
   - `HttpOnly`: Inaccessible to client JavaScript, mitigating XSS token theft.
   - `SameSite=Lax`: Protects against Cross-Site Request Forgery (CSRF).
   - `Secure`: Controlled by `SESSION_COOKIE_SECURE`. Set to `true` in HTTPS production environments.
   - `Path=/`: Valid across all application routes.
5. **Configurable Expiry**: Sessions default to a 7-day lifetime (`SESSION_MAX_AGE_SECONDS=604800`), matching between cookie `Max-Age` and database `expires_at`.

---

## 3. Google OAuth Setup & Redirect URI

To configure Google OAuth in Google Cloud Console:

1. Navigate to **APIs & Services > Credentials** in the Google Cloud Console.
2. Create an **OAuth 2.0 Client ID** (Web application).
3. Set **Authorized redirect URIs** to:
   ```text
   http://localhost:8888/api/v1/auth/google/callback
   ```
   *(Or your production domain equivalent, e.g., `https://api.yourdomain.com/api/v1/auth/google/callback`)*.
4. Copy the **Client ID** and **Client Secret** into your `.env` file.

### Required Environment Variables

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8888/api/v1/auth/google/callback

# Session Configuration
SESSION_SECRET_KEY=generate-a-strong-random-secret-key-for-production
SESSION_COOKIE_NAME=finsight_session
SESSION_MAX_AGE_SECONDS=604800
SESSION_COOKIE_SECURE=false # Set to true in HTTPS production
FRONTEND_URL=http://localhost:3000
```

---

## 4. Multi-Tenant Ownership & Vector Isolation

### Canonical User Identity

Accounts are keyed by:
```text
provider = "google"
provider_sub = Google OIDC `sub` claim
```
Accounts are **never identified solely by email address**, ensuring that email changes on the identity provider cannot lead to account takeover or tenancy leakage.

### System User Migration

Existing data created prior to Phase 12.2 is mapped to an internal system user:
- `id`: `00000000-0000-0000-0000-000000000001`
- `email`: `system@finsight.local`
- `provider`: `system`
- `provider_sub`: `system-default`

The system user is not a Google account and cannot be authenticated via Google OAuth.

### Resource Scoping & IDOR Defense

All data models enforce ownership via `user_id`:
- `documents.user_id`
- `conversation_sessions.user_id`
- `reports.user_id`

When an authenticated user requests a resource belonging to another tenant, the API returns **404 Not Found** (not 403 Forbidden) to prevent object enumeration.

### Vector Search & RAG Isolation

Vector similarity search over `chunks` with pgvector joins against `documents` and filters by `Document.user_id == current_user.id`:
```sql
SELECT chunks.*, 1.0 - (chunks.embedding <=> :query_vector) AS similarity
FROM chunks
JOIN documents ON documents.id = chunks.document_id
WHERE documents.status = 'indexed'
  AND documents.user_id = :user_id
ORDER BY chunks.embedding <=> :query_vector ASC
LIMIT :top_k;
```
This guarantees that vector similarity search and grounded RAG answer generation strictly retrieve and cite evidence from documents owned by the querying tenant.

---

## 5. Running Authentication Tests

Automated security and authorization tests mock Google OAuth and test tenant boundaries without requiring live Google credentials:

```bash
# Run all backend authentication, security, and isolation tests
pytest finsight/backend/tests/test_auth_foundation.py
pytest finsight/backend/tests/test_auth_routes.py
pytest finsight/backend/tests/test_authorization_security.py

# Run full backend test suite (278 tests)
pytest finsight/backend/tests

# Run frontend authentication tests (138 tests)
npm --prefix finsight/frontend test
```

---

## 6. Testing with Mocked vs. Live Credentials

- **Mocked Testing (Default)**: The comprehensive automated test suite uses mocked OAuth flows and synthetic user sessions to verify HMAC state validation, token hashing, cookie lifecycle, IDOR defense, and vector isolation.
- **Live Testing**: Requires setting valid `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` and registering `http://localhost:8888/api/v1/auth/google/callback` in the Google Cloud Console. If credentials are not configured, attempting to log in will gracefully fail with a configuration error from Google.
