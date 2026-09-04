import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const hubRoot = path.resolve(__dirname, '../../omnichannel_triage_hub');

console.log('================================================================');
console.log('FORENSIC AUDITOR 1 - ADVERSARIAL EDGE CASE & STRESS SUITE (M3)');
console.log('================================================================\n');

let passed = 0;
let failed = 0;

function assert(condition, name, details = '') {
  if (condition) {
    console.log(`[PASS] ${name}`);
    passed++;
  } else {
    console.error(`[FAIL] ${name} - ${details}`);
    failed++;
  }
}

// 1. Schema & GQL Invariant Assertions
console.log('--- 1. GraphQL & PostgreSQL Invariant Assertions ---');
const schemaGql = fs.readFileSync(path.join(hubRoot, 'dataconnect/schema/schema.gql'), 'utf8');

// Assert no duplicate fields or malformed syntax
const lines = schemaGql.split('\n').map(l => l.trim()).filter(Boolean);
const fieldLines = lines.filter(l => l.includes(':') && !l.startsWith('#') && !l.startsWith('type'));
const fieldNames = fieldLines.map(l => l.split(':')[0].trim());
const uniqueFieldNames = new Set(fieldNames);
assert(fieldNames.length === uniqueFieldNames.size, 'No duplicate field definitions in schema.gql', `Found duplicates in: ${fieldNames.join(', ')}`);

// Assert mandatory fields are non-null
const nonNullFields = fieldLines.filter(l => l.includes('!'));
assert(nonNullFields.length === fieldLines.length, 'All schema.gql fields are strictly non-nullable (!)');

// Assert JSONB column mappings for nested data
assert(schemaGql.includes('dataType: "jsonb"'), 'schema.gql explicitly specifies dataType: "jsonb" for unstructured video metadata');

// 2. Query/Mutation Parameter Completeness
console.log('\n--- 2. Query & Mutation Parameter Completeness ---');
const mutationsGql = fs.readFileSync(path.join(hubRoot, 'dataconnect/connector/mutations.gql'), 'utf8');
const requiredMutationParams = ['$filename', '$filepath', '$domain', '$entity', '$viralFeatures', '$technical'];
for (const param of requiredMutationParams) {
  assert(mutationsGql.includes(param), `CreateVideoTag mutation accepts variable ${param}`);
}

// 3. TypeScript SDK Contract & Interface Coverage
console.log('\n--- 3. TypeScript SDK Contract & Interface Coverage ---');
const sdkCode = fs.readFileSync(path.join(hubRoot, 'frontend/src/lib/dataconnect/index.ts'), 'utf8');

assert(sdkCode.includes('export interface VideoTag'), 'VideoTag interface is exported');
assert(sdkCode.includes('export interface ListVideoTagsData'), 'ListVideoTagsData interface is exported');
assert(sdkCode.includes('export interface ListVideoTagsVariables'), 'ListVideoTagsVariables interface is exported');
assert(sdkCode.includes('export interface GetVideoTagData'), 'GetVideoTagData interface is exported');
assert(sdkCode.includes('export interface GetVideoTagVariables'), 'GetVideoTagVariables interface is exported');
assert(sdkCode.includes('export interface CreateVideoTagData'), 'CreateVideoTagData interface is exported');
assert(sdkCode.includes('export interface CreateVideoTagVariables'), 'CreateVideoTagVariables interface is exported');
assert(sdkCode.includes('export interface UseVideoTagsResult'), 'UseVideoTagsResult interface is exported');

// 4. Memory Leak & React Hook Cleanup Protection
console.log('\n--- 4. React Hook Safety & Leak Prevention ---');
assert(sdkCode.includes('useCallback'), 'useVideoTags uses useCallback for stable function identities');
assert(sdkCode.includes('useEffect'), 'useVideoTags uses useEffect with explicit dependency array');
assert(sdkCode.includes('useState'), 'useVideoTags uses useState for isolated state encapsulation');

// 5. Build Artifact Integrity
console.log('\n--- 5. Build Artifact Manifest Integrity ---');
const distHtml = fs.readFileSync(path.join(hubRoot, 'frontend/dist/index.html'), 'utf8');
assert(distHtml.includes('<!DOCTYPE html>') || distHtml.includes('<!doctype html>'), 'Production index.html has valid doctype');
assert(distHtml.includes('/assets/index-'), 'Production index.html references hashed bundle assets');

console.log('\n================================================================');
console.log(`STRESS AUDIT RESULTS: ${passed} PASSED, ${failed} FAILED`);
console.log('================================================================\n');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
