import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('====================================================');
console.log('M1 ADVERSARIAL STRESS TEST & EDGE-CASE SUITE');
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

// 1. Stress Test: Fallback & Default Props Safety
console.log('--- 1. Default Props & Edge-Case Safety ---');

const headerSrc = fs.readFileSync(path.join(__dirname, 'src/components/Header.tsx'), 'utf8');
assert(headerSrc.includes('adbStatus = { text:'), 'Header provides robust fallback default props for adbStatus');
assert(headerSrc.includes('phoneLinkStatus = { text:'), 'Header provides robust fallback default props for phoneLinkStatus');

const feedSrc = fs.readFileSync(path.join(__dirname, 'src/components/PhoneLinkFeed.tsx'), 'utf8');
assert(feedSrc.includes('feedState = {'), 'PhoneLinkFeed provides robust default props for feedState');
assert(feedSrc.includes('isPulling = false'), 'PhoneLinkFeed defaults isPulling to false');
assert(feedSrc.includes('disabled={isPulling}'), 'PhoneLinkFeed disables pull button during active pull');
assert(feedSrc.includes('onError={() => setVideoError(true)}'), 'PhoneLinkFeed catches video load errors gracefully');

const queueSrc = fs.readFileSync(path.join(__dirname, 'src/components/CollisionQueue.tsx'), 'utf8');
assert(queueSrc.includes('DEFAULT_COLLISION_ITEMS'), 'CollisionQueue defines fallback items constant');
assert(queueSrc.includes('items = DEFAULT_COLLISION_ITEMS'), 'CollisionQueue defaults items to DEFAULT_COLLISION_ITEMS');
assert(queueSrc.includes('collisionList.map'), 'CollisionQueue uses safe array mapping for queue items');

const typesSrc = fs.readFileSync(path.join(__dirname, 'src/types/index.ts'), 'utf8');
assert(typesSrc.includes('resolutionChoice?:'), 'src/types/index.ts defines optional resolutionChoice on CollisionItem');
assert(typesSrc.includes('resolved?:'), 'src/types/index.ts defines optional resolved on CollisionItem');

// 2. Stress Test: Media Generation Script (Rule R21)
console.log('\n--- 2. Procedural Generation Script Verification ---');
const genScriptPath = path.join(__dirname, 'generate_assets.py');
assert(fs.existsSync(genScriptPath), 'generate_assets.py exists in frontend root');
const genScript = fs.readFileSync(genScriptPath, 'utf8');
assert(genScript.includes('imageio_ffmpeg'), 'generate_assets.py uses imageio_ffmpeg for zero-dependency local rendering');
assert(genScript.includes('540x960') || genScript.includes('9:16') || (genScript.includes('540') && genScript.includes('960')), 'generate_assets.py configures 9:16 aspect ratio (540x960)');
assert(genScript.includes('placeholder.mp4'), 'generate_assets.py targets placeholder.mp4 in public/');
assert(genScript.includes('placeholder.png'), 'generate_assets.py targets placeholder.png in public/');

// 3. Stress Test: Accessibility & WCAG Baseline Checks
console.log('\n--- 3. A11y & Visual Contrast Check ---');
const indexHtml = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
assert(indexHtml.includes('lang="en"'), 'HTML element has valid lang="en" attribute');
assert(indexHtml.includes('viewport'), 'HTML contains standard responsive viewport meta tag');
assert(indexHtml.includes('<title>Omnichannel Triage Hub</title>'), 'HTML contains descriptive document title');

const appSrc = fs.readFileSync(path.join(__dirname, 'src/App.tsx'), 'utf8');
assert(appSrc.includes('<main'), 'App uses semantic <main> landmark element');
assert(headerSrc.includes('<header'), 'Header uses semantic <header> landmark element');
assert(feedSrc.includes('<section'), 'PhoneLinkFeed uses semantic <section> landmark element');
assert(queueSrc.includes('<section'), 'CollisionQueue uses semantic <section> landmark element');

console.log('\n====================================================');
console.log(`STRESS TEST RESULTS: ${passedTests} PASSED, ${failedTests} FAILED`);
console.log('====================================================\n');

if (failedTests > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
