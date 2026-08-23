# MutualFundRAGBot Deployment Plan

## 1. Deployment Architecture

Deploy the application as two services:

- **Backend:** FastAPI on Railway
- **Frontend:** Static HTML/CSS/JavaScript on Vercel
- **LLM:** Groq, called only by the Railway backend
- **Vector and metadata stores:** Chroma plus SQLite available to the Railway service
- **Source corpus:** The seven approved Groww URLs only

Request flow:

```text
Browser -> Vercel frontend -> Railway /ask
                         -> Railway retrieval/index
                         -> Groq generation
                         -> structured answer with one approved citation
```

The Groq key, embedding credentials, vector store, and SQLite metadata must never be exposed to Vercel or the browser.

## 2. Deployment Readiness Changes

Complete these code changes before deploying the services separately.

### 2.1 Backend CORS

Add FastAPI CORS middleware in `app/api.py` and allow only the deployed Vercel origin(s), for example:

- `https://<vercel-project>.vercel.app`
- The final custom frontend domain, if one is configured
- `http://localhost:8000` for local development, if needed

Read the value from a backend environment variable such as:

```dotenv
FRONTEND_ORIGINS=https://<vercel-project>.vercel.app
```

Do not use `*` when credentials or future authenticated endpoints may be introduced.

### 2.2 Configurable API base URL

The current `ui/app.js` calls `/ask` and `/sources`, which works when FastAPI serves the frontend from the same origin but not when Vercel hosts the frontend. Add a frontend build/runtime configuration value:

```js
const API_BASE_URL = "https://<railway-service>.up.railway.app";
```

Use `${API_BASE_URL}/ask`, `${API_BASE_URL}/sources`, and `${API_BASE_URL}/health` in the browser client. Prefer injecting this value at deploy time or generating a small configuration file rather than hard-coding a temporary Railway URL.

Do not put `GROQ_API_KEY`, database paths, or embedding secrets in frontend configuration.

### 2.3 Backend binding and proxy headers

Railway supplies the listening port through `$PORT`. Start Uvicorn using the Railway port:

```bash
uvicorn app.api:app --host 0.0.0.0 --port $PORT
```

Keep the existing `/health` endpoint as the Railway health check. It must not require vector initialization or a Groq network request.

## 3. Railway Backend Deployment

### 3.1 Create the service

1. Create a new Railway project.
2. Deploy the GitHub repository as a service.
3. Set the service root to the repository root.
4. Configure the start command:

```bash
uvicorn app.api:app --host 0.0.0.0 --port $PORT
```

5. Set the health check path to `/health`.
6. Generate a Railway public domain, then record it for the Vercel configuration.

A `Procfile` or Railway service configuration file may be added if the dashboard start command is not used.

### 3.2 Backend environment variables

Configure these in Railway Variables. Never commit their values.

```dotenv
APP_ENV=production
API_HOST=0.0.0.0
API_PORT=$PORT
LLM_PROVIDER=groq
GROQ_API_KEY=<rotated-groq-key>
GROQ_MODEL=openai/gpt-oss-120b
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
VECTOR_DB_PATH=/data/chroma
SQLITE_PATH=/data/processed/app.db
ALLOWED_DOMAINS=groww.in
ALLOWED_SOURCE_URLS=<exact-seven-approved-groww-urls>
DEFAULT_REFUSAL_LINK=https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth
FRONTEND_ORIGINS=https://<vercel-project>.vercel.app
```

Use the exact seven-URL value from `.env.example`; do not add aggregator or third-party URLs.

### 3.3 Vector and SQLite data strategy

The repository intentionally excludes generated Chroma, raw HTML, processed document files, and local databases. Choose one of these strategies before the first production deployment:

**Recommended for the first deployment: provision a Railway volume**

1. Attach a persistent Railway volume mounted at `/data`.
2. Place the Chroma directory at `/data/chroma`.
3. Place the SQLite metadata database at `/data/processed/app.db`.
4. Run the ingestion/index build once as a controlled release task.
5. Verify the collection contains embeddings before starting normal traffic.
6. Back up or recreate the volume from a documented corpus build when sources are refreshed.

**Alternative: ship a versioned index artifact**

Build the approved corpus and index in CI, publish an immutable artifact, and download it during deployment. Verify its checksum and schema before serving traffic. Do not upload secrets or unreviewed source material as an artifact.

A fresh Railway container without either a persistent volume or a bundled index will start but `/ask` and `/sources` will fail because the vector collection is absent.

### 3.4 Ingestion and refresh operations

Do not fetch the source corpus on every user request. Run ingestion as a scheduled or manually approved job:

1. Fetch only the seven approved Groww URLs.
2. Normalize and chunk the documents.
3. Rebuild or update Chroma and SQLite.
4. Run validation and retrieval smoke tests.
5. Promote the refreshed data only after the index integrity check passes.

Keep the existing source health and ingestion logs outside the browser response. Avoid storing user queries or personal information.

## 4. Vercel Frontend Deployment

The frontend is a static site in `ui/` and does not need Node.js or a frontend framework.

### 4.1 Recommended Vercel setup

Because the repository root contains the Python backend and the frontend lives in `ui/`, configure Vercel as follows:

- Import the GitHub repository into Vercel.
- Set **Root Directory** to `ui`.
- Framework preset: **Other**.
- Build command: `./vercel-build.sh`.
- Output directory: `.`.
- Install command: leave empty.

Ensure `index.html`, `styles.css`, and `app.js` are included in the deployment.

### 4.2 Frontend API configuration

Set the Railway URL through the chosen frontend configuration mechanism, for example:

```dotenv
PUBLIC_API_BASE_URL=https://<railway-service>.up.railway.app
```

For the framework-free static deployment, set `PUBLIC_API_BASE_URL` in Vercel and let `ui/vercel-build.sh` generate `config.js` during the build. Confirm that the value contains no trailing path that would produce `/ask/ask`. Local same-origin development uses the empty default in `ui/config.js`.

### 4.3 Vercel domains

1. Deploy a preview first.
2. Confirm the preview origin is present in Railway `FRONTEND_ORIGINS`.
3. Add the production custom domain, if applicable.
4. Add the production domain to Railway CORS settings.
5. Redeploy Railway after changing allowed origins.

## 5. Cross-Service Verification

Run these checks after both services deploy:

### Backend checks

```bash
curl -fsS https://<railway-service>.up.railway.app/health
curl -fsS https://<railway-service>.up.railway.app/sources
```

Expected results:

- `/health` returns HTTP 200 and `status: ok`.
- `/sources` returns exactly seven approved sources.
- No API response contains a non-approved URL.

### Browser checks

From the Vercel URL:

1. Load the welcome screen.
2. Confirm the disclaimer is always visible.
3. Submit all three example questions.
4. Confirm the network request targets Railway, not Vercel.
5. Confirm the response displays one citation and the source freshness footer.
6. Submit an advisory prompt such as `Should I invest in this fund?` and confirm the refusal state.
7. Open and close the approved-sources drawer.
8. Verify loading, unavailable, retry, focus, Enter, Shift+Enter, and Escape behavior.
9. Test at desktop width and approximately 390px mobile width.

### CORS check

Use the Vercel origin in an OPTIONS request and confirm the response includes the expected `access-control-allow-origin` value. Confirm an unknown origin is not allowed.

### Data integrity checks

Before production traffic:

- Verify Chroma has the expected collection and non-empty embeddings.
- Verify SQLite metadata points to the same corpus/index build.
- Verify all indexed documents use one of the seven approved URLs.
- Verify the index path is on persistent storage or restored from a verified artifact.

## 6. Security and Operations

- Rotate the Groq key that was previously exposed during development.
- Keep `.env` ignored and use Railway/Vercel secret stores only.
- Use HTTPS URLs for both services in production.
- Do not send Groq or embedding keys to the frontend.
- Do not collect PAN, Aadhaar, account numbers, OTPs, email addresses, or phone numbers.
- Restrict CORS to known frontend origins.
- Set provider and Railway usage alerts where available.
- Review Railway logs for errors without logging secrets or full sensitive requests.
- Add a deployment uptime check for `/health`.
- Document source refresh date and index version with each corpus rebuild.

## 7. Rollback Plan

### Backend rollback

1. Redeploy the previous known-good Railway deployment.
2. Restore the matching Chroma/SQLite volume or index artifact.
3. Check `/health` and `/sources`.
4. Run one factual and one refusal request before reopening traffic.

### Frontend rollback

Use Vercel's previous deployment promotion if a frontend release breaks layout or API routing. Keep the previous Railway URL stable so a frontend rollback does not require a backend rebuild.

### Data rollback

Keep the previous verified data snapshot until the new corpus passes retrieval and compliance checks. Never replace the only working index in place without a recoverable copy.

## 8. Release Checklist

- [ ] Rotate and store a valid Groq key in Railway.
- [ ] Add CORS middleware and production frontend origin.
- [ ] Make the frontend API base URL configurable.
- [ ] Provision Railway persistent storage or publish a verified index artifact.
- [ ] Deploy Railway and verify `/health`.
- [ ] Verify `/sources` returns seven approved URLs.
- [ ] Deploy `ui/` to Vercel.
- [ ] Configure Railway CORS for Vercel preview and production origins.
- [ ] Test three factual queries from the Vercel UI.
- [ ] Test advisory refusal behavior.
- [ ] Test mobile and desktop layouts.
- [ ] Confirm no secrets are present in Git, Vercel, or browser source.
- [ ] Record deployment URLs, index version, and rollback target.

## 9. Known Deployment Limitations

- The current static frontend uses same-origin API paths and requires the API-base change described above for separate Vercel/Railway hosting.
- The current backend expects a prebuilt Chroma collection and SQLite metadata store; a new Railway container cannot reconstruct them automatically from the committed repository alone.
- The current startup validation checks configuration, while full service construction occurs on the first `/ask` or `/sources` request. Keep the post-deployment smoke tests in place to catch missing runtime dependencies.
- Groq availability, model access, rate limits, and API-key validity remain external dependencies.
