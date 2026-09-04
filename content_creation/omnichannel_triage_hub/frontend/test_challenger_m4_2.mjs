/**
 * Empirical Adversarial Challenger 2 Test Suite (Node.js)
 * Milestone 4: E2E Integration & Verification Audit
 * Omnichannel Triage Hub
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_DIR = __dirname;
const REPO_ROOT = path.resolve(__dirname, '..');
const SRC_DIR = path.join(FRONTEND_DIR, 'src');
const COMPONENTS_DIR = path.join(SRC_DIR, 'components');
const LIB_DIR = path.join(SRC_DIR, 'lib');
const DATACONNECT_DIR = path.join(REPO_ROOT, 'dataconnect');

let passCount = 0;
let failCount = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`[PASS] ${message}`);
    passCount++;
  } else {
    console.error(`[FAIL] ${message}`);
    failCount++;
  }
}

console.log('====================================================================');
console.log('CHALLENGER 2 EMPIRICAL ADVERSARIAL TEST SUITE (Node.js)');
console.log('Milestone 4: E2E Integration & Verification Audit');
console.log('====================================================================\n');

// -----------------------------------------------------------------------------
// 1. REST API Client Structure & Offline Fallback Contract
// -----------------------------------------------------------------------------
console.log('--- 1. REST API Client Contract & Graceful Fallback ---');
const apiPath = path.join(LIB_DIR, 'api.ts');
assert(fs.existsSync(apiPath), 'frontend/src/lib/api.ts exists');
const apiSrc = fs.readFileSync(apiPath, 'utf-8');

assert(apiSrc.includes('export interface AdbPullOptions'), 'api.ts exports AdbPullOptions interface');
assert(apiSrc.includes('export interface AdbPullResponse'), 'api.ts exports AdbPullResponse interface');
assert(apiSrc.includes('export interface CaptureScreenOptions'), 'api.ts exports CaptureScreenOptions interface');
assert(apiSrc.includes('export interface CaptureScreenResponse'), 'api.ts exports CaptureScreenResponse interface');
assert(apiSrc.includes('export interface HealthResponse'), 'api.ts exports HealthResponse interface');
assert(apiSrc.includes('export interface DevicesResponse'), 'api.ts exports DevicesResponse interface');
assert(apiSrc.includes('export interface StagingInventoryResponse'), 'api.ts exports StagingInventoryResponse interface');
assert(apiSrc.includes('export const FALLBACK_POSTER_FRAME'), 'api.ts exports FALLBACK_POSTER_FRAME constant');

// Check that functions have timeout and fallback safety
assert(apiSrc.includes('fetchWithTimeout'), 'api.ts uses fetchWithTimeout helper for abort protection');
assert(apiSrc.includes('is_fallback: true'), 'api.ts fallback handlers set is_fallback: true');
assert(apiSrc.includes('564166656'), 'api.ts fallback returns 538 MB simulated transfer payload');
assert(apiSrc.includes('data:image/svg+xml'), 'FALLBACK_POSTER_FRAME is valid SVG data URI');

// -----------------------------------------------------------------------------
// 2. Multi-Step UI Wiring & Event Handlers in App.tsx
// -----------------------------------------------------------------------------
console.log('\n--- 2. App.tsx UI Wiring & Event Handlers ---');
const appPath = path.join(SRC_DIR, 'App.tsx');
assert(fs.existsSync(appPath), 'src/App.tsx exists');
const appSrc = fs.readFileSync(appPath, 'utf-8');

assert(appSrc.includes('handleTriggerAdbPull'), 'App.tsx defines handleTriggerAdbPull callback');
assert(appSrc.includes('handleCaptureScreen'), 'App.tsx defines handleCaptureScreen callback');
assert(appSrc.includes('handleSelectVideoTag'), 'App.tsx defines handleSelectVideoTag callback');
assert(appSrc.includes('triggerAdbPull({ mock: true })'), 'handleTriggerAdbPull calls triggerAdbPull with mock options');
assert(appSrc.includes("captureScreen({ format: 'png' })"), 'handleCaptureScreen calls captureScreen with format: png');
assert(appSrc.includes('getHealth()'), 'App.tsx invokes getHealth on mount for initial ADB detection');

// Verify notification toast component
assert(appSrc.includes('role="status"'), 'App.tsx toast notification uses role="status"');
assert(appSrc.includes('aria-live="polite"'), 'App.tsx toast notification uses aria-live="polite"');
assert(appSrc.includes('tagNotification'), 'App.tsx manages tagNotification state');
assert(appSrc.includes('notificationType'), 'App.tsx supports info/success/error notification types');

// Hotkey check
assert(
  appSrc.includes("e.ctrlKey && e.shiftKey && (e.key === 'T' || e.key === 't')"),
  'App.tsx binds global Ctrl+Shift+T hotkey with case-insensitivity'
);
assert(appSrc.includes('e.preventDefault()'), 'App.tsx calls preventDefault on hotkey capture');

// -----------------------------------------------------------------------------
// 3. Component Hierarchy & Prop Integrity
// -----------------------------------------------------------------------------
console.log('\n--- 3. Component Hierarchy & Prop Integrity ---');
const feedPath = path.join(COMPONENTS_DIR, 'PhoneLinkFeed.tsx');
const feedSrc = fs.readFileSync(feedPath, 'utf-8');

assert(feedSrc.includes('onTriggerAdbPull'), 'PhoneLinkFeed accepts onTriggerAdbPull prop');
assert(feedSrc.includes('onCaptureScreen'), 'PhoneLinkFeed accepts onCaptureScreen prop');
assert(feedSrc.includes('onSelectVideoTag'), 'PhoneLinkFeed accepts onSelectVideoTag prop');
assert(feedSrc.includes('isPulling'), 'PhoneLinkFeed accepts isPulling prop');
assert(feedSrc.includes('VideoTagsPanel'), 'PhoneLinkFeed embeds VideoTagsPanel component');
assert(feedSrc.includes('aspect-[9/16]'), 'PhoneLinkFeed enforces 9:16 aspect ratio container');
assert(feedSrc.includes('Live Capture'), 'PhoneLinkFeed has Live Capture badge');

const colPath = path.join(COMPONENTS_DIR, 'CollisionQueue.tsx');
const colSrc = fs.readFileSync(colPath, 'utf-8');

assert(colSrc.includes('col-span-8'), 'CollisionQueue spans 8 grid columns');
assert(colSrc.includes('Resolution Mismatch'), 'CollisionQueue displays Resolution Mismatch conflict');
assert(colSrc.includes('Keep 4K ADB Version'), 'CollisionQueue has Keep 4K ADB Version resolution button');
assert(colSrc.includes('Keep Takeout'), 'CollisionQueue has Keep Takeout resolution button');
assert(colSrc.includes('Undo'), 'CollisionQueue supports Undo resolution');

// -----------------------------------------------------------------------------
// 4. Data Connect GQL Schema & Queries Conformance
// -----------------------------------------------------------------------------
console.log('\n--- 4. Data Connect GQL Schema & Queries Conformance ---');
const schemaPath = path.join(DATACONNECT_DIR, 'schema', 'schema.gql');
const schemaSrc = fs.readFileSync(schemaPath, 'utf-8');

assert(schemaSrc.includes('type VideoTag @table(name: "video_tags"'), 'schema.gql maps VideoTag to video_tags table');
assert(schemaSrc.includes('filename: String! @unique'), 'schema.gql enforces unique filename');
assert(schemaSrc.includes('domain: String!'), 'schema.gql defines domain');
assert(schemaSrc.includes('entity: String!'), 'schema.gql defines entity');
assert(schemaSrc.includes('viralFeatures: Any!'), 'schema.gql defines viralFeatures');
assert(schemaSrc.includes('technical: Any!'), 'schema.gql defines technical');

const queriesPath = path.join(DATACONNECT_DIR, 'connector', 'queries.gql');
const queriesSrc = fs.readFileSync(queriesPath, 'utf-8');
assert(queriesSrc.includes('query ListVideoTags'), 'queries.gql defines ListVideoTags query');
assert(queriesSrc.includes('query GetVideoTag'), 'queries.gql defines GetVideoTag query');

const mutationsPath = path.join(DATACONNECT_DIR, 'connector', 'mutations.gql');
const mutationsSrc = fs.readFileSync(mutationsPath, 'utf-8');
assert(mutationsSrc.includes('mutation CreateVideoTag'), 'mutations.gql defines CreateVideoTag mutation');

// -----------------------------------------------------------------------------
// 5. Build Artifact Soundness Check
// -----------------------------------------------------------------------------
console.log('\n--- 5. Production Build Artifact Inspection ---');
const distIndexPath = path.join(FRONTEND_DIR, 'dist', 'index.html');
assert(fs.existsSync(distIndexPath), 'dist/index.html exists');

const distAssetsDir = path.join(FRONTEND_DIR, 'dist', 'assets');
assert(fs.existsSync(distAssetsDir), 'dist/assets exists');

const jsFiles = fs.readdirSync(distAssetsDir).filter((f) => f.endsWith('.js'));
const cssFiles = fs.readdirSync(distAssetsDir).filter((f) => f.endsWith('.css'));
assert(jsFiles.length > 0, `Production JS bundle exists: ${jsFiles.join(', ')}`);
assert(cssFiles.length > 0, `Production CSS bundle exists: ${cssFiles.join(', ')}`);

console.log('\n====================================================================');
console.log(`TOTAL CHECKS: ${passCount + failCount} | PASSED: ${passCount} | FAILED: ${failCount}`);
console.log('====================================================================\n');

if (failCount > 0) {
  process.exit(1);
} else {
  console.log('ALL CHALLENGER 2 NODE CHECKS PASSED EMPIRICALLY.');
  process.exit(0);
}
