## 2026-08-27T11:48:18Z
You are Worker M3 assigned to implement Milestone 3 (Firebase Data Connect Integration) for Omnichannel Triage Hub.

Your working directory is: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_m3\
Read the original request at: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md
Read the project specifications at: G:\My Drive\GOOGLE ANTIGRAVITY\PROJECT.md
Read the survey analysis at: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_survey_2\analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write Ownership:
`g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/dataconnect/`
`g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/frontend/src/lib/`
`g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/frontend/src/components/`

Scope & Deliverables:
1. Initialize Firebase Data Connect configuration in `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/dataconnect/`:
   - `dataconnect.yaml`: Root configuration pointing to schema and connector directories, specifying serviceId (`omnichannel-service`), location (`us-central1`).
   - `schema/schema.gql`: Define the PostgreSQL table schema for `video_tags`:
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
   - `connector/connector.yaml`: Connector configuration with connectorId (`omnichannel-connector`) and SDK generation targets:
     ```yaml
     connectorId: "omnichannel-connector"
     generate:
       javascriptSdk:
         outputDir: "../../frontend/src/lib/dataconnect"
         package: "@firebase/data-connect"
         packageJsonDir: "../../frontend"
     ```
   - `connector/queries.gql`:
     ```graphql
     query ListVideoTags @auth(level: PUBLIC) {
       videoTags {
         id
         filename
         filepath
         domain
         entity
         viralFeatures
         technical
         createdAt
         updatedAt
       }
     }

     query GetVideoTag($id: Int64!) @auth(level: PUBLIC) {
       videoTag(id: $id) {
         id
         filename
         filepath
         domain
         entity
         viralFeatures
         technical
         createdAt
         updatedAt
       }
     }
     ```
   - `connector/mutations.gql`:
     ```graphql
     mutation CreateVideoTag($filename: String!, $filepath: String!, $domain: String!, $entity: String!, $viralFeatures: Any!, $technical: Any!) @auth(level: PUBLIC) {
       videoTag_insert(data: {
         filename: $filename,
         filepath: $filepath,
         domain: $domain,
         entity: $entity,
         viralFeatures: $viralFeatures,
         technical: $technical,
         createdAt_expr: "request.time",
         updatedAt_expr: "request.time"
       })
     }
     ```
2. Configure Firebase in React Frontend:
   - In `frontend/`: ensure `firebase` and `@firebase/data-connect` packages are configured in `package.json` and installed.
   - `frontend/src/lib/firebase.ts`: Initialize Firebase app and Data Connect client, with automatic local emulator connection (`connectDataConnectEmulator(dc, 'localhost', 9399)`) when in development mode.
   - `frontend/src/lib/dataconnect/`: Implement the generated TypeScript SDK modules (`index.ts`, types, connector definition, `listVideoTags`, `createVideoTag`, `getVideoTag`, and client query hooks with resilient fallback for offline/emulator environments).
   - `frontend/src/components/VideoTagsPanel.tsx` / `frontend/src/components/PhoneLinkFeed.tsx`: Integrate the `listVideoTags` query hook into the frontend UI so video tags are reactively queried and displayed from Firebase Data Connect.
3. Verification:
   - Run `npm run build` in `frontend/` to confirm strict TypeScript compilation of the Data Connect SDK and components.
   - Write and run unit/integration tests verifying schema syntax, GraphQL document parsing, query definitions, and SDK exports.
4. Document all artifacts and test results in `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\worker_m3\handoff.md`.
5. Send a message to parent when completed.
