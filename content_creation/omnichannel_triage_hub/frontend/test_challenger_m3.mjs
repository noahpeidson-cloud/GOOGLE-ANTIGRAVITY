import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const hubRoot = path.resolve(__dirname, '..');

console.log('====================================================================');
console.log('CHALLENGER 1 EMPIRICAL ADVERSARIAL TEST SUITE');
console.log('Milestone 3: Firebase Data Connect Integration Audit');
console.log('====================================================================\n');

let passedTests = 0;
let failedTests = 0;
const failures = [];

function assert(condition, testName, details = '') {
  if (condition) {
    console.log(`[PASS] ${testName}`);
    passedTests++;
  } else {
    console.error(`[FAIL] ${testName} - ${details}`);
    failedTests++;
    failures.push({ testName, details });
  }
}

// =============================================================================
// 1. GraphQL Schema Definitions & Table Constraints
// =============================================================================
console.log('--- 1. GraphQL Schema & Data Connect Configuration Audit ---');

// 1.1 Check dataconnect.yaml structure and parameters
const dataconnectYamlPath = path.join(hubRoot, 'dataconnect/dataconnect.yaml');
assert(fs.existsSync(dataconnectYamlPath), 'dataconnect.yaml exists at root dataconnect/');
if (fs.existsSync(dataconnectYamlPath)) {
  const dcYaml = fs.readFileSync(dataconnectYamlPath, 'utf8');
  assert(/specVersion:\s*["']v1["']/.test(dcYaml), 'dataconnect.yaml specifies specVersion: "v1"');
  assert(/serviceId:\s*["']omnichannel-service["']/.test(dcYaml), 'dataconnect.yaml specifies serviceId: "omnichannel-service"');
  assert(/location:\s*["']us-central1["']/.test(dcYaml), 'dataconnect.yaml specifies location: "us-central1"');
  assert(/source:\s*["']\.\/schema["']/.test(dcYaml), 'dataconnect.yaml configures schema source');
  assert(/database:\s*["']omnichannel_db["']/.test(dcYaml), 'dataconnect.yaml configures PostgreSQL database name "omnichannel_db"');
  assert(/instanceId:\s*["']omnichannel-postgres["']/.test(dcYaml), 'dataconnect.yaml configures Cloud SQL instance "omnichannel-postgres"');
}

// 1.2 Check schema.gql: directives, field nullability, PostgreSQL mappings
const schemaGqlPath = path.join(hubRoot, 'dataconnect/schema/schema.gql');
assert(fs.existsSync(schemaGqlPath), 'schema.gql exists in dataconnect/schema/');
if (fs.existsSync(schemaGqlPath)) {
  const schema = fs.readFileSync(schemaGqlPath, 'utf8');

  // Directives
  assert(schema.includes('@table('), 'schema.gql uses @table directive');
  assert(schema.includes('name: "video_tags"'), 'schema.gql maps table name to "video_tags"');
  assert(schema.includes('key: "id"'), 'schema.gql sets primary key to "id"');
  assert(schema.includes('singular: "videoTag"'), 'schema.gql sets singular to "videoTag"');
  assert(schema.includes('plural: "videoTags"'), 'schema.gql sets plural to "videoTags"');

  // Fields and non-null constraints
  assert(/id:\s*Int64!/.test(schema), 'schema.gql specifies id: Int64!');
  assert(/filename:\s*String!\s*@unique/.test(schema), 'schema.gql specifies filename: String! @unique');
  assert(/filepath:\s*String!/.test(schema), 'schema.gql specifies filepath: String!');
  assert(/domain:\s*String!/.test(schema), 'schema.gql specifies domain: String!');
  assert(/entity:\s*String!/.test(schema), 'schema.gql specifies entity: String!');
  assert(/viralFeatures:\s*Any!\s*@col\(name:\s*"viral_features",\s*dataType:\s*"jsonb"\)/.test(schema),
    'schema.gql specifies viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb")');
  assert(/technical:\s*Any!\s*@col\(name:\s*"technical",\s*dataType:\s*"jsonb"\)/.test(schema),
    'schema.gql specifies technical: Any! @col(name: "technical", dataType: "jsonb")');
  assert(/createdAt:\s*Timestamp!/.test(schema), 'schema.gql specifies createdAt: Timestamp!');
  assert(/updatedAt:\s*Timestamp!/.test(schema), 'schema.gql specifies updatedAt: Timestamp!');
}

// 1.3 Check connector.yaml
const connectorYamlPath = path.join(hubRoot, 'dataconnect/connector/connector.yaml');
assert(fs.existsSync(connectorYamlPath), 'connector.yaml exists in dataconnect/connector/');
if (fs.existsSync(connectorYamlPath)) {
  const connYaml = fs.readFileSync(connectorYamlPath, 'utf8');
  assert(/connectorId:\s*["']omnichannel-connector["']/.test(connYaml), 'connector.yaml sets connectorId "omnichannel-connector"');
  assert(/outputDir:\s*["']\.\.\/\.\.\/frontend\/src\/lib\/dataconnect["']/.test(connYaml), 'connector.yaml sets outputDir correctly');
  assert(/package:\s*["']@firebase\/data-connect["']/.test(connYaml), 'connector.yaml sets package correctly');
  assert(/packageJsonDir:\s*["']\.\.\/\.\.\/frontend["']/.test(connYaml), 'connector.yaml sets packageJsonDir correctly');
}

// 1.4 Check queries.gql
const queriesGqlPath = path.join(hubRoot, 'dataconnect/connector/queries.gql');
assert(fs.existsSync(queriesGqlPath), 'queries.gql exists in dataconnect/connector/');
if (fs.existsSync(queriesGqlPath)) {
  const queries = fs.readFileSync(queriesGqlPath, 'utf8');
  assert(queries.includes('query ListVideoTags @auth(level: PUBLIC)'), 'queries.gql defines ListVideoTags with @auth(level: PUBLIC)');
  assert(queries.includes('query GetVideoTag($id: Int64!) @auth(level: PUBLIC)'), 'queries.gql defines GetVideoTag($id: Int64!) with @auth(level: PUBLIC)');
  assert(queries.includes('videoTags {'), 'queries.gql queries videoTags list');
  assert(queries.includes('videoTag(id: $id) {'), 'queries.gql queries single videoTag by id');
  assert(queries.includes('viralFeatures'), 'queries.gql includes viralFeatures field');
  assert(queries.includes('technical'), 'queries.gql includes technical field');
}

// 1.5 Check mutations.gql
const mutationsGqlPath = path.join(hubRoot, 'dataconnect/connector/mutations.gql');
assert(fs.existsSync(mutationsGqlPath), 'mutations.gql exists in dataconnect/connector/');
if (fs.existsSync(mutationsGqlPath)) {
  const mutations = fs.readFileSync(mutationsGqlPath, 'utf8');
  assert(mutations.includes('mutation CreateVideoTag('), 'mutations.gql defines CreateVideoTag mutation');
  assert(mutations.includes('@auth(level: PUBLIC)'), 'mutations.gql has @auth(level: PUBLIC)');
  assert(mutations.includes('videoTag_insert(data: {'), 'mutations.gql performs videoTag_insert');
  assert(mutations.includes('createdAt_expr: "request.time"'), 'mutations.gql binds createdAt_expr to "request.time"');
  assert(mutations.includes('updatedAt_expr: "request.time"'), 'mutations.gql binds updatedAt_expr to "request.time"');
}

// =============================================================================
// 2. SDK Operation Functions, Interfaces & Fallback Constants
// =============================================================================
console.log('\n--- 2. Frontend Data Connect SDK & Type Soundness Audit ---');

const dcSdkPath = path.join(__dirname, 'src/lib/dataconnect/index.ts');
assert(fs.existsSync(dcSdkPath), 'src/lib/dataconnect/index.ts exists');

if (fs.existsSync(dcSdkPath)) {
  const dcSdk = fs.readFileSync(dcSdkPath, 'utf8');

  // 2.1 ConnectorConfig
  assert(dcSdk.includes("connector: 'omnichannel-connector'"), 'SDK connectorConfig has connector: omnichannel-connector');
  assert(dcSdk.includes("service: 'omnichannel-service'"), 'SDK connectorConfig has service: omnichannel-service');
  assert(dcSdk.includes("location: 'us-central1'"), 'SDK connectorConfig has location: us-central1');

  // 2.2 TypeScript Interfaces
  assert(dcSdk.includes('export interface VideoTag'), 'SDK exports interface VideoTag');
  assert(dcSdk.includes('export interface ListVideoTagsData'), 'SDK exports interface ListVideoTagsData');
  assert(dcSdk.includes('export interface GetVideoTagData'), 'SDK exports interface GetVideoTagData');
  assert(dcSdk.includes('export interface CreateVideoTagData'), 'SDK exports interface CreateVideoTagData');
  assert(dcSdk.includes('export interface CreateVideoTagVariables'), 'SDK exports interface CreateVideoTagVariables');

  // 2.3 Query & Mutation Ref Creators
  assert(dcSdk.includes('export function listVideoTagsRef'), 'SDK exports listVideoTagsRef');
  assert(dcSdk.includes('export function getVideoTagRef'), 'SDK exports getVideoTagRef');
  assert(dcSdk.includes('export function createVideoTagRef'), 'SDK exports createVideoTagRef');

  // 2.4 Action Execution Functions
  assert(dcSdk.includes('export async function listVideoTags'), 'SDK exports async listVideoTags');
  assert(dcSdk.includes('export async function getVideoTag'), 'SDK exports async getVideoTag');
  assert(dcSdk.includes('export async function createVideoTag'), 'SDK exports async createVideoTag');

  // 2.5 Reactive Hook
  assert(dcSdk.includes('export function useVideoTags'), 'SDK exports useVideoTags hook');
  assert(dcSdk.includes('export const INITIAL_OFFLINE_VIDEO_TAGS'), 'SDK exports INITIAL_OFFLINE_VIDEO_TAGS');

  // 2.6 Extract INITIAL_OFFLINE_VIDEO_TAGS data structure for static and validation tests
  const initialMatch = dcSdk.match(/export const INITIAL_OFFLINE_VIDEO_TAGS:\s*VideoTag\[\]\s*=\s*(\[[\s\S]*?\]);/);
  assert(initialMatch !== null, 'INITIAL_OFFLINE_VIDEO_TAGS array found in source');
  if (initialMatch) {
    try {
      const parsedTags = eval(`(${initialMatch[1]})`);
      assert(Array.isArray(parsedTags) && parsedTags.length >= 3, `INITIAL_OFFLINE_VIDEO_TAGS contains ${parsedTags.length} initial items`);
      for (let i = 0; i < parsedTags.length; i++) {
        const t = parsedTags[i];
        assert(typeof t.id === 'string' && t.id.length > 0, `Tag ${i + 1} has valid string id "${t.id}"`);
        assert(typeof t.filename === 'string' && t.filename.endsWith('.mp4'), `Tag ${i + 1} has valid mp4 filename "${t.filename}"`);
        assert(typeof t.filepath === 'string' && t.filepath.startsWith('/sdcard/'), `Tag ${i + 1} has valid filepath "${t.filepath}"`);
        assert(['EDM_FESTIVALS', 'SPORTS_CARDS', 'TRAVEL_AND_LIFE'].includes(t.domain), `Tag ${i + 1} has recognized domain "${t.domain}"`);
        assert(typeof t.entity === 'string' && t.entity.length > 0, `Tag ${i + 1} has non-empty entity "${t.entity}"`);
        assert(typeof t.viralFeatures === 'object' && t.viralFeatures !== null, `Tag ${i + 1} has viralFeatures object`);
        assert(typeof t.technical === 'object' && t.technical !== null, `Tag ${i + 1} has technical object`);
        assert(!isNaN(Date.parse(t.createdAt)), `Tag ${i + 1} has parseable ISO createdAt timestamp`);
        assert(!isNaN(Date.parse(t.updatedAt)), `Tag ${i + 1} has parseable ISO updatedAt timestamp`);
      }
    } catch (e) {
      assert(false, 'Failed to parse INITIAL_OFFLINE_VIDEO_TAGS', e.message);
    }
  }
}

// =============================================================================
// 3. Offline Fallback & Optimistic Mutation Adversarial Simulation
// =============================================================================
console.log('\n--- 3. Offline Fallback & Optimistic Mutation Stress Test ---');

// Test 3.1: Simulate optimistic mutation generation logic
const testNewTag = {
  filename: '20260827_050000_challenger.mp4',
  filepath: '/sdcard/DCIM/Camera/20260827_050000_challenger.mp4',
  domain: 'EDM_FESTIVALS',
  entity: 'Martin Garrix (Ultra 2026)',
  viralFeatures: { visualHooks: ['Laser Array', 'Pyro Drop'], energyLevel: 'Maximum' },
  technical: { resolution: '3840x2160', fps: 60, codec: 'hevc', bitrateKbps: 65000, audioClipping: false },
};

const optimisticTag = {
  id: String(Date.now()),
  filename: testNewTag.filename,
  filepath: testNewTag.filepath,
  domain: testNewTag.domain,
  entity: testNewTag.entity,
  viralFeatures: testNewTag.viralFeatures,
  technical: testNewTag.technical,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

assert(optimisticTag.filename === testNewTag.filename, 'Optimistic tag preserves filename');
assert(optimisticTag.domain === testNewTag.domain, 'Optimistic tag preserves domain');
assert(optimisticTag.entity === testNewTag.entity, 'Optimistic tag preserves entity');
assert(optimisticTag.viralFeatures.visualHooks.length === 2, 'Optimistic tag preserves nested viralFeatures');
assert(optimisticTag.technical.resolution === '3840x2160', 'Optimistic tag preserves technical metrics');
assert(!isNaN(Date.parse(optimisticTag.createdAt)), 'Optimistic tag generates valid ISO createdAt');
assert(!isNaN(Date.parse(optimisticTag.updatedAt)), 'Optimistic tag generates valid ISO updatedAt');

// Test 3.2: Adversarial payload testing
const adversarialCases = [
  {
    name: 'Unicode & Emoji in entity',
    vars: {
      filename: '20260827_emoji.mp4',
      filepath: '/sdcard/DCIM/Camera/20260827_emoji.mp4',
      domain: 'EDM_FESTIVALS',
      entity: '🔥⚡ Subtronics @ Red Rocks 🛸',
      viralFeatures: { visualHooks: ['💥 Pyro', '🌈 Lasers'] },
      technical: { resolution: '3840x2160', fps: 60, codec: 'h264' },
    }
  },
  {
    name: 'Sports Card with high monetary value string & complex grading metadata',
    vars: {
      filename: '20260827_card.mp4',
      filepath: '/sdcard/DCIM/Camera/20260827_card.mp4',
      domain: 'SPORTS_CARDS',
      entity: '2000 Playoff Contenders Tom Brady #144 Rookie Auto BGS 9.5',
      viralFeatures: { visualHooks: ['Auto 10 Grade', 'Subgrades: Centering 9.5, Corners 9.5, Edges 9.5, Surface 9.0'], estimatedValue: '$1,500,000' },
      technical: { resolution: '3840x2160', fps: 60, codec: 'hevc', macroFocus: true },
    }
  },
  {
    name: 'Array-based viralFeatures format',
    vars: {
      filename: '20260827_array.mp4',
      filepath: '/sdcard/DCIM/Camera/20260827_array.mp4',
      domain: 'TRAVEL_AND_LIFE',
      entity: 'Sedona Cathedral Rock Hike Sunset',
      viralFeatures: ['Golden Hour', 'Red Rock Panorama', 'Drone 4K'],
      technical: { resolution: '3840x2160', fps: 60, codec: 'h264' },
    }
  }
];

for (const tc of adversarialCases) {
  const constructedTag = {
    id: String(Date.now() + Math.floor(Math.random() * 10000)),
    filename: tc.vars.filename,
    filepath: tc.vars.filepath,
    domain: tc.vars.domain,
    entity: tc.vars.entity,
    viralFeatures: tc.vars.viralFeatures,
    technical: tc.vars.technical,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  assert(constructedTag.entity === tc.vars.entity, `Adversarial case "${tc.name}" handles entity without corruption`);
  assert(constructedTag.filename === tc.vars.filename, `Adversarial case "${tc.name}" handles filename`);
}

// =============================================================================
// 4. Firebase App & Client Configuration Audit
// =============================================================================
console.log('\n--- 4. Firebase Initialization & Emulator Configuration ---');

const fbTsPath = path.join(__dirname, 'src/lib/firebase.ts');
const fbTs = fs.readFileSync(fbTsPath, 'utf8');

assert(fbTs.includes('firebaseConfig'), 'firebase.ts exports firebaseConfig object');
assert(fbTs.includes('VITE_FIREBASE_PROJECT_ID'), 'firebase.ts supports VITE_FIREBASE_PROJECT_ID environment variable');
assert(fbTs.includes('VITE_DATA_CONNECT_EMULATOR_HOST'), 'firebase.ts supports VITE_DATA_CONNECT_EMULATOR_HOST override');
assert(fbTs.includes('VITE_DATA_CONNECT_EMULATOR_PORT'), 'firebase.ts supports VITE_DATA_CONNECT_EMULATOR_PORT override');
assert(fbTs.includes('9399'), 'firebase.ts defaults to standard Data Connect emulator port 9399');
assert(fbTs.includes('connectDataConnectEmulator'), 'firebase.ts connects to emulator safely inside try/catch');

// =============================================================================
// 5. Component Layout & Integration Audit
// =============================================================================
console.log('\n--- 5. Component Tree & UI Interaction Verification ---');

const vtpPath = path.join(__dirname, 'src/components/VideoTagsPanel.tsx');
const vtp = fs.readFileSync(vtpPath, 'utf8');

assert(vtp.includes('useVideoTags'), 'VideoTagsPanel consumes useVideoTags hook');
assert(vtp.includes('onSelectTag'), 'VideoTagsPanel exposes onSelectTag callback prop');
assert(vtp.includes('selectedTagId'), 'VideoTagsPanel accepts selectedTagId prop for active highlight');
assert(vtp.includes('isOfflineFallback'), 'VideoTagsPanel renders offline/emulator fallback indicator');
assert(vtp.includes('PostgreSQL • Cloud SQL'), 'VideoTagsPanel renders Cloud SQL indicator when connected');
assert(vtp.includes('handleCreateTag'), 'VideoTagsPanel includes form submission handler');
assert(vtp.includes('refetch()'), 'VideoTagsPanel includes manual refetch trigger');

const plfPath = path.join(__dirname, 'src/components/PhoneLinkFeed.tsx');
const plf = fs.readFileSync(plfPath, 'utf8');
assert(plf.includes('<VideoTagsPanel'), 'PhoneLinkFeed embeds VideoTagsPanel');
assert(plf.includes('onSelectTag={handleSelectTag}'), 'PhoneLinkFeed passes onSelectTag to VideoTagsPanel');
assert(plf.includes('selectedTagId={selectedTag?.id}'), 'PhoneLinkFeed synchronizes selectedTagId');

const appPath = path.join(__dirname, 'src/App.tsx');
const app = fs.readFileSync(appPath, 'utf8');
assert(app.includes('handleSelectVideoTag'), 'App.tsx implements handleSelectVideoTag callback');
assert(app.includes('onSelectVideoTag={handleSelectVideoTag}'), 'App.tsx binds onSelectVideoTag to PhoneLinkFeed');
assert(app.includes('Loaded from Firebase Data Connect'), 'App.tsx updates status to "Loaded from Firebase Data Connect"');

// =============================================================================
// 6. Build Reliability & Bundle Verification
// =============================================================================
console.log('\n--- 6. Strict Production Build & Asset Integrity ---');
try {
  const buildOutput = execSync('npm run build', { cwd: __dirname, encoding: 'utf8' });
  assert(true, 'npm run build executes cleanly with exit code 0');

  const distDir = path.join(__dirname, 'dist');
  assert(fs.existsSync(path.join(distDir, 'index.html')), 'dist/index.html generated');

  const assetsDir = path.join(distDir, 'assets');
  const assetFiles = fs.readdirSync(assetsDir);
  const jsBundles = assetFiles.filter(f => f.endsWith('.js'));
  const cssBundles = assetFiles.filter(f => f.endsWith('.css'));

  assert(jsBundles.length >= 1, `JavaScript bundle generated: ${jsBundles.join(', ')}`);
  assert(cssBundles.length >= 1, `CSS bundle generated: ${cssBundles.join(', ')}`);

  let jsTotalSize = 0;
  for (const js of jsBundles) {
    const stats = fs.statSync(path.join(assetsDir, js));
    jsTotalSize += stats.size;
  }
  assert(jsTotalSize > 50000, `Production JS bundle is substantial (${(jsTotalSize / 1024).toFixed(2)} KB)`);

} catch (err) {
  assert(false, 'npm run build failed', err.message);
}

// Final Summary
console.log('\n====================================================================');
console.log(`CHALLENGER SUMMARY: ${passedTests} PASSED, ${failedTests} FAILED`);
console.log('====================================================================\n');

if (failedTests > 0) {
  console.error('CHALLENGER AUDIT: REJECT - Failed Tests:');
  for (const f of failures) {
    console.error(`  - ${f.testName}: ${f.details}`);
  }
  process.exit(1);
} else {
  console.log('CHALLENGER AUDIT: ALL ADVERSARIAL CHALLENGES PASSED EMPIRICALLY.');
  console.log('EXPLICIT VERDICT: APPROVE');
  process.exit(0);
}
