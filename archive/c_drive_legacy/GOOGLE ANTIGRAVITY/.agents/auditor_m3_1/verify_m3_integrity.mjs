import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const hubRoot = path.resolve(__dirname, '../../omnichannel_triage_hub');

console.log('================================================================');
console.log('FORENSIC AUDITOR 1 - INDEPENDENT INTEGRITY VERIFICATION (M3)');
console.log('Firebase Data Connect Backend & Frontend SDK Deep Forensic Audit');
console.log('================================================================\n');

let passed = 0;
let failed = 0;
const findings = [];

function check(assertion, testName, evidence = '') {
  if (assertion) {
    console.log(`[PASS] ${testName}`);
    passed++;
  } else {
    console.error(`[FAIL] ${testName} -> ${evidence}`);
    failed++;
    findings.push({ testName, evidence });
  }
}

// -----------------------------------------------------------------------------
// Check 1: File Existence & Structural Placement
// -----------------------------------------------------------------------------
console.log('--- Phase 1: Structural Placement & File Integrity ---');

const dataconnectDir = path.join(hubRoot, 'dataconnect');
const schemaDir = path.join(dataconnectDir, 'schema');
const connectorDir = path.join(dataconnectDir, 'connector');
const frontendSdkDir = path.join(hubRoot, 'frontend/src/lib/dataconnect');

check(fs.existsSync(path.join(dataconnectDir, 'dataconnect.yaml')), 'dataconnect/dataconnect.yaml exists');
check(fs.existsSync(path.join(schemaDir, 'schema.gql')), 'dataconnect/schema/schema.gql exists');
check(fs.existsSync(path.join(connectorDir, 'connector.yaml')), 'dataconnect/connector/connector.yaml exists');
check(fs.existsSync(path.join(connectorDir, 'queries.gql')), 'dataconnect/connector/queries.gql exists');
check(fs.existsSync(path.join(connectorDir, 'mutations.gql')), 'dataconnect/connector/mutations.gql exists');
check(fs.existsSync(path.join(frontendSdkDir, 'index.ts')), 'frontend/src/lib/dataconnect/index.ts exists');
check(fs.existsSync(path.join(hubRoot, 'frontend/src/lib/firebase.ts')), 'frontend/src/lib/firebase.ts exists');
check(fs.existsSync(path.join(hubRoot, 'frontend/src/components/VideoTagsPanel.tsx')), 'frontend/src/components/VideoTagsPanel.tsx exists');

// -----------------------------------------------------------------------------
// Check 2: dataconnect.yaml Schema Configuration
// -----------------------------------------------------------------------------
console.log('\n--- Phase 2: dataconnect.yaml Configuration Audit ---');
const dcYaml = fs.readFileSync(path.join(dataconnectDir, 'dataconnect.yaml'), 'utf8');
check(dcYaml.includes('specVersion: "v1"'), 'Spec version is v1');
check(dcYaml.includes('serviceId: "omnichannel-service"'), 'Service ID matches "omnichannel-service"');
check(dcYaml.includes('location: "us-central1"'), 'Location matches "us-central1"');
check(dcYaml.includes('source: "./schema"'), 'Schema source path configured as "./schema"');
check(dcYaml.includes('database: "omnichannel_db"'), 'PostgreSQL database is "omnichannel_db"');
check(dcYaml.includes('instanceId: "omnichannel-postgres"'), 'Cloud SQL instance ID configured');
check(dcYaml.includes('connectorDirs: ["./connector"]'), 'Connector dirs configured as ["./connector"]');

// -----------------------------------------------------------------------------
// Check 3: schema.gql PostgreSQL Table Schema Analysis
// -----------------------------------------------------------------------------
console.log('\n--- Phase 3: PostgreSQL GraphQL Table Schema Forensic Check ---');
const schemaGql = fs.readFileSync(path.join(schemaDir, 'schema.gql'), 'utf8');
check(schemaGql.includes('type VideoTag @table('), 'Type VideoTag has @table directive');
check(schemaGql.includes('name: "video_tags"'), 'Maps to PostgreSQL table "video_tags"');
check(schemaGql.includes('key: "id"'), 'Primary key designated as "id"');
check(schemaGql.includes('singular: "videoTag"'), 'Singular entity name is "videoTag"');
check(schemaGql.includes('plural: "videoTags"'), 'Plural entity name is "videoTags"');
check(schemaGql.includes('id: Int64!'), 'Field id is Int64!');
check(schemaGql.includes('filename: String! @unique'), 'Field filename is String! @unique');
check(schemaGql.includes('filepath: String!'), 'Field filepath is String!');
check(schemaGql.includes('domain: String!'), 'Field domain is String!');
check(schemaGql.includes('entity: String!'), 'Field entity is String!');
check(schemaGql.includes('viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb")'), 'Field viralFeatures maps to jsonb column "viral_features"');
check(schemaGql.includes('technical: Any! @col(name: "technical", dataType: "jsonb")'), 'Field technical maps to jsonb column "technical"');
check(schemaGql.includes('createdAt: Timestamp!'), 'Field createdAt is Timestamp!');
check(schemaGql.includes('updatedAt: Timestamp!'), 'Field updatedAt is Timestamp!');

// -----------------------------------------------------------------------------
// Check 4: connector.yaml, queries.gql, mutations.gql Operations
// -----------------------------------------------------------------------------
console.log('\n--- Phase 4: GraphQL Operations & Connector Audit ---');
const connYaml = fs.readFileSync(path.join(connectorDir, 'connector.yaml'), 'utf8');
check(connYaml.includes('connectorId: "omnichannel-connector"'), 'Connector ID is "omnichannel-connector"');
check(connYaml.includes('outputDir: "../../frontend/src/lib/dataconnect"'), 'Output directory points to frontend SDK path');
check(connYaml.includes('package: "@firebase/data-connect"'), 'Target SDK package is @firebase/data-connect');

const queriesGql = fs.readFileSync(path.join(connectorDir, 'queries.gql'), 'utf8');
check(queriesGql.includes('query ListVideoTags @auth(level: PUBLIC)'), 'ListVideoTags query has PUBLIC auth');
check(queriesGql.includes('videoTags {'), 'ListVideoTags queries videoTags collection');
check(queriesGql.includes('query GetVideoTag($id: Int64!) @auth(level: PUBLIC)'), 'GetVideoTag query takes Int64! parameter and has PUBLIC auth');

const mutationsGql = fs.readFileSync(path.join(connectorDir, 'mutations.gql'), 'utf8');
check(mutationsGql.includes('mutation CreateVideoTag('), 'CreateVideoTag mutation defined');
check(mutationsGql.includes('@auth(level: PUBLIC)'), 'CreateVideoTag has PUBLIC auth');
check(mutationsGql.includes('videoTag_insert(data: {'), 'CreateVideoTag invokes videoTag_insert');
check(mutationsGql.includes('createdAt_expr: "request.time"'), 'Binds createdAt_expr to request.time');
check(mutationsGql.includes('updatedAt_expr: "request.time"'), 'Binds updatedAt_expr to request.time');

// -----------------------------------------------------------------------------
// Check 5: Frontend TypeScript SDK & Facade Analysis
// -----------------------------------------------------------------------------
console.log('\n--- Phase 5: Frontend TypeScript SDK & Facade Inspection ---');
const sdkContent = fs.readFileSync(path.join(frontendSdkDir, 'index.ts'), 'utf8');

// 5.1 Real imports from firebase/data-connect
check(sdkContent.includes("from 'firebase/data-connect'") || sdkContent.includes('from "@firebase/data-connect"'), 'SDK imports genuine symbols from firebase/data-connect');
check(sdkContent.includes('queryRef'), 'SDK imports queryRef');
check(sdkContent.includes('mutationRef'), 'SDK imports mutationRef');
check(sdkContent.includes('executeQuery'), 'SDK imports executeQuery');
check(sdkContent.includes('executeMutation'), 'SDK imports executeMutation');
check(sdkContent.includes('getDataConnect'), 'SDK imports getDataConnect');

// 5.2 Real function implementations (Not empty dummy facades)
check(sdkContent.includes('return queryRef<ListVideoTagsData'), 'listVideoTagsRef constructs authentic queryRef');
check(sdkContent.includes('return queryRef<GetVideoTagData, GetVideoTagVariables>'), 'getVideoTagRef constructs authentic queryRef');
check(sdkContent.includes('return mutationRef<CreateVideoTagData, CreateVideoTagVariables>'), 'createVideoTagRef constructs authentic mutationRef');
check(sdkContent.includes('return executeQuery(listVideoTagsRef(dc, vars))'), 'listVideoTags executes authentic executeQuery');
check(sdkContent.includes('return executeQuery(getVideoTagRef(vars, dc))'), 'getVideoTag executes authentic executeQuery');
check(sdkContent.includes('return executeMutation(createVideoTagRef(vars, dc))'), 'createVideoTag executes authentic executeMutation');

// 5.3 Reactive Hook & Offline Resilience
check(sdkContent.includes('export function useVideoTags'), 'Exports useVideoTags React hook');
check(sdkContent.includes('const result = await listVideoTags(dc, vars)'), 'useVideoTags attempts authentic live query');
check(sdkContent.includes('setIsOfflineFallback(false)'), 'Sets fallback to false upon live query success');
check(sdkContent.includes('setIsOfflineFallback(true)'), 'Handles offline/unconnected emulator fallback');
check(sdkContent.includes('await createVideoTag(newTagVars, dc)'), 'addTag calls genuine createVideoTag mutation');

// -----------------------------------------------------------------------------
// Check 6: Firebase Client Initialization & Emulator Fallback
// -----------------------------------------------------------------------------
console.log('\n--- Phase 6: Firebase Client Initialization Audit ---');
const fbClient = fs.readFileSync(path.join(hubRoot, 'frontend/src/lib/firebase.ts'), 'utf8');
check(fbClient.includes('initializeApp(firebaseConfig)'), 'Calls initializeApp with firebaseConfig');
check(fbClient.includes('getDataConnect(app, connectorConfig)'), 'Initializes DataConnect singleton with connectorConfig');
check(fbClient.includes('connectDataConnectEmulator(dataConnect, emulatorHost, emulatorPort)'), 'Connects to Data Connect emulator for local development');

// -----------------------------------------------------------------------------
// Check 7: UI Component & State Integration
// -----------------------------------------------------------------------------
console.log('\n--- Phase 7: UI Component & State Integration Audit ---');
const panelCode = fs.readFileSync(path.join(hubRoot, 'frontend/src/components/VideoTagsPanel.tsx'), 'utf8');
check(panelCode.includes('useVideoTags()'), 'VideoTagsPanel consumes useVideoTags hook');
check(panelCode.includes('handleCreateTag'), 'VideoTagsPanel provides tag creation form handler');
check(panelCode.includes('addTag(newTagVars)'), 'VideoTagsPanel dispatches addTag mutation');
check(panelCode.includes('refetch()'), 'VideoTagsPanel provides manual refetch trigger');
check(panelCode.includes('onSelectTag && onSelectTag(tag)'), 'VideoTagsPanel emits onSelectTag callback');

const feedCode = fs.readFileSync(path.join(hubRoot, 'frontend/src/components/PhoneLinkFeed.tsx'), 'utf8');
check(feedCode.includes('<VideoTagsPanel'), 'PhoneLinkFeed embeds VideoTagsPanel component');
check(feedCode.includes('selectedTagId={selectedTag?.id}'), 'PhoneLinkFeed tracks selected tag ID');
check(feedCode.includes('onSelectTag={handleSelectTag}'), 'PhoneLinkFeed receives tag selection event');

const appCode = fs.readFileSync(path.join(hubRoot, 'frontend/src/App.tsx'), 'utf8');
check(appCode.includes('onSelectVideoTag={handleSelectVideoTag}'), 'App passes handleSelectVideoTag callback to feed');
check(appCode.includes('action: \'Loaded from Firebase Data Connect\''), 'App updates vision result when tag is selected');

// -----------------------------------------------------------------------------
// Summary & Exit
// -----------------------------------------------------------------------------
console.log('\n================================================================');
console.log(`INTEGRITY VERIFICATION RESULTS: ${passed} PASSED, ${failed} FAILED`);
console.log('================================================================\n');

if (failed > 0) {
  console.error('VERDICT: INTEGRITY VIOLATION DETECTED');
  findings.forEach(f => console.error(` - ${f.testName}: ${f.evidence}`));
  process.exit(1);
} else {
  console.log('VERDICT: CLEAN (All integrity and architectural checks verified)');
  process.exit(0);
}
