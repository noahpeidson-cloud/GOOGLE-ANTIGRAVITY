# Handoff Report: Requirement R1 (Shared Database Extraction)

**Sender:** Explorer 1 (`teamwork_preview_explorer_survey_1`)  
**Recipient:** Teamwork Orchestrator (`teamwork_preview_orchestrator_3` / `9539051a-2f1f-4189-9b1a-d44269b0ac27`)  
**Date:** 2026-08-29T12:57:30Z  
**Type:** Hard Handoff (Investigation Survey Complete)  
**Detailed Report:** `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_1\analysis.md`

---

## 1. Observation

1. **Current Physical Location of Data Connect**:
   - The Data Connect configuration, GraphQL schemas, and connectors currently reside in `workspace_database/dataconnect/`:
     - `workspace_database/dataconnect/dataconnect.yaml` (Lines 1-12) specifies `serviceId: "omnichannel-service"`, `location: "us-central1"`, `database: "omnichannel_db"`, `instanceId: "omnichannel-postgres"`, `source: "./schema"`, `connectorDirs: ["./connector"]`.
     - `workspace_database/dataconnect/schema/schema.gql` (Lines 6-16) defines:
       ```graphql
       type VideoTag @table(name: "video_tags", key: "id", singular: "videoTag", plural: "videoTags") {
         id: Int64!
         filename: String! @unique
         filepath: String!
         domain: String!
         entity: String!
         viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb")
         technical: Any! @col(name: "technical", dataType: "jsonb")
         createdAt: Timestamp!
         updatedAt: Timestamp!
       }
       ```
     - `workspace_database/dataconnect/connector/connector.yaml` (Lines 1-7) specifies:
       ```yaml
       connectorId: "omnichannel-connector"
       generate:
         javascriptSdk:
           outputDir: "../../omnichannel_triage_hub/frontend/src/lib/dataconnect"
           package: "@firebase/data-connect"
           packageJsonDir: "../../omnichannel_triage_hub/frontend"
       ```
     - `workspace_database/dataconnect/connector/queries.gql` defines `query ListVideoTags` and `query GetVideoTag($id: Int64!)`.
     - `workspace_database/dataconnect/connector/mutations.gql` defines `mutation CreateVideoTag(...)`.
   - The target root directory `G:\My Drive\GOOGLE ANTIGRAVITY\dataconnect/` currently does not exist.

2. **Root Configuration (`firebase.json`)**:
   - `firebase.json` at workspace root currently contains:
     ```json
     {
       "dataconnect": {
         "source": "workspace_database/dataconnect"
       },
       "emulators": {
         "auth": { "port": 9099 },
         "dataconnect": { "port": 9399 },
         "ui": { "enabled": true },
         "singleProjectMode": true
       }
     }
     ```

3. **Frontend Integration (`omnichannel_triage_hub/frontend`)**:
   - `frontend/src/lib/dataconnect/index.ts` contains the generated TypeScript SDK with interfaces `VideoTag`, `ListVideoTagsData`, `CreateVideoTagVariables`, action execution functions (`listVideoTags`, `createVideoTag`), and React hook `useVideoTags()`.
   - `frontend/src/lib/firebase.ts` (Line 7) imports `{ connectorConfig }` from `./dataconnect` and initializes `dataConnect = getDataConnect(app, connectorConfig)`.
   - `frontend/src/components/VideoTagsPanel.tsx` (Line 13) imports `useVideoTags`, `VideoTag`, `CreateVideoTagVariables` from `../lib/dataconnect`.
   - `frontend/src/components/PhoneLinkFeed.tsx` (Lines 4-5) imports `VideoTagsPanel` and `VideoTag`.

4. **Python Backend & Locked Silos**:
   - `quick_share_ai_loop/database_sink.py` contains a PostgreSQL connector for `video_tags` with connection pooling, but is under strict cross-session lock ("Music Baptism Image Concepts").
   - There is currently no shared root Python database client for the other tracks (`media_pipeline`, `local_daemon`, `content_creation`, `sports_cards`).

5. **Test Files and Path Hardcodings**:
   - `omnichannel_triage_hub/tests/test_e2e_integration.py` (Line 32) defines `DATACONNECT_DIR = REPO_ROOT / "dataconnect"`.
   - `omnichannel_triage_hub/tests/test_challenger_m4_empirical.py` (Line 34) defines `DATACONNECT_DIR = REPO_ROOT / "dataconnect"`.
   - `omnichannel_triage_hub/frontend/test_adversarial_m3.mjs` (Line 36) defines `dataconnectYamlPath = path.join(hubRoot, 'dataconnect/dataconnect.yaml')`.

---

## 2. Logic Chain

1. **Step 1 (Extraction Location)**: The objective is to lift the Firebase Data Connect schema to the workspace root (`G:\My Drive\GOOGLE ANTIGRAVITY\dataconnect/`). Moving `workspace_database/dataconnect/` to `dataconnect/` places the database definitions at the root level accessible to all tracks.
2. **Step 2 (Configuration Updates)**:
   - `firebase.json` at root must be updated from `"source": "workspace_database/dataconnect"` to `"source": "dataconnect"`.
   - In `dataconnect/connector/connector.yaml`, the relative path `../../omnichannel_triage_hub/frontend/src/lib/dataconnect` from `dataconnect/connector/` (depth 2) resolves cleanly to `G:\My Drive\GOOGLE ANTIGRAVITY\omnichannel_triage_hub\frontend\src\lib\dataconnect`, preserving the exact SDK generation location with zero breaking changes for React imports.
3. **Step 3 (Universal Python Access)**:
   - Since `quick_share_ai_loop/` cannot be modified due to Guardrail R4, creating a shared `dataconnect/db_client.py` provides immediate, reusable PostgreSQL connection pooling, R26 fail-fast auth validation, and typed query/mutation helpers for all Python daemons.
4. **Step 4 (Test Compatibility)**:
   - Existing test files inside `omnichannel_triage_hub` that look for `DATACONNECT_DIR = REPO_ROOT / "dataconnect"` can resolve `REPO_ROOT.parent / "dataconnect"` or be supported via a directory link/copy so all test tiers continue to pass.
5. **Step 5 (Cross-Session Safety)**:
   - Because `dataconnect/` is created at workspace root and no files in `quick_share_ai_loop/`, `video_reviewer.html`, or `daemon_orchestrator.py` are touched, cross-session safety is 100% maintained.

---

## 3. Caveats

- **Active PostgreSQL Instance**: In production/staging, the PostgreSQL instance `omnichannel-postgres` (`omnichannel_db`) requires environment variables (`PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB`). When operating with local emulators, the Firebase Data Connect emulator (`port 9399`) uses PGlite or local Postgres.
- **Legacy Path Backwards-Compatibility**: If any legacy scripts assume `omnichannel_triage_hub/dataconnect`, ensuring both root `dataconnect/` and test paths are aligned will prevent test failures.
- **No other caveats.**

---

## 4. Conclusion

Lifting `dataconnect/` to the workspace root (`G:\My Drive\GOOGLE ANTIGRAVITY\dataconnect/`) is completely feasible, non-disruptive, and provides a unified database layer across React frontend components and Python backend scripts.

### Action Plan for Implementation:
1. Lift `workspace_database/dataconnect` to `G:\My Drive\GOOGLE ANTIGRAVITY\dataconnect/`.
2. Update `firebase.json` at root to `"source": "dataconnect"`.
3. Verify `dataconnect/connector/connector.yaml` generates to `../../omnichannel_triage_hub/frontend/src/lib/dataconnect`.
4. Provide a shared Python database client `dataconnect/db_client.py` with `psycopg2` connection pooling and Rule R26 fail-fast auth.
5. Verify zero modifications to `quick_share_ai_loop/`, `video_reviewer.html`, and `daemon_orchestrator.py`.

---

## 5. Verification Method

To independently verify the implementation:
1. **Schema File Verification**:
   ```powershell
   Test-Path "G:\My Drive\GOOGLE ANTIGRAVITY\dataconnect\dataconnect.yaml"
   Test-Path "G:\My Drive\GOOGLE ANTIGRAVITY\dataconnect\schema\schema.gql"
   Test-Path "G:\My Drive\GOOGLE ANTIGRAVITY\dataconnect\connector\connector.yaml"
   ```
2. **Firebase Configuration Check**:
   Inspect `firebase.json` to ensure `"source": "dataconnect"`.
3. **Frontend SDK & Component Build**:
   ```powershell
   cd "G:\My Drive\GOOGLE ANTIGRAVITY\omnichannel_triage_hub\frontend"
   npm run build
   ```
4. **E2E Test Execution**:
   ```powershell
   cd "G:\My Drive\GOOGLE ANTIGRAVITY\omnichannel_triage_hub"
   pytest tests/test_e2e_integration.py -k "dataconnect"
   ```
5. **Cross-Session Safety Invalidation Condition**:
   Verify `git status` or file timestamps in `quick_share_ai_loop/`, `video_reviewer.html`, and `daemon_orchestrator.py` show 0 modifications.
