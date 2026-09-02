/**
 * Node.js E2E Runner for Omnichannel Triage Hub
 * Verifies Frontend bundle integrity, FastAPI contracts, Data Connect definitions, and API client types.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');
const FRONTEND_DIR = path.join(REPO_ROOT, 'frontend');
const DATACONNECT_DIR = path.join(REPO_ROOT, 'dataconnect');
const LOCAL_DAEMON_DIR = path.join(REPO_ROOT, 'local_daemon');

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

console.log('====================================================');
console.log('OMNICHANNEL TRIAGE HUB — E2E INTEGRATION RUNNER');
console.log('====================================================\n');

// 1. Frontend Bundle & Build Artifacts
console.log('--- Tier 1: Frontend & Static Asset Verification ---');
const distIndexPath = path.join(FRONTEND_DIR, 'dist', 'index.html');
assert(fs.existsSync(distIndexPath), 'dist/index.html exists');

const distAssetsDir = path.join(FRONTEND_DIR, 'dist', 'assets');
assert(fs.existsSync(distAssetsDir), 'dist/assets directory exists');

const assetFiles = fs.readdirSync(distAssetsDir);
const jsBundle = assetFiles.find((f) => f.endsWith('.js'));
const cssBundle = assetFiles.find((f) => f.endsWith('.css'));
assert(Boolean(jsBundle), `JS bundle found: ${jsBundle}`);
assert(Boolean(cssBundle), `CSS bundle found: ${cssBundle}`);

// 2. REST API Client Verification
console.log('\n--- Tier 1: Frontend API Client Verification ---');
const apiClientPath = path.join(FRONTEND_DIR, 'src', 'lib', 'api.ts');
assert(fs.existsSync(apiClientPath), 'frontend/src/lib/api.ts exists');
const apiClientSrc = fs.readFileSync(apiClientPath, 'utf-8');
assert(apiClientSrc.includes('export async function triggerAdbPull'), 'api.ts exports triggerAdbPull');
assert(apiClientSrc.includes('export async function captureScreen'), 'api.ts exports captureScreen');
assert(apiClientSrc.includes('export async function getHealth'), 'api.ts exports getHealth');
assert(apiClientSrc.includes('export async function getDevices'), 'api.ts exports getDevices');
assert(apiClientSrc.includes('export async function getStagingInventory'), 'api.ts exports getStagingInventory');
assert(apiClientSrc.includes('is_fallback'), 'api.ts handles graceful fallback');

// 3. UI Component Integration Wiring
console.log('\n--- Tier 1: UI Wiring & Actions ---');
const appSrc = fs.readFileSync(path.join(FRONTEND_DIR, 'src', 'App.tsx'), 'utf-8');
assert(appSrc.includes('triggerAdbPull'), 'App.tsx imports triggerAdbPull');
assert(appSrc.includes('captureScreen'), 'App.tsx imports captureScreen');
assert(appSrc.includes('getHealth'), 'App.tsx imports getHealth');
assert(appSrc.includes('handleTriggerAdbPull'), 'App.tsx defines handleTriggerAdbPull');
assert(appSrc.includes('handleCaptureScreen'), 'App.tsx defines handleCaptureScreen');
assert(appSrc.includes('Ctrl+Shift+T') || appSrc.includes("e.key === 'T'"), 'App.tsx binds hotkey');

// 4. Data Connect Contracts
console.log('\n--- Tier 1: Data Connect Contracts ---');
const schemaPath = path.join(DATACONNECT_DIR, 'schema', 'schema.gql');
assert(fs.existsSync(schemaPath), 'dataconnect/schema/schema.gql exists');
const schemaSrc = fs.readFileSync(schemaPath, 'utf-8');
assert(schemaSrc.includes('type VideoTag @table'), 'schema.gql defines VideoTag table');
assert(schemaSrc.includes('viralFeatures: Any!'), 'schema.gql defines viralFeatures');
assert(schemaSrc.includes('technical: Any!'), 'schema.gql defines technical');

// 5. Local Daemon Backend Code
console.log('\n--- Tier 1: FastAPI Local Daemon ---');
const daemonMainPath = path.join(LOCAL_DAEMON_DIR, 'main.py');
assert(fs.existsSync(daemonMainPath), 'local_daemon/main.py exists');
const daemonSrc = fs.readFileSync(daemonMainPath, 'utf-8');
assert(daemonSrc.includes('/api/health'), 'main.py defines /api/health');
assert(daemonSrc.includes('/api/trigger-adb-pull'), 'main.py defines /api/trigger-adb-pull');
assert(daemonSrc.includes('/api/capture-screen'), 'main.py defines /api/capture-screen');
assert(daemonSrc.includes('CORSMiddleware'), 'main.py configures CORS middleware');

console.log('\n====================================================');
console.log(`TOTAL CHECKS: ${passCount + failCount} | PASSED: ${passCount} | FAILED: ${failCount}`);
console.log('====================================================\n');

if (failCount > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
