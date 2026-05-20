# Aegis AI Presentation

Render the reveal.js deck from this directory:

```bash
quarto render index.qmd
```

Preview while editing:

```bash
quarto preview index.qmd
```

## Slide Outline

1. **Aegis AI** - title, project promise, and core GCP services.
2. **What We Are Presenting** - talk arc for problem, architecture, reliability, and demo.
3. **The Problem We Want to Solve** - why cross-project incident context matters.
4. **One-Sentence System** - end-to-end event flow from client error to Slack and BigQuery.
5. **Goals and Boundaries** - goals and non-goals from the M1 project plan.
6. **Architecture: Two Trust Domains** - Aegis Hub Project versus Client Project.
7. **Incident Pipeline** - Cloud Logging sink, Pub/Sub, analyzer, BigQuery, Slack.
8. **Operator Experience in Slack** - planned commands and sample status response.
9. **Hub Microservices** - Slack Gateway, Incident Analyzer, and Metrics Service.
10. **APIs and Data Contracts** - Slack, REST, Pub/Sub, and idempotency key.
11. **Storage Design** - BigQuery, Firestore, Pub/Sub/DLQ, and Secret Manager.
12. **Reliability Targets** - core SLIs and SLOs for the Hub.
13. **Reliability Mechanisms** - managed GCP mechanisms plus application controls.
14. **Security and Privacy** - least-privilege IAM, secrets, sanitized storage, public surface.
15. **Cost-Aware Scaling Path** - prototype assumptions and large-scale direction.
16. **Planned Demo Scenario** - concrete class demo sequence.
17. **Team Division** - four-person ownership split.
18. **What This Project Will Prove** - closing takeaway.

Speaker notes are embedded in `index.qmd` using Quarto reveal.js note blocks.
