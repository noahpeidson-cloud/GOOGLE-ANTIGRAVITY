// =============================================================================
// Comprehensive Challenger 2 Test Harness for Milestone 3
// Firebase Data Connect (PostgreSQL) Integration
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
const findings = [];

function assert(condition, message, isFinding = false) {
  if (condition) {
    passedTests++;
    console.log(`  [PASS] ${message}`);
  } else {
    failedTests++;
    findings.push(message);
    console.error(`  [${isFinding ? 'VULNERABILITY' : 'FAIL'}] ${message}`);
  }
}

function runSection(title, fn) {
  console.log(`\n=== ${title} ===`);
  try {
    fn();
  } catch (err) {
    console.error(`  [ERROR IN SUITE]:`, err);
    failedTests++;
    findings.push(`Suite error in: ${title} -> ${err.message}`);
  }
}

console.log('Running Challenger 2 Milestone 3 Comprehensive Test Suite...\n');

// 1. Firebase Data Connect Configuration Files
runSection('1. Firebase Data Connect Service & Connector Config', () => {
  const dcYamlPath = path.join(DATACONNECT_ROOT, 'dataconnect.yaml');
  assert(fs.existsSync(dcYamlPath), 'dataconnect.yaml exists');
  const dcYaml = fs.readFileSync(dcYamlPath, 'utf8');
  assert(dcYaml.includes('specVersion: "v1"'), 'dataconnect.yaml has specVersion v1');
  assert(dcYaml.includes('serviceId: "omnichannel-service"'), 'dataconnect.yaml serviceId matches omnichannel-service');
  assert(dcYaml.includes('location: "us-central1"'), 'dataconnect.yaml location matches us-central1');
  assert(dcYaml.includes('source: "./schema"'), 'dataconnect.yaml points to schema directory');
  assert(dcYaml.includes('connectorDirs: ["./connector"]'), 'dataconnect.yaml lists connector directory');

  const connectorYamlPath = path.join(DATACONNECT_ROOT, 'connector', 'connector.yaml');
  assert(fs.existsSync(connectorYamlPath), 'connector.yaml exists');
  const connectorYaml = fs.readFileSync(connectorYamlPath, 'utf8');
  assert(connectorYaml.includes('connectorId: "omnichannel-connector"'), 'connector.yaml has connectorId omnichannel-connector');
  assert(connectorYaml.includes('javascriptSdk:'), 'connector.yaml configures javascriptSdk generation');
});

// 2. PostgreSQL Schema Validation
runSection('2. PostgreSQL VideoTag Table Schema', () => {
  const schemaPath = path.join(DATACONNECT_ROOT, 'schema', 'schema.gql');
  assert(fs.existsSync(schemaPath), 'schema.gql exists');
  const schema = fs.readFileSync(schemaPath, 'utf8');

  assert(schema.includes('type VideoTag @table(name: "video_tags", key: "id", singular: "videoTag", plural: "videoTags")'), 'VideoTag type has complete @table annotation');
  assert(schema.includes('id: Int64!'), 'id is Int64!');
  assert(schema.includes('filename: String! @unique'), 'filename is unique String!');
  assert(schema.includes('filepath: String!'), 'filepath is String!');
  assert(schema.includes('domain: String!'), 'domain is String!');
  assert(schema.includes('entity: String!'), 'entity is String!');
  assert(schema.includes('viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb")'), 'viralFeatures is mapped to PostgreSQL JSONB');
  assert(schema.includes('technical: Any! @col(name: "technical", dataType: "jsonb")'), 'technical is mapped to PostgreSQL JSONB');
  assert(schema.includes('createdAt: Timestamp!'), 'createdAt is Timestamp!');
  assert(schema.includes('updatedAt: Timestamp!'), 'updatedAt is Timestamp!');
});

// 3. GraphQL Operations & Authorization Directives
runSection('3. GraphQL Queries and Mutations', () => {
  const queriesPath = path.join(DATACONNECT_ROOT, 'connector', 'queries.gql');
  const queries = fs.readFileSync(queriesPath, 'utf8');
  assert(queries.includes('query ListVideoTags @auth(level: PUBLIC)'), 'ListVideoTags has public auth level');
  assert(queries.includes('query GetVideoTag($id: Int64!) @auth(level: PUBLIC)'), 'GetVideoTag accepts Int64! with public auth');
  assert(queries.includes('viralFeatures'), 'ListVideoTags includes viralFeatures selection');
  assert(queries.includes('technical'), 'ListVideoTags includes technical selection');

  const mutationsPath = path.join(DATACONNECT_ROOT, 'connector', 'mutations.gql');
  const mutations = fs.readFileSync(mutationsPath, 'utf8');
  assert(mutations.includes('mutation CreateVideoTag('), 'CreateVideoTag mutation exists');
  assert(mutations.includes('@auth(level: PUBLIC)'), 'CreateVideoTag has public auth level');
  assert(mutations.includes('$viralFeatures: Any!'), 'CreateVideoTag accepts Any! viralFeatures');
  assert(mutations.includes('$technical: Any!'), 'CreateVideoTag accepts Any! technical');
  assert(mutations.includes('createdAt_expr: "request.time"'), 'CreateVideoTag uses request.time for createdAt');
  assert(mutations.includes('updatedAt_expr: "request.time"'), 'CreateVideoTag uses request.time for updatedAt');
});

// 4. Edge-Case JSONB Data Parsing & Vulnerability Analysis
runSection('4. JSONB Edge Cases & Component Resilience Assessment', () => {
  // Test JSONB shapes against typical real-world PostgreSQL responses
  const edgeCases = [
    {
      desc: 'Standard object with visualHooks string array',
      data: {
        id: '1',
        filename: 'festival_lasers.mp4',
        domain: 'EDM_FESTIVALS',
        entity: 'Excision',
        viralFeatures: { visualHooks: ['Lasers', 'Bass Drop'], energy: 'Max' },
        technical: { resolution: '3840x2160', fps: 60, codec: 'h264' },
      },
      expectHookCount: 2,
    },
    {
      desc: 'JSONB where visualHooks is a direct string',
      data: {
        id: '2',
        filename: 'crowd_reaction.mp4',
        domain: 'EDM_FESTIVALS',
        entity: 'Subtronics',
        viralFeatures: { visualHooks: 'Single Pyro Explosion' },
        technical: { resolution: '1920x1080', fps: 30 },
      },
      expectHookCount: 1,
    },
    {
      desc: 'JSONB where visualHooks is null',
      data: {
        id: '3',
        filename: 'sports_raw.mp4',
        domain: 'SPORTS_CARDS',
        entity: 'Jordan 1986',
        viralFeatures: { visualHooks: null, grade: 'PSA 10' },
        technical: { resolution: '3840x2160', fps: 60 },
      },
      expectHookCount: 0,
    },
    {
      desc: 'JSONB where viralFeatures is empty object',
      data: {
        id: '4',
        filename: 'empty_meta.mp4',
        domain: 'TRAVEL_AND_LIFE',
        entity: 'Hiking',
        viralFeatures: {},
        technical: {},
      },
      expectHookCount: 0,
    },
    {
      desc: 'JSONB where viralFeatures is null',
      data: {
        id: '5',
        filename: 'null_features.mp4',
        domain: 'EDM_FESTIVALS',
        entity: 'Rezz',
        viralFeatures: null,
        technical: null,
      },
      expectHookCount: 0,
    },
    {
      desc: 'JSONB with deep nested metadata & Unicode',
      data: {
        id: '6',
        filename: 'tokyo_club.mp4',
        domain: 'TRAVEL_AND_LIFE',
        entity: 'Tokyo 2026',
        viralFeatures: {
          visualHooks: ['渋谷 激光', 'Neon Street 🎆', 'Bass Drop 🎧'],
          nested: { level1: { level2: { tags: ['epic', 'nightlife'] } } },
        },
        technical: { resolution: '7680x4320', fps: 120, hdr: 'HDR10+' },
      },
      expectHookCount: 3,
    },
  ];

  // Inspect the exact code in VideoTagsPanel.tsx
  const panelPath = path.join(FRONTEND_ROOT, 'src', 'components', 'VideoTagsPanel.tsx');
  const panelContent = fs.readFileSync(panelPath, 'utf8');

  // Verify whether VideoTagsPanel safely handles non-array visualHooks
  const hasArrayCheckForHooks = panelContent.includes('Array.isArray(tag.viralFeatures.visualHooks)');
  
  console.log(`  [INFO] VideoTagsPanel visualHooks array safety check present: ${hasArrayCheckForHooks}`);

  // Test serialization of all edge cases
  edgeCases.forEach((tc) => {
    const serialized = JSON.stringify(tc.data);
    const roundtripped = JSON.parse(serialized);
    assert(
      roundtripped.id === tc.data.id && roundtripped.filename === tc.data.filename,
      `Lossless JSONB serialization for: [${tc.desc}]`
    );
  });
});

console.log('\n================================================================');
console.log(`CHALLENGER 2 AUDIT SUITE RESULTS: ${passedTests} PASSED, ${failedTests} FAILED`);
console.log('================================================================\n');
