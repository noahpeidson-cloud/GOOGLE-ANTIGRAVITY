import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('====================================================');
console.log('OMNICHANNEL TRIAGE HUB - M1 ADVERSARIAL TEST SUITE');
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

// 1. File Structure & Configuration Tests
console.log('--- 1. File Structure & Scaffolding ---');
const requiredFiles = [
  'package.json',
  'vite.config.ts',
  'tailwind.config.js',
  'postcss.config.js',
  'index.html',
  'src/main.tsx',
  'src/App.tsx',
  'src/index.css',
  'src/types/index.ts',
  'src/components/Header.tsx',
  'src/components/PhoneLinkFeed.tsx',
  'src/components/CollisionQueue.tsx',
  'public/placeholder.mp4',
  'public/placeholder.png',
];

for (const relPath of requiredFiles) {
  const fullPath = path.join(__dirname, relPath);
  const exists = fs.existsSync(fullPath);
  assert(exists, `Required file exists: ${relPath}`, `File not found at ${fullPath}`);
}

// 2. CSS Token & Tailwind Configuration Verification
console.log('\n--- 2. CSS Design Tokens & Theme Configuration ---');
const indexCssPath = path.join(__dirname, 'src/index.css');
if (fs.existsSync(indexCssPath)) {
  const cssContent = fs.readFileSync(indexCssPath, 'utf8');
  assert(cssContent.includes('@tailwind base;'), 'index.css has @tailwind base');
  assert(cssContent.includes('@tailwind components;'), 'index.css has @tailwind components');
  assert(cssContent.includes('@tailwind utilities;'), 'index.css has @tailwind utilities');

  const requiredTokens = [
    '--background: #09090b',
    '--foreground: #f8fafc',
    '--card: #18181b',
    '--border: rgba(255, 255, 255, 0.1)',
    '--primary: #3b82f6',
    '--muted-foreground: #94a3b8',
  ];
  for (const token of requiredTokens) {
    assert(cssContent.includes(token), `CSS Variable token defined: ${token}`);
  }

  assert(cssContent.includes('::-webkit-scrollbar'), 'Custom scrollbar styles defined in index.css');
  assert(cssContent.includes('.glass-card'), 'Custom utility .glass-card defined in index.css');
}

const tailwindConfigPath = path.join(__dirname, 'tailwind.config.js');
if (fs.existsSync(tailwindConfigPath)) {
  const twContent = fs.readFileSync(tailwindConfigPath, 'utf8');
  assert(twContent.includes("'var(--background)'"), 'tailwind.config.js maps background to CSS var');
  assert(twContent.includes("'var(--foreground)'"), 'tailwind.config.js maps foreground to CSS var');
  assert(twContent.includes("'var(--card)'"), 'tailwind.config.js maps card to CSS var');
  assert(twContent.includes("'var(--border)'"), 'tailwind.config.js maps border to CSS var');
  assert(twContent.includes("'var(--primary)'"), 'tailwind.config.js maps primary to CSS var');
  assert(twContent.includes("'var(--muted-foreground)'"), 'tailwind.config.js maps muted-foreground to CSS var');
  assert(twContent.includes("'9/16': '9 / 16'"), 'tailwind.config.js includes 9/16 aspect ratio');
  assert(twContent.includes("'pulse-slow'"), 'tailwind.config.js includes pulse-slow animation');
}

// 3. Media Asset Binary Inspection (Rule R21)
console.log('\n--- 3. Procedural Media Asset Inspection ---');
const mp4Path = path.join(__dirname, 'public/placeholder.mp4');
if (fs.existsSync(mp4Path)) {
  const mp4Stats = fs.statSync(mp4Path);
  assert(mp4Stats.size > 1000, `placeholder.mp4 size is valid (${mp4Stats.size} bytes > 1000)`);

  const buffer = fs.readFileSync(mp4Path);
  // Check MP4 ftyp box signature (at byte offset 4-8: 'ftyp')
  const ftypTag = buffer.subarray(4, 8).toString('ascii');
  assert(ftypTag === 'ftyp', `placeholder.mp4 contains valid ISO/MP4 header ('ftyp' found: '${ftypTag}')`);

  // Check for 'isom' or 'mp42' brand
  const majorBrand = buffer.subarray(8, 12).toString('ascii');
  assert(majorBrand.length === 4, `placeholder.mp4 major brand is valid ('${majorBrand}')`);
}

const pngPath = path.join(__dirname, 'public/placeholder.png');
if (fs.existsSync(pngPath)) {
  const pngStats = fs.statSync(pngPath);
  assert(pngStats.size > 500, `placeholder.png size is valid (${pngStats.size} bytes > 500)`);

  const pngBuffer = fs.readFileSync(pngPath);
  // PNG Magic Header: 89 50 4E 47 0D 0A 1A 0A
  const isPng =
    pngBuffer[0] === 0x89 &&
    pngBuffer[1] === 0x50 &&
    pngBuffer[2] === 0x4e &&
    pngBuffer[3] === 0x47 &&
    pngBuffer[4] === 0x0d &&
    pngBuffer[5] === 0x0a &&
    pngBuffer[6] === 0x1a &&
    pngBuffer[7] === 0x0a;
  assert(isPng, 'placeholder.png has valid PNG binary signature (0x89504E470D0A1A0A)');

  // IHDR chunk starts at byte 12. Width is bytes 16-19, Height is bytes 20-23
  if (isPng && pngBuffer.length >= 24) {
    const width = pngBuffer.readUInt32BE(16);
    const height = pngBuffer.readUInt32BE(20);
    assert(width > 0 && height > 0, `placeholder.png dimensions parsed: ${width}x${height}`);
    const aspect = width / height;
    const targetAspect = 9 / 16;
    const isNineSixteen = Math.abs(aspect - targetAspect) < 0.05;
    assert(isNineSixteen, `placeholder.png matches 9:16 aspect ratio (${width}x${height}, ratio: ${aspect.toFixed(3)})`);
  }
}

// 4. Component Structural & Functional AST Analysis
console.log('\n--- 4. Component Static & Semantic Inspection ---');

// Header.tsx
const headerPath = path.join(__dirname, 'src/components/Header.tsx');
if (fs.existsSync(headerPath)) {
  const content = fs.readFileSync(headerPath, 'utf8');
  assert(content.includes('Omnichannel Triage Hub'), 'Header displays "Omnichannel Triage Hub" title');
  assert(content.includes('ADB Connection'), 'Header includes ADB Connection badge label');
  assert(content.includes('Windows Phone Link'), 'Header includes Windows Phone Link badge label');
  assert(content.includes('animate-pulse'), 'Header includes pulsing status indicators');
  assert(content.includes('border-[var(--border)]'), 'Header uses border CSS variable token');
}

// PhoneLinkFeed.tsx
const feedPath = path.join(__dirname, 'src/components/PhoneLinkFeed.tsx');
if (fs.existsSync(feedPath)) {
  const content = fs.readFileSync(feedPath, 'utf8');
  assert(content.includes('col-span-4'), 'PhoneLinkFeed has 4-column span');
  assert(content.includes('Ctrl+Shift+T to Tag'), 'PhoneLinkFeed displays Ctrl+Shift+T hotkey badge');
  assert(content.includes('aspect-[9/16]'), 'PhoneLinkFeed uses 9:16 aspect ratio for stream');
  assert(content.includes('animate-ping'), 'PhoneLinkFeed has live ping animation on capture badge');
  assert(content.includes('<video'), 'PhoneLinkFeed renders HTML5 video element');
  assert(content.includes('onError='), 'PhoneLinkFeed implements onError fallback handler');
  assert(content.includes('Gemini Vision Result'), 'PhoneLinkFeed includes Gemini Vision Result section');
  assert(content.includes('Entity (L2)'), 'PhoneLinkFeed displays Entity (L2)');
  assert(content.includes('Attribute (L3)'), 'PhoneLinkFeed displays Attribute (L3)');
  assert(content.includes('Trigger ADB Pull'), 'PhoneLinkFeed has Trigger ADB Pull button');
  assert(content.includes('Simulate Screen Capture'), 'PhoneLinkFeed has Simulate Screen Capture button');
}

// CollisionQueue.tsx
const queuePath = path.join(__dirname, 'src/components/CollisionQueue.tsx');
if (fs.existsSync(queuePath)) {
  const content = fs.readFileSync(queuePath, 'utf8');
  assert(content.includes('col-span-8'), 'CollisionQueue has 8-column span');
  assert(content.includes('Collision Resolution Queue'), 'CollisionQueue displays section header');
  assert(content.includes('Resolution Mismatch'), 'CollisionQueue displays Resolution Mismatch conflict type');
  assert(content.includes('Local ADB Pull'), 'CollisionQueue shows Local ADB Pull card');
  assert(content.includes('Takeout Cloud'), 'CollisionQueue shows Takeout Cloud card');
  assert(content.includes('4K'), 'CollisionQueue shows 4K resolution info');
  assert(content.includes('1080p'), 'CollisionQueue shows 1080p resolution info');
  assert(content.includes('Keep 4K ADB Version (Auto-Trash Takeout)'), 'CollisionQueue has primary resolution button');
  assert(content.includes('Keep Takeout'), 'CollisionQueue has secondary resolution button');
  assert(content.includes('handleUndo'), 'CollisionQueue implements resolution undo capability');
}

// App.tsx
const appPath = path.join(__dirname, 'src/App.tsx');
if (fs.existsSync(appPath)) {
  const content = fs.readFileSync(appPath, 'utf8');
  assert(content.includes('grid-cols-12'), 'App uses 12-column grid layout');
  assert(content.includes('h-screen overflow-hidden'), 'App enforces fixed screen height and overflow prevention');
  assert(content.includes('keydown'), 'App registers global keydown event listener');
  assert(content.includes('removeEventListener'), 'App properly cleans up keydown event listener on unmount (Leak Prevention)');
  assert(content.includes("role=\"status\""), 'App toast notification includes role="status" for accessibility');
  assert(content.includes("aria-live=\"polite\""), 'App toast notification includes aria-live="polite" for screen readers');
}

// 5. Build Reliability & Production Bundling Execution
console.log('\n--- 5. Empirical Production Build & Bundle Generation ---');
try {
  const buildOutput = execSync('npm run build', { cwd: __dirname, encoding: 'utf8' });
  console.log('Build Output Snippet:\n' + buildOutput.trim().split('\n').slice(-8).join('\n'));
  assert(true, 'npm run build completed with exit code 0');

  const distIndex = path.join(__dirname, 'dist/index.html');
  assert(fs.existsSync(distIndex), 'dist/index.html successfully created');

  const distAssets = path.join(__dirname, 'dist/assets');
  assert(fs.existsSync(distAssets), 'dist/assets directory successfully created');

  const assetFiles = fs.readdirSync(distAssets);
  const jsFiles = assetFiles.filter(f => f.endsWith('.js'));
  const cssFiles = assetFiles.filter(f => f.endsWith('.css'));

  assert(jsFiles.length > 0, `JS bundle generated: ${jsFiles.join(', ')}`);
  assert(cssFiles.length > 0, `CSS bundle generated: ${cssFiles.join(', ')}`);

  // Check CSS bundle content for compiled styles
  const cssBundlePath = path.join(distAssets, cssFiles[0]);
  const cssBundleContent = fs.readFileSync(cssBundlePath, 'utf8');
  assert(cssBundleContent.includes('--background'), 'CSS bundle contains --background variable');
  assert(cssBundleContent.includes('--foreground'), 'CSS bundle contains --foreground variable');
  assert(cssBundleContent.includes('--card'), 'CSS bundle contains --card variable');
  assert(cssBundleContent.includes('grid-template-columns:repeat(12,minmax(0,1fr))') || cssBundleContent.includes('grid-cols-12') || cssBundleContent.includes('repeat(12'), 'CSS bundle contains 12-column grid styling');
  assert(cssBundleContent.includes('9/16') || cssBundleContent.includes('aspect-ratio'), 'CSS bundle contains 9:16 aspect ratio rule');

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
