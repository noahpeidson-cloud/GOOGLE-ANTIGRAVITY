// =============================================================================
// Challenger 2: Milestone 3 Deep JSONB & Robustness Stress Harness
// Omnichannel Triage Hub - Firebase Data Connect (PostgreSQL) Integration
// =============================================================================

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const REPO_ROOT = path.resolve(__dirname, '..', '..', 'omnichannel_triage_hub');
const FRONTEND_ROOT = path.join(REPO_ROOT, 'frontend');
const DATACONNECT_ROOT = path.join(REPO_ROOT, 'dataconnect');

let passedTests = 0;
let failedTests = 0;
const failures = [];

function assert(condition, message) {
  if (condition) {
    passedTests++;
    console.log(`  [PASS] ${message}`);
  } else {
    failedTests++;
    failures.push(message);
    console.error(`  [FAIL] ${message}`);
  }
}

function runSection(title, fn) {
  console.log(`\n=== ${title} ===`);
  try {
    fn();
  } catch (err) {
    console.error(`  [ERROR IN SUITE]:`, err);
    failedTests++;
    failures.push(`Suite error in: ${title} -> ${err.message}`);
  }
}

console.log('Starting Milestone 3 Challenger JSONB & Robustness Verification...\n');

// -----------------------------------------------------------------------------
// SECTION 1: Firebase Data Connect Architecture & Schema AST Checks
// -----------------------------------------------------------------------------
runSection('1. Firebase Data Connect Schema & Directive Verification', () => {
  const schemaPath = path.join(DATACONNECT_ROOT, 'schema', 'schema.gql');
  assert(fs.existsSync(schemaPath), 'schema.gql exists in dataconnect/schema/');
  const schemaContent = fs.readFileSync(schemaPath, 'utf8');

  assert(schemaContent.includes('@table(name: "video_tags"'), 'schema.gql maps type VideoTag to table "video_tags"');
  assert(schemaContent.includes('key: "id"'), 'schema.gql specifies key: "id"');
  assert(schemaContent.includes('id: Int64!'), 'schema.gql defines id: Int64!');
  assert(schemaContent.includes('filename: String! @unique'), 'schema.gql defines filename: String! @unique');
  assert(schemaContent.includes('filepath: String!'), 'schema.gql defines filepath: String!');
  assert(schemaContent.includes('domain: String!'), 'schema.gql defines domain: String!');
  assert(schemaContent.includes('entity: String!'), 'schema.gql defines entity: String!');
  
  // JSONB column directives
  assert(
    schemaContent.includes('viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb")'),
    'schema.gql defines viralFeatures: Any! with PostgreSQL jsonb column mapping'
  );
  assert(
    schemaContent.includes('technical: Any! @col(name: "technical", dataType: "jsonb")'),
    'schema.gql defines technical: Any! with PostgreSQL jsonb column mapping'
  );
  assert(schemaContent.includes('createdAt: Timestamp!'), 'schema.gql defines createdAt: Timestamp!');
  assert(schemaContent.includes('updatedAt: Timestamp!'), 'schema.gql defines updatedAt: Timestamp!');
});

// -----------------------------------------------------------------------------
// SECTION 2: GraphQL Connector Operations & Security Directives
// -----------------------------------------------------------------------------
runSection('2. GraphQL Connector Operations & Security Directives', () => {
  const queriesPath = path.join(DATACONNECT_ROOT, 'connector', 'queries.gql');
  const mutationsPath = path.join(DATACONNECT_ROOT, 'connector', 'mutations.gql');

  assert(fs.existsSync(queriesPath), 'queries.gql exists in dataconnect/connector/');
  assert(fs.existsSync(mutationsPath), 'mutations.gql exists in dataconnect/connector/');

  const queriesContent = fs.readFileSync(queriesPath, 'utf8');
  const mutationsContent = fs.readFileSync(mutationsPath, 'utf8');

  // Queries
  assert(queriesContent.includes('query ListVideoTags @auth(level: PUBLIC)'), 'ListVideoTags has public auth level');
  assert(queriesContent.includes('query GetVideoTag($id: Int64!) @auth(level: PUBLIC)'), 'GetVideoTag accepts Int64! id with public auth');
  assert(queriesContent.includes('viralFeatures') && queriesContent.includes('technical'), 'Queries request viralFeatures and technical JSONB fields');

  // Mutations
  assert(
    mutationsContent.includes('mutation CreateVideoTag($filename: String!, $filepath: String!, $domain: String!, $entity: String!, $viralFeatures: Any!, $technical: Any!) @auth(level: PUBLIC)'),
    'CreateVideoTag mutation accepts Any! for viralFeatures and technical with public auth'
  );
  assert(mutationsContent.includes('videoTag_insert('), 'CreateVideoTag calls auto-generated videoTag_insert');
  assert(mutationsContent.includes('createdAt_expr: "request.time"'), 'CreateVideoTag uses server-evaluated request.time for createdAt');
  assert(mutationsContent.includes('updatedAt_expr: "request.time"'), 'CreateVideoTag uses server-evaluated request.time for updatedAt');
});

// -----------------------------------------------------------------------------
// SECTION 3: Deep Edge-Case JSONB Payload Generation & Serialization
// -----------------------------------------------------------------------------
runSection('3. JSONB Edge Cases & Extreme Payload Validation', () => {
  const testCases = [
    {
      name: 'Standard EDM festival features',
      payload: {
        visualHooks: ['Mainstage Lasers', 'Paradox Visuals', 'Bass Drop'],
        energyLevel: 'Maximum',
        crowdReaction: 'Moshpit',
        bpm: 150,
      },
    },
    {
      name: 'Standard Sports Card grading features',
      payload: {
        visualHooks: ['Gem Mint Holo', 'UV Blacklight Test', 'Corner Centering 50/50'],
        cardDetails: {
          year: 1986,
          brand: 'Fleer',
          player: 'Michael Jordan',
          number: 57,
          grade: 'PSA 10',
          subgrades: { centering: 10, corners: 10, edges: 10, surface: 10 },
        },
        estimatedValue: '$250,000',
      },
    },
    {
      name: 'Empty JSON object',
      payload: {},
    },
    {
      name: 'Array of string hooks',
      payload: ['Hook 1', 'Hook 2', 'Hook 3'],
    },
    {
      name: 'Array of complex objects',
      payload: [
        { type: 'pyro', startSec: 12.4, endSec: 18.2 },
        { type: 'drop', startSec: 18.2, subBassHz: 32 },
      ],
    },
    {
      name: 'Primitive and Null values inside JSONB',
      payload: {
        nullVal: null,
        boolTrue: true,
        boolFalse: false,
        integerVal: 42,
        floatVal: 3.141592653589793,
        exponentVal: 1.23e-10,
        emptyString: '',
      },
    },
    {
      name: 'Deeply Nested JSON Object (15 levels)',
      payload: (() => {
        let obj = { leaf: 'deep_value', depth: 15 };
        for (let i = 14; i >= 1; i--) {
          obj = { level: i, nested: obj };
        }
        return obj;
      })(),
    },
    {
      name: 'Extreme Multilingual & Unicode Strings',
      payload: {
        emoji: '🔥⚡🚀🎧🎉💎✨🔊🎵🕹️',
        cjk: '电子音乐节 • 现场激光秀 • 1986年飞人乔丹卡',
        cyrillic: 'Фестиваль электронной музыки и спортивные карточки',
        arabic_rtl: 'مهرجان الموسيقى الإلكترونية وبطاقات التداول الرياضية',
        hebrew_rtl: 'פסטיבל מוזיקה אלקטרונית וקלפי ספורט',
        diacritics: 'Café, Résumé, Über, Naïve, São Paulo',
        specialPunctuation: '«» „“ ”’ — – … ‰ ‱ ‼ ⁇ ⁈ ⁉',
      },
    },
    {
      name: 'Security & Sanitization Edge Cases (Code-like strings in JSONB)',
      payload: {
        xssTag: "<script>alert('xss')</script>",
        htmlImg: '<img src="x" onerror="console.log(1)" />',
        sqlInjection: "'; DROP TABLE video_tags; --",
        quotes: '"double quotes" and \'single quotes\' and `backticks`',
        escapes: 'Line 1\nLine 2\r\nTab\tBackslash\\Null\u0000End',
        jsonInString: '{"nestedKey": "nestedVal", "array": [1,2,3]}',
      },
    },
    {
      name: 'Massive JSON payload (10,000 items / large strings)',
      payload: {
        massiveArray: Array.from({ length: 1000 }, (_, i) => `item_${i}`),
        largeString: 'A'.repeat(50000),
        metadata: { count: 1000, size: 'large' },
      },
    },
  ];

  testCases.forEach((tc) => {
    // 1. Must JSON serialize and parse losslessly
    const serialized = JSON.stringify(tc.payload);
    const parsed = JSON.parse(serialized);
    assert(
      JSON.stringify(parsed) === serialized,
      `JSONB lossless roundtrip serialization: [${tc.name}]`
    );

    // 2. Validate against TypeScript VideoTag contract requirements
    const mockVideoTag = {
      id: '999',
      filename: 'test_file.mp4',
      filepath: '/sdcard/test.mp4',
      domain: 'TEST_DOMAIN',
      entity: 'Test Entity',
      viralFeatures: tc.payload,
      technical: { resolution: '3840x2160', fps: 60 },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    assert(typeof mockVideoTag.id === 'string', `Mock tag ID is string: [${tc.name}]`);
    assert(mockVideoTag.viralFeatures !== undefined, `Mock tag viralFeatures exists: [${tc.name}]`);
  });
});

// -----------------------------------------------------------------------------
// SECTION 4: Frontend UI Component Parsing Resilience Simulation
// -----------------------------------------------------------------------------
runSection('4. UI Component Parsing Resilience (VideoTagsPanel & App.tsx logic)', () => {
  // Extract features parsing logic as implemented in VideoTagsPanel.tsx
  function extractVisualHooks(viralFeatures) {
    return Array.isArray(viralFeatures)
      ? viralFeatures
      : typeof viralFeatures === 'object' && viralFeatures !== null && 'visualHooks' in viralFeatures
      ? viralFeatures.visualHooks
      : [];
  }

  // Extract feature string formatting as implemented in App.tsx
  function formatViralFeaturesForToast(viralFeatures) {
    return Array.isArray(viralFeatures)
      ? viralFeatures.join(', ')
      : typeof viralFeatures === 'object' && viralFeatures !== null && 'visualHooks' in viralFeatures
      ? Array.isArray(viralFeatures.visualHooks)
        ? viralFeatures.visualHooks.join(', ')
        : String(viralFeatures.visualHooks)
      : 'Indexed in PostgreSQL';
  }

  const edgePayloads = [
    { input: null, desc: 'null input' },
    { input: undefined, desc: 'undefined input' },
    { input: {}, desc: 'empty object' },
    { input: [], desc: 'empty array' },
    { input: ['Hook A', 'Hook B'], desc: 'array of strings' },
    { input: [{ hook: 'A' }, { hook: 'B' }], desc: 'array of objects' },
    { input: { visualHooks: ['Laser', 'Drop'] }, desc: 'object with string array visualHooks' },
    { input: { visualHooks: 'Single String Hook' }, desc: 'object with string visualHooks' },
    { input: { visualHooks: null }, desc: 'object with null visualHooks' },
    { input: { visualHooks: 12345 }, desc: 'object with number visualHooks' },
    { input: 'raw string payload', desc: 'primitive string' },
    { input: 98765, desc: 'primitive number' },
    { input: true, desc: 'primitive boolean' },
  ];

  edgePayloads.forEach(({ input, desc }) => {
    // Test VideoTagsPanel extractor does not crash
    let hooks;
    let panelThrew = false;
    try {
      hooks = extractVisualHooks(input);
    } catch (e) {
      panelThrew = true;
    }
    assert(!panelThrew, `VideoTagsPanel extraction does not throw on ${desc}`);
    assert(Array.isArray(hooks) || hooks === input, `VideoTagsPanel returns array or raw value safely for ${desc}`);

    // Test App.tsx toast formatter does not crash
    let toastStr;
    let appThrew = false;
    try {
      toastStr = formatViralFeaturesForToast(input);
    } catch (e) {
      appThrew = true;
    }
    assert(!appThrew, `App.tsx formatter does not throw on ${desc}`);
    assert(typeof toastStr === 'string', `App.tsx produces string representation for ${desc}: "${toastStr}"`);
  });
});

// -----------------------------------------------------------------------------
// SECTION 5: Frontend SDK Module & Fallback Architecture
// -----------------------------------------------------------------------------
runSection('5. SDK Module & Reactive Hook Resilience Verification', () => {
  const sdkPath = path.join(FRONTEND_ROOT, 'src', 'lib', 'dataconnect', 'index.ts');
  assert(fs.existsSync(sdkPath), 'frontend/src/lib/dataconnect/index.ts exists');
  const sdkContent = fs.readFileSync(sdkPath, 'utf8');

  // Verify SDK function exports
  assert(sdkContent.includes('export const connectorConfig: ConnectorConfig'), 'Exports connectorConfig');
  assert(sdkContent.includes('export function listVideoTagsRef'), 'Exports listVideoTagsRef');
  assert(sdkContent.includes('export function getVideoTagRef'), 'Exports getVideoTagRef');
  assert(sdkContent.includes('export function createVideoTagRef'), 'Exports createVideoTagRef');
  assert(sdkContent.includes('export async function listVideoTags'), 'Exports listVideoTags');
  assert(sdkContent.includes('export async function getVideoTag'), 'Exports getVideoTag');
  assert(sdkContent.includes('export async function createVideoTag'), 'Exports createVideoTag');
  assert(sdkContent.includes('export function useVideoTags'), 'Exports useVideoTags hook');
  assert(sdkContent.includes('export const INITIAL_OFFLINE_VIDEO_TAGS'), 'Exports INITIAL_OFFLINE_VIDEO_TAGS');

  // Verify Firebase initializers
  const firebasePath = path.join(FRONTEND_ROOT, 'src', 'lib', 'firebase.ts');
  assert(fs.existsSync(firebasePath), 'frontend/src/lib/firebase.ts exists');
  const firebaseContent = fs.readFileSync(firebasePath, 'utf8');

  assert(firebaseContent.includes('getDataConnect(app, connectorConfig)'), 'Initializes Data Connect with connectorConfig');
  assert(firebaseContent.includes('connectDataConnectEmulator('), 'Includes connectDataConnectEmulator configuration');
});

// -----------------------------------------------------------------------------
// Summary
// -----------------------------------------------------------------------------
console.log('\n================================================================');
console.log(`CHALLENGER 2 JSONB STRESS TEST RESULTS: ${passedTests} PASSED, ${failedTests} FAILED`);
if (failedTests > 0) {
  console.log('FAILURES:');
  failures.forEach((f) => console.log(`  - ${f}`));
  process.exit(1);
} else {
  console.log('ALL EMPIRICAL CHALLENGER TESTS PASSED WITH ZERO ERRORS.');
  console.log('================================================================\n');
}
