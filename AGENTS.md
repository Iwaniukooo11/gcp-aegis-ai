# Project context
User has first experience with Google Cloud and is dumb as hell, you must be aware of that

Use folder .llm_context/ to keep notes, instructions, other specs or necessary junk. 

In file .llm_context/Aegis_AI_M1_Checkpoint_with_Firebase.md there is a descirption of the project in markdown format. 

Aegis AI is a serverless, multi-project ChatOps/SRE assistant for monitoring applications running in external Google Cloud projects. The system is divided into two environments:

## Brief project desciption

1. **Aegis Hub Project** — the central serverless application operated by the team.  
2. **Client Project** — a mock monitored environment containing a GKE-based microservice application with chaos/failure endpoints.

When an error occurs in the Client Project, Cloud Logging routes selected error logs to the Hub through Pub/Sub. The Hub normalizes the incident, stores a sanitized incident record in BigQuery, sends a human-readable Slack alert, and may optionally enrich the incident with Gemini-generated explanation. Engineers use **app mentions** to ask about a specific incident (`@bot INC-… question`) and the **`/aegis-latest-incidents`** slash command to list recent incidents.

The solution demonstrates correct cloud architecture, serverless/PaaS preference, infrastructure-as-code, storage design, APIs, reliability thinking, and large-scale assumptions. It is not expected to be scaled heavily because of the limited course budget, but the architecture should be extensible.

## Architecture of project (may not be readable in Aegis_AI_M1_Checkpoint_with_Firebase)

NOTE: Some aspects changed, note the next section !!!

flowchart TB
 subgraph GKE["GKE Autopilot Cluster"]
        ChaosBackend["Chaos Backend Services"]
        ChaosStorage[("Some SQL\nStorage")]
  end
 subgraph CLIENT["Client Project - Target Environment"]
        GKE
        Logging["Cloud Logging"]
        Monitoring["Cloud Monitoring"]
        Sink["Log Router Sink\nseverity >= ERROR"]
  end
 subgraph ARTIFACT["Artifact Registry (Container Images)"]
        SlackGateway["Cloud Run\nSlack Gateway"]
        IncidentAnalyzer["Cloud Run\nIncident Analyzer"]
        MetricsService["Cloud Run\nMetrics Service"]
  end
 subgraph HUB["Aegis Hub Project - SaaS Provider"]
        PubSub["Pub/Sub Topic\naegis-incoming-logs"]
        DLQ["Pub/Sub Dead Letter Topic"]
        ARTIFACT
        Gemini["Vertex AI / Gemini"]
        BigQuery[("BigQuery\naegis_incidents")]
        Firestore[("Firestore\nSession State")]
  end
    SRE["👤 DevOps / SRE User"] -- App mention or /aegis-latest-incidents --> Slack["Slack Workspace"]
    ChaosBackend --> ChaosStorage
    GKE --> Logging & Monitoring
    Logging --> Sink
    Sink -- "cross-project publish" --> PubSub
    PubSub -- push subscription --> IncidentAnalyzer
    PubSub -. failed messages .-> DLQ
    IncidentAnalyzer -- analyze stack trace --> Gemini
    IncidentAnalyzer -- write sanitized record --> BigQuery
    IncidentAnalyzer -- post alert --> Slack
    Slack -- HTTPS request --> SlackGateway
    SlackGateway -- read/write context --> Firestore
    SlackGateway -- REST /metrics/status --> MetricsService
    SlackGateway -- request analysis --> Gemini
    MetricsService -- "read-only API calls" --> Monitoring
    MetricsService -- explain metrics --> Gemini
    MetricsService -- Slack response --> Slack

    style Gemini fill:#2962ff7a
    style Slack fill:#aa00ff91

## Changes from the original plan in markdown document

- **Metrics Service** in `.llm_context/Aegis_AI_M1_Checkpoint_with_Firebase.md` is renamed to **Query Processor** (same role: cross-project health, monitoring, and logging queries).
- Slack Gateway is a thin layer: Slack Events API in, `chat.postMessage` out, routes to Query Processor and receives Incident Analyzer alerts
- Slack Gateway handles two Slack ingress paths: **app mentions** (`incident_id` + `text` only) and slash command **`/aegis-latest-incidents`** (optional limit text)
- Query Processor handles 2 paths: (1) app mention with `incident_id` — Gateway sends `POST /v1/incidents/{id}/query` with `text`; QP loads Firestore session, runs Gemini + Monitoring, returns `slack_text` + `timestamp`. (2) `/aegis-latest-incidents` — Gateway sends `GET /v1/incidents/latest?limit=N`; QP queries BigQuery (`terminal_status = SUCCESS` only), Gateway formats the list for Slack
- Incident Analyzer does not connect to Slack; it posts alert payloads to Slack Gateway (no `channel_id`; Gateway uses `DEFAULT_SLACK_CHANNEL_ID`)
- Slack Gateway has no Vertex AI, Firestore, BigQuery, or Monitoring access
- Only one slash command in MVP: `/aegis-latest-incidents` (`/aegis status`, `/aegis help`, etc. remain out of scope)
- when in doubt search `docs/*-spec.md` or `.llm_context/new_architecture_description.md`




## Technology

- Use python unless otherwise specified
- Use uv, add new deps with uv add, use uv sync if necessary
- Use docstrings for main public functions
- Do not use inline comments unless absolutely necessary, code should explain itself
- Do not overcomplicate, this is a student project. Keep the services modular but do not overcomplicate
- Act as senior software engineer
- Backend services should use Fast API if they are written in Python



## Repository structure

```
terraform/
  aegis-hub/          # Hub project: Cloud Run, Pub/Sub, Firestore, BigQuery, secrets, IAM
  client-agent/       # Client project: GKE Autopilot, log sink, cross-project IAM

aegis-hub-code/       # One folder per Hub Cloud Run service (Python + FastAPI + uv)
  slack-gateway/      # Slack Events API (app mentions), /aegis-latest-incidents, alert relay
  incident-analyzer/  # Pub/Sub push: normalize logs, BigQuery, Slack alerts, Gemini
  query-processor/    # REST: status, metrics, recent errors (was Metrics Service in M1 doc)

client-mock-code/     # GKE workloads deployed into client-agent cluster (2 mock services)
  java-api/            # Java API pod: primary chaos/OOM demo target
  python-worker/       # Python worker pod: secondary failure/timeout demo target
```

- Each service folder owns its own `pyproject.toml`, `Dockerfile`, and `README.md`.
- Hub service names align with Terraform Cloud Run resources in `terraform/aegis-hub/cloudrun.tf`.
- Client service names match Slack `/aegis status <service-name>` examples (`java-api`, `python-worker`).

## Infrastructure

In terraform/aegis-hub and terraform/client-agent



## Persona and Communication Style
- Speak like a direct, blunt tech peer (sometimes called "caveman" or "monkey" style).
- Zero conversational fluff, zero pleasantries ("Sure!", "Here is..."), and zero summary conclusions.
- Use full names (f.e insetad of TF: terraform, instead of GH: GitHub)

## Response Format
- Keep vocabulary simple, punchy, and completely literal.
- Lead with the direct consequence or core truth immediately.
- If posssible, use emojis