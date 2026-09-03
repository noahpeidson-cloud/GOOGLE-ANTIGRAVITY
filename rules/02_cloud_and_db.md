---
title: "Cloud & Database Guardrails"
category: "cloud_and_db"
enforcement: "strict"
---

# Cloud & Database Guardrails

## R17. BigQuery DDL Guardrail
- **Context:** When generating `CREATE TABLE` schemas (`.sql` files) for BigQuery to be executed via the `bq` CLI.
- **Mandate:** Agents MUST NOT use the `DEFAULT` keyword (e.g., `DEFAULT CURRENT_TIMESTAMP()`) in column definitions.
- **Actionable Execution:** Handle default values at the application layer or within the `INSERT` statement to avoid syntax parser rejections in the CLI.

## R34. Google Drive MCP Bandwidth Guardrail
- **Context:** When attempting to discover or explore files within Google Drive via the `gdrive` MCP integration.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using the generic `list_resources` tool on the `gdrive` MCP server.
- **Actionable Execution:** Read the targeted schemas (e.g., `listGoogleDocs.json`, `search.json`) in the MCP config folder and use `call_mcp_tool` with those specific commands.

## R36. GCP Authentication Guardrail
- **Context:** When provisioning service identities or backend authentication for Google Cloud (GCP) resources.
- **Mandate:** Agents MUST NOT attempt to use Microsoft Store Developer CLI or Azure AD Service Principals to authenticate GCP pipelines.
- **Actionable Execution:** Use native GCP Application Default Credentials (ADC), Service Account keys via `.env`, or Workload Identity Federation.
