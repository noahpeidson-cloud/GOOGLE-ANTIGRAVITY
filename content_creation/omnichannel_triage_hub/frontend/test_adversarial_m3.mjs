import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const hubRoot = path.resolve(__dirname, '..');

console.log('====================================================');
console.log('OMNICHANNEL TRIAGE HUB - M3 ADVERSARIAL TEST SUITE');
console.log('Firebase Data Connect Backend & Frontend SDK Audit');
console.log('====================================================\n');

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

// -----------------------------------------------------------------------------
// 1. Data Connect Backend Configuration & Schema Tests
// -----------------------------------------------------------------------------
console.log('--- 1. Firebase Data Connect Configuration & Schema ---');

// 1.1 dataconnect.yaml
const dataconnectYamlPath = path.join(hubRoot, 'dataconnect/dataconnect.yaml');
assert(fs.existsSync(dataconnectYamlPath), 'dataconnect.yaml exists in dataconnect/');
if (fs.existsSync(dataconnectYamlPath)) {
  const dcYaml = fs.readFileSync(dataconnectYamlPath, 'utf8');
  assert(dcYaml.includes('serviceId: "omnichannel-service"'), 'dataconnect.yaml specifies serviceId "omnichannel-service"');
  assert(dcYaml.includes('location: "us-central1"'), 'dataconnect.yaml specifies location "us-central1"');
  assert(dcYaml.includes('source: "./schema"'), 'dataconnect.yaml configures schema source directory');
  assert(dcYaml.includes('connectorDirs: ["./connector"]'), 'dataconnect.yaml configures connectorDirs');
  assert(dcYaml.includes('postgresql:'), 'dataconnect.yaml configures PostgreSQL datasource');
}

// 1.2 schema/schema.gql
const schemaGqlPath = path.join(hubRoot, 'dataconnect/schema/schema.gql');
assert(fs.existsSync(schemaGqlPath), 'schema.gql exists in dataconnect/schema/');
if (fs.existsSync(schemaGqlPath)) {
  const schemaContent = fs.readFileSync(schemaGqlPath, 'utf8');
  assert(schemaContent.includes('type VideoTag @table('), 'schema.gql defines VideoTag type with @table directive');
  assert(schemaContent.includes('name: "video_tags"'), 'schema.gql maps table name to "video_tags"');
  assert(schemaContent.includes('key: "id"'), 'schema.gql specifies primary key "id"');
  assert(schemaContent.includes('singular: "videoTag"'), 'schema.gql specifies singular name "videoTag"');
  assert(schemaContent.includes('plural: "videoTags"'), 'schema.gql specifies plural name "videoTags"');
  assert(schemaContent.includes('id: Int64!'), 'schema.gql defines id as Int64!');
  assert(schemaContent.includes('filename: String! @unique'), 'schema.gql defines filename as String! @unique');
  assert(schemaContent.includes('filepath: String!'), 'schema.gql defines filepath as String!');
  assert(schemaContent.includes('domain: String!'), 'schema.gql defines domain as String!');
  assert(schemaContent.includes('entity: String!'), 'schema.gql defines entity as String!');
  assert(schemaContent.includes('viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb")'), 'schema.gql defines viralFeatures as JSONB');
  assert(schemaContent.includes('technical: Any! @col(name: "technical", dataType: "jsonb")'), 'schema.gql defines technical as JSONB');
  assert(schemaContent.includes('createdAt: Timestamp!'), 'schema.gql defines createdAt as Timestamp!');
  assert(schemaContent.includes('updatedAt: Timestamp!'), 'schema.gql defines updatedAt as Timestamp!');
}

// 1.3 connector/connector.yaml
const connectorYamlPath = path.join(hubRoot, 'dataconnect/connector/connector.yaml');
assert(fs.existsSync(connectorYamlPath), 'connector.yaml exists in dataconnect/connector/');
if (fs.existsSync(connectorYamlPath)) {
  const connYaml = fs.readFileSync(connectorYamlPath, 'utf8');
  assert(connYaml.includes('connectorId: "omnichannel-connector"'), 'connector.yaml specifies connectorId "omnichannel-connector"');
  assert(connYaml.includes('javascriptSdk:'), 'connector.yaml configures javascriptSdk generation target');
  assert(connYaml.includes('outputDir: "../../frontend/src/lib/dataconnect"'), 'connector.yaml sets outputDir to frontend/src/lib/dataconnect');
  assert(connYaml.includes('package: "@firebase/data-connect"'), 'connector.yaml sets package to @firebase/data-connect');
  assert(connYaml.includes('packageJsonDir: "../../frontend"'), 'connector.yaml sets packageJsonDir to frontend');
}

// 1.4 connector/queries.gql
const queriesGqlPath = path.join(hubRoot, 'dataconnect/connector/queries.gql');
assert(fs.existsSync(queriesGqlPath), 'queries.gql exists in dataconnect/connector/');
if (fs.existsSync(queriesGqlPath)) {
  const queriesContent = fs.readFileSync(queriesGqlPath, 'utf8');
  assert(queriesContent.includes('query ListVideoTags @auth(level: PUBLIC)'), 'queries.gql defines ListVideoTags query with PUBLIC auth');
  assert(queriesContent.includes('videoTags {'), 'queries.gql queries videoTags collection');
  assert(queriesContent.includes('query GetVideoTag($id: Int64!) @auth(level: PUBLIC)'), 'queries.gql defines GetVideoTag query by id with PUBLIC auth');
  assert(queriesContent.includes('videoTag(id: $id) {'), 'queries.gql queries single videoTag by id');
}

// 1.5 connector/mutations.gql
const mutationsGqlPath = path.join(hubRoot, 'dataconnect/connector/mutations.gql');
assert(fs.existsSync(mutationsGqlPath), 'mutations.gql exists in dataconnect/connector/');
if (fs.existsSync(mutationsGqlPath)) {
  const mutationsContent = fs.readFileSync(mutationsGqlPath, 'utf8');
  assert(mutationsContent.includes('mutation CreateVideoTag('), 'mutations.gql defines CreateVideoTag mutation');
  assert(mutationsContent.includes('@auth(level: PUBLIC)'), 'mutations.gql enforces auth level PUBLIC');
  assert(mutationsContent.includes('videoTag_insert(data: {'), 'mutations.gql executes videoTag_insert');
  assert(mutationsContent.includes('createdAt_expr: "request.time"'), 'mutations.gql binds createdAt_expr to request.time');
  assert(mutationsContent.includes('updatedAt_expr: "request.time"'), 'mutations.gql binds updatedAt_expr to request.time');
}

// -----------------------------------------------------------------------------
// 2. React Frontend Firebase & Data Connect SDK Tests
// -----------------------------------------------------------------------------
console.log('\n--- 2. React Frontend Firebase & SDK Integration ---');

// 2.1 frontend/package.json
const packageJsonPath = path.join(__dirname, 'package.json');
const pkgJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
assert(pkgJson.dependencies['firebase'] !== undefined, 'package.json includes firebase dependency');
assert(pkgJson.dependencies['@firebase/data-connect'] !== undefined, 'package.json includes @firebase/data-connect dependency');

// 2.2 frontend/src/lib/firebase.ts
const firebaseTsPath = path.join(__dirname, 'src/lib/firebase.ts');
assert(fs.existsSync(firebaseTsPath), 'src/lib/firebase.ts exists');
if (fs.existsSync(firebaseTsPath)) {
  const fbTs = fs.readFileSync(firebaseTsPath, 'utf8');
  assert(fbTs.includes('initializeApp'), 'firebase.ts imports initializeApp');
  assert(fbTs.includes('getDataConnect'), 'firebase.ts imports getDataConnect');
  assert(fbTs.includes('connectDataConnectEmulator'), 'firebase.ts imports connectDataConnectEmulator');
  assert(fbTs.includes('connectorConfig'), 'firebase.ts imports connectorConfig from dataconnect SDK');
  assert(fbTs.includes('connectDataConnectEmulator(dataConnect, emulatorHost, emulatorPort)'), 'firebase.ts connects to emulator in dev mode');
}

// 2.3 frontend/src/lib/dataconnect/index.ts
const dcSdkPath = path.join(__dirname, 'src/lib/dataconnect/index.ts');
assert(fs.existsSync(dcSdkPath), 'src/lib/dataconnect/index.ts exists');
if (fs.existsSync(dcSdkPath)) {
  const dcSdk = fs.readFileSync(dcSdkPath, 'utf8');
  assert(dcSdk.includes('connector: \'omnichannel-connector\''), 'dataconnect SDK specifies connector omnichannel-connector');
  assert(dcSdk.includes('service: \'omnichannel-service\''), 'dataconnect SDK specifies service omnichannel-service');
  assert(dcSdk.includes('location: \'us-central1\''), 'dataconnect SDK specifies location us-central1');
  assert(dcSdk.includes('export function listVideoTagsRef'), 'dataconnect SDK exports listVideoTagsRef');
  assert(dcSdk.includes('export function getVideoTagRef'), 'dataconnect SDK exports getVideoTagRef');
  assert(dcSdk.includes('export function createVideoTagRef'), 'dataconnect SDK exports createVideoTagRef');
  assert(dcSdk.includes('export async function listVideoTags'), 'dataconnect SDK exports listVideoTags action shortcut');
  assert(dcSdk.includes('export async function getVideoTag'), 'dataconnect SDK exports getVideoTag action shortcut');
  assert(dcSdk.includes('export async function createVideoTag'), 'dataconnect SDK exports createVideoTag action shortcut');
  assert(dcSdk.includes('export function useVideoTags'), 'dataconnect SDK exports reactive useVideoTags hook');
  assert(dcSdk.includes('isOfflineFallback'), 'dataconnect SDK provides offline fallback state');
  assert(dcSdk.includes('INITIAL_OFFLINE_VIDEO_TAGS'), 'dataconnect SDK exports INITIAL_OFFLINE_VIDEO_TAGS');
}

// 2.4 frontend/src/components/VideoTagsPanel.tsx
const panelPath = path.join(__dirname, 'src/components/VideoTagsPanel.tsx');
assert(fs.existsSync(panelPath), 'src/components/VideoTagsPanel.tsx exists');
if (fs.existsSync(panelPath)) {
  const panelContent = fs.readFileSync(panelPath, 'utf8');
  assert(panelContent.includes('useVideoTags'), 'VideoTagsPanel uses useVideoTags hook');
  assert(panelContent.includes('Firebase Data Connect'), 'VideoTagsPanel displays header title');
  assert(panelContent.includes('isOfflineFallback'), 'VideoTagsPanel handles offline/emulator fallback indicator');
  assert(panelContent.includes('refetch()'), 'VideoTagsPanel provides refetch capability');
  assert(panelContent.includes('addTag('), 'VideoTagsPanel provides create tag mutation form');
  assert(panelContent.includes('EDM_FESTIVALS'), 'VideoTagsPanel supports EDM domain selection');
  assert(panelContent.includes('SPORTS_CARDS'), 'VideoTagsPanel supports Sports Cards domain selection');
}

// 2.5 frontend/src/components/PhoneLinkFeed.tsx integration
const feedPath = path.join(__dirname, 'src/components/PhoneLinkFeed.tsx');
if (fs.existsSync(feedPath)) {
  const feedContent = fs.readFileSync(feedPath, 'utf8');
  assert(feedContent.includes('VideoTagsPanel'), 'PhoneLinkFeed embeds VideoTagsPanel component');
  assert(feedContent.includes('onSelectVideoTag'), 'PhoneLinkFeed supports onSelectVideoTag callback');
  assert(feedContent.includes('handleSelectTag'), 'PhoneLinkFeed handles tag selection events');
}

// 2.6 frontend/src/App.tsx integration
const appPath = path.join(__dirname, 'src/App.tsx');
if (fs.existsSync(appPath)) {
  const appContent = fs.readFileSync(appPath, 'utf8');
  assert(appContent.includes('onSelectVideoTag={handleSelectVideoTag}'), 'App.tsx connects onSelectVideoTag handler');
  assert(appContent.includes('Loaded from Firebase Data Connect'), 'App.tsx updates visionResult action when tag is selected');
}

// -----------------------------------------------------------------------------
// 3. TypeScript Compilation & Production Build Verification
// -----------------------------------------------------------------------------
console.log('\n--- 3. Strict TypeScript Compilation & Vite Bundling ---');
try {
  const buildOutput = execSync('npm run build', { cwd: __dirname, encoding: 'utf8' });
  console.log('Build Output Snippet:\n' + buildOutput.trim().split('\n').slice(-8).join('\n'));
  assert(true, 'npm run build completed with exit code 0');

  const distAssets = path.join(__dirname, 'dist/assets');
  assert(fs.existsSync(distAssets), 'dist/assets directory exists');

  const files = fs.readdirSync(distAssets);
  const jsFiles = files.filter((f) => f.endsWith('.js'));
  assert(jsFiles.length > 0, `Production JS bundle generated (${jsFiles.join(', ')})`);

  // Verify that Data Connect identifiers are bundled into the distribution
  let bundleHasDataConnect = false;
  for (const jsFile of jsFiles) {
    const content = fs.readFileSync(path.join(distAssets, jsFile), 'utf8');
    if (
      content.includes('omnichannel-connector') ||
      content.includes('omnichannel-service') ||
      content.includes('ListVideoTags') ||
      content.includes('VideoTagsPanel')
    ) {
      bundleHasDataConnect = true;
      break;
    }
  }
  assert(bundleHasDataConnect, 'Production bundle contains Data Connect connector/service tokens');
} catch (err) {
  assert(false, 'npm run build failed', err.message);
}

// Summary
console.log('\n====================================================');
console.log(`TEST RESULTS: ${passedTests} PASSED, ${failedTests} FAILED`);
console.log('====================================================\n');

if (failedTests > 0) {
  console.error('Failure Details:');
  for (const f of failures) {
    console.error(`- ${f.testName}: ${f.details}`);
  }
  process.exit(1);
} else {
  console.log('ALL EMPIRICAL TESTS PASSED SUCCESSFULLY.');
  process.exit(0);
}
