# Slack Gateway — full specification and contracts

Document version: requirements triage (2026-05).  
Service name: `aegis-slack-gateway` (Cloud Run, Aegis Hub project)

---

## 1. Purpose and placement in Aegis Hub

The **Slack Gateway** is a public Cloud Run service in the **Aegis Hub** project. It acts as a thin communication layer between Slack and the internal Hub services (Query Processor, Incident Analyzer).

**Core responsibilities:**

- Receive Slack bot mentions (`app_mention` events) from Slack Events API
- Parse structured user input (incident queries, latest incidents requests)
- Forward parsed requests to Query Processor via REST
- Receive alert payloads from Incident Analyzer via internal HTTP endpoint
- Post all responses and alerts to Slack channels/threads

**What Slack Gateway does NOT do:**

- No direct access to Firestore, BigQuery, Cloud Monitoring, or Vertex AI
- No business logic (metric analysis, incident processing, AI queries)
- No session state management
- No authentication logic beyond Slack (MVP: signing verification skipped)

```mermaid
flowchart LR
  User[👤 SRE User] -->|@bot mention| Slack[Slack Workspace]
  Slack -->|HTTPS webhook| SG[Slack Gateway]
  SG -->|REST + OIDC token| QP[Query Processor]
  IA[Incident Analyzer] -->|POST alert| SG
  SG -->|chat.postMessage| Slack
  QP --> FS[(Firestore)]
  QP --> BQ[(BigQuery)]
  QP --> MON[Cloud Monitoring]
  QP --> GEM[Vertex AI]
```



### 1.1 Service characteristics


| Property           | Value                                                                      |
| ------------------ | -------------------------------------------------------------------------- |
| **Type**           | Cloud Run (stateless, autoscaling)                                         |
| **Ingress**        | `INGRESS_TRAFFIC_ALL` (public endpoint for Slack webhooks)                 |
| **IAM (inbound)**  | `allUsers` (Slack Events API needs public access)                          |
| **IAM (outbound)** | Service account `aegis-bot-sa` with `roles/run.invoker` on Query Processor |
| **Language**       | Python 3.11+                                                               |
| **Framework**      | FastAPI                                                                    |
| **State**          | Stateless (no database, cache, or in-memory session storage)               |


---

## 2. User-facing flows (via Slack)

Users interact with Aegis AI exclusively through Slack bot mentions. Slack Gateway translates these mentions into structured API calls.

### 2.1 Incident query (troubleshooting conversation)

**Slack user action:**

```
@aegis-bot INC-2026-00041 why is memory high
```

**Gateway responsibility:**

1. Receive `app_mention` event from Slack Events API
2. Extract `incident_id` (first token after bot mention)
3. Extract `message` (remaining text)
4. Validate structure (must have both incident ID and message)
5. Call Query Processor: `POST /v1/incidents/{incident_id}/query` with `{"message": "why is memory high"}`
6. On 200: post `slack_text` from response to same Slack thread
7. On 404/4xx/5xx: post human-readable error to Slack

### 2.2 Latest incidents list

**Slack user action:**

```
@aegis-bot latest 10
```

**Gateway responsibility:**

1. Detect keyword `latest` in mention text
2. Parse limit number (default: 10 if not specified)
3. Call Query Processor: `GET /v1/incidents/latest?limit=10`
4. Format JSON response into readable Slack message:
  ```
   Latest incidents:
  ```
  1. INC-2026-00041 | java-api | OutOfMemoryError | Critical | 4 min ago
  2. INC-2026-00040 | python-worker | TimeoutError | Warning | 19 min ago
    .
    `
5. Post formatted text to Slack thread/channel

### 2.3 Alert posting (from Incident Analyzer)

**Incident Analyzer action:**
When a new incident is detected and stored in BigQuery, Analyzer creates initial Firestore session and wants to alert SRE team in Slack.

**Gateway responsibility:**

1. Receive `POST /internal/v1/alerts` from Incident Analyzer (private, authenticated)
2. Extract `text`, `channel_id`, optional `thread_ts`
3. Post message to Slack using `chat.postMessage` API
4. Return 200 on success, 5xx on Slack API failure

---

## 3. HTTP API contracts

### 3.1 Inbound: Slack Events API → Gateway

**Endpoint:** `POST /slack/events`

**Purpose:** Receive Slack Events API callbacks (primarily `app_mention`)

**Authentication (MVP):** None (Slack signing secret verification skipped for MVP; can be added later)

**Request body (Slack `app_mention` event example):**

```json
{
  "type": "event_callback",
  "event": {
    "type": "app_mention",
    "user": "U123456",
    "text": "<@U987654> INC-2026-00041 why is memory high",
    "ts": "1653412345.000100",
    "channel": "C123456",
    "thread_ts": "1653410000.000000"
  }
}
```

**Special case: URL verification (Slack setup):**

```json
{
  "type": "url_verification",
  "challenge": "random_string"
}
```

**Response:** `{"challenge": "random_string"}` (HTTP 200)

**Response for app_mention:** HTTP 200 `{"ok": true}` (immediate acknowledgment)

**Processing:**

1. Check `event.type == "app_mention"`
2. Parse `event.text`: strip bot user ID mention, extract incident ID and message
3. Determine flow: `latest` keyword → latest incidents, otherwise → incident query
4. Call Query Processor (async, no blocking)
5. Post response to Slack using `event.channel` and optional `event.thread_ts`

### 3.2 Inbound: Incident Analyzer → Gateway

**Endpoint:** `POST /internal/v1/alerts`

**Purpose:** Post incident alerts to Slack on behalf of Incident Analyzer

**Authentication:** Google Cloud Run OIDC identity token (audience = Slack Gateway URL)

**IAM:** `aegis-bot-sa` service account with `roles/run.invoker` on Slack Gateway

**Request body:**

```json
{
  "channel_id": "C123456",
  "text": "🚨 New incident detected:\n**INC-2026-00041** | java-api | OutOfMemoryError\nSeverity: Critical\n\nReply with: @aegis-bot INC-2026-00041 <your question>",
  "thread_ts": null
}
```

**Response:**

- **200 OK:** `{"ok": true, "ts": "1653412345.000100"}` (Slack message timestamp)
- **400 Bad Request:** Missing required fields
- **502 Bad Gateway:** Slack API returned error
- **503 Service Unavailable:** Cannot reach Slack API

### 3.3 Outbound: Gateway → Query Processor

**Base URL:** Environment variable `QUERY_PROCESSOR_URL` (Cloud Run service URI)

**Authentication:** Google Cloud Run OIDC identity token (audience = Query Processor URL)

**Headers:**

```
Authorization: Bearer <identity_token>
Content-Type: application/json
X-Request-Id: <uuid>
```

#### 3.3.1 Incident query

**Endpoint:** `POST /v1/incidents/{incident_id}/query`

**Request body:**

```json
{
  "message": "why is memory high"
}
```

**Success response (200 OK):**

```json
{
  "incident_id": "INC-2026-00041",
  "slack_text": "Memory is high because...\n\nRecommended actions:\n1. Check heap dumps\n2. Review recent deployments",
  "timestamp": "2026-05-20T21:30:00Z"
}
```

**Error responses:**


| HTTP | `error_code`                                      | Meaning                            | Gateway action                                                  |
| ---- | ------------------------------------------------- | ---------------------------------- | --------------------------------------------------------------- |
| 400  | `INVALID_REQUEST`                                 | Malformed request                  | Post "Invalid request format" to Slack                          |
| 404  | `SESSION_NOT_FOUND`                               | Incident/session doesn't exist     | Post "Incident {id} not found. Check the incident ID." to Slack |
| 403  | `PROJECT_NOT_ALLOWED`                             | Client project not allowed         | Post "Access denied to project" to Slack                        |
| 502  | `GEMINI_INVALID_PLAN` / `GEMINI_INVALID_RESPONSE` | AI processing failed               | Post "AI analysis failed, try again" to Slack                   |
| 503  | `DEPENDENCY_UNAVAILABLE`                          | Firestore/Monitoring/BigQuery down | Post "Service temporarily unavailable" to Slack                 |
| 504  | `PROCESSING_TIMEOUT`                              | Processing exceeded deadline       | Post "Request timed out, try again" to Slack                    |


#### 3.3.2 Latest incidents

**Endpoint:** `GET /v1/incidents/latest?limit=10`

**Query parameters:**

- `limit` (optional, default 10): Number of incidents to return

**Success response (200 OK):**

```json
{
  "incidents": [
    {
      "incident_id": "INC-2026-00041",
      "client_project_id": "mock-client-dev",
      "service_name": "java-api",
      "error_type": "OutOfMemoryError",
      "severity": "Critical",
      "timestamp": "2026-05-20T21:26:00Z",
      "minutes_ago": 4
    },
    {
      "incident_id": "INC-2026-00040",
      "client_project_id": "mock-client-dev",
      "service_name": "python-worker",
      "error_type": "TimeoutError",
      "severity": "Warning",
      "timestamp": "2026-05-20T21:11:00Z",
      "minutes_ago": 19
    }
  ],
  "total": 2
}
```

**Error responses:**


| HTTP | Meaning                 | Gateway action                      |
| ---- | ----------------------- | ----------------------------------- |
| 400  | Invalid limit parameter | Post "Invalid request" to Slack     |
| 503  | BigQuery unavailable    | Post "Service unavailable" to Slack |


### 3.4 Outbound: Gateway → Slack Web API

**Endpoint:** `https://slack.com/api/chat.postMessage`

**Authentication:** `Authorization: Bearer <SLACK_BOT_TOKEN>`

**Request body:**

```json
{
  "channel": "C123456",
  "text": "Message text here",
  "thread_ts": "1653410000.000000"
}
```

**Response:**

```json
{
  "ok": true,
  "channel": "C123456",
  "ts": "1653412345.000100",
  "message": {
    "text": "Message text here",
    "user": "U987654"
  }
}
```

**Error handling:**

- If `ok == false`: log error, return 502 to caller (if Incident Analyzer), or silently fail (if posting user response)

---

## 4. Message parsing logic

### 4.1 Bot mention text format

**Expected structure:**

```
@bot-name INCIDENT_ID MESSAGE
```

or

```
@bot-name latest [N]
```

**Parsing algorithm:**

1. Strip bot user ID mention (e.g. `<@U987654>`) from `event.text`
2. Split remaining text by whitespace: `tokens = text.strip().split()`
3. **Latest incidents path:**
  - If `tokens[0].lower() == "latest"`: extract `limit = int(tokens[1])` if exists, else default 10
  - Call `GET /v1/incidents/latest?limit={limit}`
4. **Incident query path:**
  - Extract `incident_id = tokens[0]`
  - Validate format: must match pattern `INC-\d{4}-\d{5}` (e.g. `INC-2026-00041`)
  - Extract `message = " ".join(tokens[1:])` (everything after incident ID)
  - If `message` is empty: post error "Invalid format. Usage: @bot INC-XXXX-XXXXX your question"
  - Call `POST /v1/incidents/{incident_id}/query`

### 4.2 Latest incidents formatting

**Input (from Query Processor):**

```json
{
  "incidents": [
    {
      "incident_id": "INC-2026-00041",
      "service_name": "java-api",
      "error_type": "OutOfMemoryError",
      "severity": "Critical",
      "minutes_ago": 4
    }
  ],
  "total": 1
}
```

**Output (Slack message):**

```
📋 Latest incidents (1 total):

1. INC-2026-00041 | java-api | OutOfMemoryError | Critical | 4 min ago
```

**Formatting rules:**

- Add emoji prefix: 📋
- Header: "Latest incidents ({total} total):"
- Each incident: numbered list with format `{id} | {service} | {error_type} | {severity} | {minutes_ago} min ago`
- If `total == 0`: "No recent incidents found."

### 4.3 Error message mapping


| Query Processor error                                 | Slack user message                                                                                                                                 |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 404 `SESSION_NOT_FOUND`                               | "❌ Incident `{incident_id}` not found. Please check the incident ID."                                                                              |
| 400 `INVALID_REQUEST`                                 | "❌ Invalid request format. Usage: `@aegis-bot INC-XXXX-XXXXX your question`"                                                                       |
| 403 `PROJECT_NOT_ALLOWED`                             | "❌ Access denied to the specified project."                                                                                                        |
| 502 `GEMINI_INVALID_PLAN` / `GEMINI_INVALID_RESPONSE` | "❌ AI analysis failed. Please try again."                                                                                                          |
| 503 `DEPENDENCY_UNAVAILABLE`                          | "❌ Service temporarily unavailable. Please try again in a moment."                                                                                 |
| 504 `PROCESSING_TIMEOUT`                              | "❌ Request timed out. Please try again."                                                                                                           |
| Gateway parsing error                                 | "❌ Invalid message format. Use:\n• `@aegis-bot INC-XXXX-XXXXX your question` for incident queries\n• `@aegis-bot latest [N]` for recent incidents" |


---

## 5. Threading behavior

**Requirement:** When user mentions bot in a Slack thread, Gateway should reply in the same thread (not as new top-level message).

**Implementation:**

1. Slack `app_mention` event includes `thread_ts` field if message was sent in a thread
2. When posting response via `chat.postMessage`, include `thread_ts` from original event
3. If `thread_ts` is not present (top-level mention), post as top-level message

**Example:**

```python
# Original event
event = {
    "channel": "C123456",
    "thread_ts": "1653410000.000000"  # Present if in thread
}

# Response
slack_client.chat_postMessage(
    channel=event["channel"],
    text="Response text",
    thread_ts=event.get("thread_ts")  # Preserves thread context
)
```

---

## 6. Environment variables


| Variable                   | Source           | Purpose                                                      | Required |
| -------------------------- | ---------------- | ------------------------------------------------------------ | -------- |
| `SLACK_BOT_TOKEN`          | Secret Manager   | OAuth token for Slack Web API (`chat.postMessage`)           | Yes      |
| `SLACK_SIGNING_SECRET`     | Secret Manager   | Verify Slack request signatures (MVP: not used)              | No (MVP) |
| `QUERY_PROCESSOR_URL`      | Terraform output | Cloud Run URL for Query Processor                            | Yes      |
| `GCP_PROJECT`              | Hub project ID   | For logging, OIDC token audience                             | Yes      |
| `GCP_REGION`               | Region           | For logging                                                  | Yes      |
| `ENVIRONMENT`              | `dev` / `prod`   | Logging labels                                               | Yes      |
| `DEFAULT_SLACK_CHANNEL_ID` | Manual config    | Default alert channel (if Incident Analyzer doesn't specify) | No       |


**Removed from Gateway (compared to current Terraform):**

- `FIRESTORE_DATABASE` — not needed (Query Processor owns Firestore)
- `BIGQUERY_DATASET` / `BIGQUERY_INCIDENTS_TABLE` — not needed (Query Processor owns BigQuery)
- `ALLOWED_CLIENT_PROJECT_IDS` — not needed (Query Processor validates projects)
- `METRICS_SERVICE_URL` — renamed to `QUERY_PROCESSOR_URL` (same purpose)

---

## 7. Authentication and authorization

### 7.1 Inbound from Slack (public endpoint)

**Current (MVP):** No verification (accept all POST requests to `/slack/events`)

**Future (production):** Verify Slack signing secret:

1. Extract `X-Slack-Signature` and `X-Slack-Request-Timestamp` headers
2. Compute HMAC-SHA256 of `v0:{timestamp}:{body}` using `SLACK_SIGNING_SECRET`
3. Compare computed signature with `X-Slack-Signature`
4. Reject if mismatch or timestamp > 5 minutes old

### 7.2 Inbound from Incident Analyzer (private endpoint)

**Method:** Google Cloud Run OIDC identity token

**IAM:** Incident Analyzer service account (`aegis-bot-sa`) must have `roles/run.invoker` on Slack Gateway

**Verification:** FastAPI middleware validates token audience matches Gateway URL

### 7.3 Outbound to Query Processor

**Method:** Google Cloud Run OIDC identity token

**IAM:** Slack Gateway service account (`aegis-bot-sa`) must have `roles/run.invoker` on Query Processor

**Implementation:** Use `google.auth.transport.requests` to obtain identity token with audience = Query Processor URL

```python
from google.auth.transport.requests import Request
from google.oauth2 import id_token

target_audience = os.getenv("QUERY_PROCESSOR_URL")
token = id_token.fetch_id_token(Request(), target_audience)
headers = {"Authorization": f"Bearer {token}"}
```

### 7.4 Outbound to Slack Web API

**Method:** OAuth bot token

**Retrieval:** Fetch `SLACK_BOT_TOKEN` from Secret Manager at startup

**Usage:** `Authorization: Bearer {token}` on all Slack API calls

---

## 8. Health and readiness endpoints


| Method | Path      | Purpose                    | Response                                                                            |
| ------ | --------- | -------------------------- | ----------------------------------------------------------------------------------- |
| GET    | `/health` | Liveness probe (Cloud Run) | `{"status": "ok"}`                                                                  |
| GET    | `/ready`  | Readiness probe (optional) | `{"status": "ready", "dependencies": {"query_processor": "ok", "slack_api": "ok"}}` |


**Authentication:** None (must be accessible by Cloud Run health checks)

**Implementation notes:**

- `/health`: Always return 200 (service is alive)
- `/ready`: Optionally test Query Processor and Slack API reachability (not required for MVP)

---

## 9. Error handling and logging

### 9.1 Structured logging

**Format:** JSON logs with standard fields

**Required fields:**

```json
{
  "severity": "INFO",
  "message": "Received app_mention event",
  "trace": "projects/{project}/traces/{trace_id}",
  "incident_id": "INC-2026-00041",
  "slack_user": "U123456",
  "slack_channel": "C123456",
  "request_id": "uuid"
}
```

**Log levels:**

- `INFO`: Normal operations (received event, posted message, called Query Processor)
- `WARNING`: Retryable errors (Query Processor 503, Slack API rate limit)
- `ERROR`: Non-retryable errors (400 from Query Processor, invalid message format)
- `CRITICAL`: Service failures (cannot obtain OIDC token, Secret Manager unavailable)

### 9.2 Retry logic

**Query Processor calls:**

- Retry on 503, 504 (max 2 retries, exponential backoff)
- No retry on 400, 404, 502

**Slack API calls:**

- Retry on rate limit (respect `Retry-After` header)
- Retry on 5xx (max 3 retries)
- No retry on 4xx

---

## 10. Service dependencies


| Dependency                  | Type                | Purpose                                          | Failure impact                            |
| --------------------------- | ------------------- | ------------------------------------------------ | ----------------------------------------- |
| **Query Processor**         | Cloud Run (private) | Execute incident queries, fetch latest incidents | User queries fail; post error to Slack    |
| **Slack Web API**           | External HTTP       | Post messages to Slack                           | Alerts/responses not delivered; log error |
| **Secret Manager**          | GCP service         | Retrieve `SLACK_BOT_TOKEN`                       | Service fails to start                    |
| **Identity Token Provider** | GCP metadata server | Obtain OIDC tokens for Query Processor           | Cannot authenticate; queries fail         |


**Startup checks:**

1. Retrieve `SLACK_BOT_TOKEN` from Secret Manager (fail fast if missing)
2. Validate `QUERY_PROCESSOR_URL` format (fail fast if invalid)
3. Test identity token generation (log warning if fails, but don't block startup)

---

## 11. Deployment and scaling

### 11.1 Cloud Run configuration

```hcl
resource "google_cloud_run_v2_service" "slack_gateway" {
  name     = "aegis-slack-gateway"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  
  template {
    service_account = google_service_account.aegis_bot.email
    
    scaling {
      min_instance_count = 0  # Scale to zero when idle
      max_instance_count = 2  # Max 2 concurrent instances
    }
    
    containers {
      image = var.slack_gateway_image
      
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }
}
```

### 11.2 Performance targets


| Metric                       | Target       | Notes                                                             |
| ---------------------------- | ------------ | ----------------------------------------------------------------- |
| Slack Events API ack latency | < 3 seconds  | Slack requirement (not enforced in MVP since processing is async) |
| Incident query end-to-end    | < 30 seconds | Includes Query Processor AI processing                            |
| Latest incidents end-to-end  | < 5 seconds  | Query Processor reads from BigQuery                               |
| Alert posting latency        | < 2 seconds  | Incident Analyzer → Gateway → Slack                               |


---

## 12. Testing strategy

### 12.1 Unit tests

**Test cases:**

1. Message parsing: valid incident query, latest query, invalid format
2. Latest incidents formatting: empty list, single incident, multiple incidents
3. Error mapping: 404 → user message, 503 → user message
4. Threading: preserve `thread_ts`, handle missing `thread_ts`
5. Token extraction: strip bot mention, handle extra whitespace

### 12.2 Integration tests

**Test cases:**

1. Mock Slack event → Gateway → Mock Query Processor (200 response) → Mock Slack API
2. Mock Slack event with invalid format → Gateway posts error to Mock Slack API
3. Mock Incident Analyzer → Gateway → Mock Slack API (alert posting)
4. Query Processor returns 404 → Gateway posts "not found" error
5. Latest incidents: Query Processor returns JSON → Gateway formats correctly

### 12.3 Manual testing checklist

- Send `@bot INC-2026-00041 test message` in Slack → verify Query Processor receives call
- Send `@bot latest 5` → verify formatted list appears in Slack
- Send `@bot invalid format` → verify error message appears
- Trigger incident in client project → verify alert appears in Slack
- Reply to incident in thread → verify response stays in thread
- Query Processor returns 404 → verify user-friendly error in Slack

---

## 13. Future enhancements (out of scope for MVP)


| Feature                                             | Priority | Notes                                            |
| --------------------------------------------------- | -------- | ------------------------------------------------ |
| Slack signing secret verification                   | Medium   | Security hardening for production                |
| Slash commands (`/aegis status`, `/aegis help`)     | Low      | Requires separate endpoint and OAuth scope       |
| Rich Slack Block Kit formatting                     | Low      | Replace plain text with interactive blocks       |
| Request deduplication (by `X-Request-Id`)           | Low      | Prevent duplicate Query Processor calls on retry |
| Rate limiting per user                              | Low      | Prevent abuse of AI queries                      |
| Metrics export (request count, latency, error rate) | Medium   | Cloud Monitoring integration                     |
| `/ready` with dependency checks                     | Low      | More robust health checking                      |


---

## 14. Related documents

- `.llm_context/query-processor-spec.md` — Query Processor specification (Gateway's primary dependency)
- `.llm_context/Aegis_AI_M1_Checkpoint_with_Firebase.md` — Original architecture (partially superseded)
- `AGENTS.md` — Current architecture (thin Gateway, Query Processor separation)
- `terraform/aegis-hub/cloudrun.tf` — Infrastructure definition
- `terraform/aegis-hub/secrets.tf` — Slack token and signing secret management

---

## 15. Open implementation decisions


| Decision                                       | Options                                                       | Recommendation                                  |
| ---------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------- |
| FastAPI dependency injection for clients       | Create Slack/Query Processor clients per request vs singleton | Singleton (reuse HTTP sessions)                 |
| Async vs sync HTTP calls                       | `httpx.AsyncClient` vs `requests`                             | Async (better concurrency for Cloud Run)        |
| Error response format to user                  | Plain text vs structured mrkdwn                               | Plain text (simpler, mrkdwn can be added later) |
| Latest incidents default limit                 | 5, 10, or 25                                                  | 10 (aligns with Query Processor default)        |
| Incident Analyzer alert endpoint path          | `/internal/v1/alerts` vs `/v1/alerts`                         | `/internal/v1/alerts` (signals private API)     |
| Store default Slack channel in code vs env var | Hardcode vs `DEFAULT_SLACK_CHANNEL_ID`                        | Env var (easier to change per environment)      |


---

## 16. Implementation checklist

### Phase 1: Core infrastructure

- FastAPI app scaffold with `/health` endpoint
- Retrieve `SLACK_BOT_TOKEN` from Secret Manager at startup
- OIDC token generation for Query Processor authentication
- Structured JSON logging setup

### Phase 2: Slack Events API integration

- `POST /slack/events` endpoint
- URL verification handler (`type: url_verification`)
- `app_mention` event parsing
- Message format validation and splitting (incident ID + message vs `latest`)

### Phase 3: Query Processor integration

- `POST /v1/incidents/{incident_id}/query` client
- `GET /v1/incidents/latest` client
- Error response parsing and mapping
- Retry logic for 5xx responses

### Phase 4: Slack Web API integration

- `chat.postMessage` client
- Threading support (`thread_ts` passthrough)
- Error handling for Slack API failures

### Phase 5: Incident Analyzer integration

- `POST /internal/v1/alerts` endpoint
- OIDC token verification (Cloud Run authentication)
- Forward alert to Slack

### Phase 6: Message formatting

- Latest incidents JSON → Slack text formatter
- Error message templates
- Emoji prefixes for different message types

### Phase 7: Testing and deployment

- Unit tests for parsing and formatting
- Integration tests with mocked dependencies
- Dockerfile
- Cloud Build trigger
- Terraform variable updates (remove unnecessary env vars)

---

## 17. Example end-to-end flows

### Flow 1: User asks incident question

```
1. User in Slack: "@aegis-bot INC-2026-00041 why is memory spiking"
2. Slack → Gateway: POST /slack/events
   {
     "type": "event_callback",
     "event": {
       "type": "app_mention",
       "text": "<@U987654> INC-2026-00041 why is memory spiking",
       "channel": "C123456",
       "thread_ts": "1653410000.000000"
     }
   }
3. Gateway: Parse → incident_id="INC-2026-00041", message="why is memory spiking"
4. Gateway → Query Processor: POST /v1/incidents/INC-2026-00041/query
   Authorization: Bearer <oidc_token>
   {"message": "why is memory spiking"}
5. Query Processor → Gateway: 200 OK
   {
     "incident_id": "INC-2026-00041",
     "slack_text": "Memory spiking due to...\n\nActions:\n1. Check heap\n2. Review config",
     "timestamp": "..."
   }
6. Gateway → Slack: POST https://slack.com/api/chat.postMessage
   Authorization: Bearer <slack_bot_token>
   {
     "channel": "C123456",
     "thread_ts": "1653410000.000000",
     "text": "Memory spiking due to...\n\nActions:\n1. Check heap\n2. Review config"
   }
7. Slack → Gateway: {"ok": true, "ts": "..."}
8. Gateway logs success, returns 200 to Slack Events API
```

### Flow 2: User requests latest incidents

```
1. User in Slack: "@aegis-bot latest 5"
2. Slack → Gateway: POST /slack/events
3. Gateway: Parse → keyword="latest", limit=5
4. Gateway → Query Processor: GET /v1/incidents/latest?limit=5
5. Query Processor → Gateway: 200 OK
   {
     "incidents": [
       {"incident_id": "INC-2026-00041", "service_name": "java-api", ...},
       ...
     ],
     "total": 5
   }
6. Gateway: Format JSON → "📋 Latest incidents (5 total):\n\n1. INC-2026-00041 | java-api | ..."
7. Gateway → Slack: POST chat.postMessage with formatted text
8. Done
```

### Flow 3: Incident Analyzer posts alert

```
1. Incident Analyzer: Detects new incident, stores in BigQuery + Firestore
2. Analyzer → Gateway: POST /internal/v1/alerts
   Authorization: Bearer <oidc_token>
   {
     "channel_id": "C123456",
     "text": "🚨 New incident:\n**INC-2026-00041** | java-api | OOM\nReply: @aegis-bot INC-2026-00041 <question>"
   }
3. Gateway: Verify OIDC token
4. Gateway → Slack: POST chat.postMessage
5. Slack → Gateway: {"ok": true}
6. Gateway → Analyzer: 200 OK {"ok": true, "ts": "..."}
```

### Flow 4: Query Processor returns 404 (session not found)

```
1. User: "@aegis-bot INC-9999-99999 help"
2. Gateway → Query Processor: POST /v1/incidents/INC-9999-99999/query
3. Query Processor → Gateway: 404 Not Found
   {
     "error_code": "SESSION_NOT_FOUND",
     "message": "No session found for incident INC-9999-99999"
   }
4. Gateway: Map error → "❌ Incident INC-9999-99999 not found. Please check the incident ID."
5. Gateway → Slack: POST chat.postMessage with error text
6. Done
```

---

## 18. Summary: What makes Slack Gateway "thin"

**Gateway does:**

- Parse Slack events (text splitting, keyword detection)
- Format lists for display (latest incidents JSON → readable text)
- Route messages (determine incident query vs latest incidents path)
- Post messages to Slack (on behalf of Query Processor and Incident Analyzer)
- Map error codes to user-friendly messages

**Gateway does NOT:**

- Store state (sessions, conversations, incidents)
- Call AI (Gemini)
- Fetch metrics (Cloud Monitoring)
- Query incidents (BigQuery)
- Analyze errors (Incident Analyzer responsibility)
- Make decisions about which metrics to fetch (Query Processor responsibility)

**In summary:** Slack Gateway is a stateless translation layer between Slack's message format and Aegis Hub's internal REST APIs.