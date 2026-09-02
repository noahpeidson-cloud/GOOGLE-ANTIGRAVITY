---
name: streamlined-firebase-ai
description: >-
  Strict guardrails for Firebase project creation and Firebase AI Logic implementation. Prevents 403 CLI errors and ensures secure, initialized AI endpoints.
---

# Streamlined Firebase & AI Protocol

## 1. Firebase Project Creation (The 403 Bypass)
When a new Firebase project is required, the agent MUST NOT attempt to use irebase projects:create via the CLI, as this frequently fails with 403 Permission Denied due to backend GCP billing/org policies.
**Mandatory Action:** The agent must instruct the user to create the project manually via [console.firebase.google.com](https://console.firebase.google.com/), and then retrieve the Project ID. The agent will then link the local environment using 
px -y firebase-tools@latest use <PROJECT_ID>.

## 2. Proper AI Execution (Firebase AI Logic)
When building a mobile or web app that uses the Gemini API via Firebase AI Logic, the agent must enforce these exact strictures:
*   **Provisioning:** The agent MUST run 
px -y firebase-tools@latest init ailogic to provision the backend service. (Do not rely solely on lutterfire configure, as that only configures the client and results in PERMISSION_DENIED).
*   **Security:** The agent MUST instruct the user to configure App Check (e.g., reCAPTCHA Enterprise or Play Integrity). Without App Check, unauthorized clients can drain the AI quota.
*   **Model Selection:** Always default to gemini-flash-latest (or gemini-2.5-flash if explicitly requested) for text/multimodal tasks, or gemini-2.5-flash-image for Imagen tasks. Never use deprecated models like gemini-1.5-flash.
