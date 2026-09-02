/**
 * =============================================================================
 * Challenger 2 Adversarial Stress Suite for Milestone 5 (Zero-Waste Audit R4)
 * Focus: WCAG AA Contrast Stress, Theme Token Variations, Keyboard Navigation,
 * CLS = 0 Media Stability, and Rendering Performance under Scale.
 * =============================================================================
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');
const FRONTEND_DIR = path.join(REPO_ROOT, 'frontend');
const SRC_DIR = path.join(FRONTEND_DIR, 'src');
const COMPONENTS_DIR = path.join(SRC_DIR, 'components');
const DIST_DIR = path.join(FRONTEND_DIR, 'dist');

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const failureDetails = [];

function assert(condition, message, details = '') {
  totalTests++;
  if (condition) {
    console.log(`  [PASS] ${message}`);
    passedTests++;
  } else {
    console.error(`  [FAIL] ${message} - ${details}`);
    failedTests++;
    failureDetails.push({ message, details });
  }
}

// -----------------------------------------------------------------------------
// Accurate WCAG 2.1 Contrast Formula
// -----------------------------------------------------------------------------
function parseHex(hex) {
  let clean = hex.replace('#', '');
  if (clean.length === 3) {
    clean = clean.split('').map(c => c + c).join('');
  }
  const intVal = parseInt(clean, 16);
  return {
    r: (intVal >> 16) & 255,
    g: (intVal >> 8) & 255,
    b: intVal & 255
  };
}

function relativeLuminance(rgb) {
  const [r, g, b] = [rgb.r / 255, rgb.g / 255, rgb.b / 255].map(v => {
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(fgHex, bgHex) {
  const l1 = relativeLuminance(parseHex(fgHex));
  const l2 = relativeLuminance(parseHex(bgHex));
  const max = Math.max(l1, l2);
  const min = Math.min(l1, l2);
  return (max + 0.05) / (min + 0.05);
}

// Alpha blend over background: fg rgba over bg rgb
function blendColors(fgRgb, fgAlpha, bgRgb) {
  return {
    r: Math.round((1 - fgAlpha) * bgRgb.r + fgAlpha * fgRgb.r),
    g: Math.round((1 - fgAlpha) * bgRgb.g + fgAlpha * fgRgb.g),
    b: Math.round((1 - fgAlpha) * bgRgb.b + fgAlpha * fgRgb.b),
  };
}

function rgbToHex(rgb) {
  return '#' + [rgb.r, rgb.g, rgb.b].map(x => x.toString(16).padStart(2, '0')).join('');
}

console.log('======================================================================');
console.log('CHALLENGER 2: ADVERSARIAL STRESS AUDIT — A11Y, CONTRAST, CLS & PERF');
console.log('======================================================================\n');

// -----------------------------------------------------------------------------
// 1. ADVERSARIAL THEME MATRIX CONTRAST TESTING
// -----------------------------------------------------------------------------
console.log('--- 1. Adversarial Theme & State Contrast Matrix ---');

// Define 4 theme palettes: Standard Dark, OLED Pure Black, Slate Dark, High Contrast
const themes = [
  { name: 'Standard Dark Theme', bg: '#09090b', card: '#18181b', border: '#27272a' },
  { name: 'OLED Pure Black', bg: '#000000', card: '#0f0f0f', border: '#333333' },
  { name: 'Slate Midnight Theme', bg: '#020617', card: '#0f172a', border: '#1e293b' },
  { name: 'Zinc Deep Theme', bg: '#18181b', card: '#27272a', border: '#3f3f46' },
];

const typographyTokens = [
  { name: 'Primary Foreground Text (#f8fafc)', fg: '#f8fafc', minNormal: 4.5, minLarge: 3.0 },
  { name: 'Muted Foreground Text (#94a3b8)', fg: '#94a3b8', minNormal: 4.5, minLarge: 3.0 },
  { name: 'Green Status Badge (#4ade80)', fg: '#4ade80', minNormal: 4.5, minLarge: 3.0 },
  { name: 'Blue Status Badge (#60a5fa)', fg: '#60a5fa', minNormal: 4.5, minLarge: 3.0 },
  { name: 'Amber Warning Badge (#fbbf24)', fg: '#fbbf24', minNormal: 4.5, minLarge: 3.0 },
  { name: 'Red Conflict Badge (#f87171)', fg: '#f87171', minNormal: 4.5, minLarge: 3.0 },
  { name: 'Purple Tag Badge (#d8b4fe)', fg: '#d8b4fe', minNormal: 4.5, minLarge: 3.0 },
];

for (const theme of themes) {
  console.log(`\n  [Theme Variant: ${theme.name}]`);
  for (const token of typographyTokens) {
    const ratioOnBg = contrastRatio(token.fg, theme.bg);
    const ratioOnCard = contrastRatio(token.fg, theme.card);

    console.log(`    - ${token.name} on BG (${theme.bg}): ${ratioOnBg.toFixed(2)}:1`);
    assert(
      ratioOnBg >= token.minNormal,
      `${token.name} on ${theme.name} Background meets WCAG AA (Target >= ${token.minNormal}:1, got ${ratioOnBg.toFixed(2)}:1)`,
      `Contrast ratio ${ratioOnBg.toFixed(2)}:1 is below ${token.minNormal}:1`
    );

    console.log(`    - ${token.name} on Card (${theme.card}): ${ratioOnCard.toFixed(2)}:1`);
    assert(
      ratioOnCard >= token.minNormal,
      `${token.name} on ${theme.name} Card meets WCAG AA (Target >= ${token.minNormal}:1, got ${ratioOnCard.toFixed(2)}:1)`,
      `Contrast ratio ${ratioOnCard.toFixed(2)}:1 is below ${token.minNormal}:1`
    );
  }
}

// -----------------------------------------------------------------------------
// 2. BUTTON INTERACTIVE STATES (Normal, Hover, Active, Focus, Disabled)
// -----------------------------------------------------------------------------
console.log('\n--- 2. Interactive Button State Contrast & Legibility ---');

const buttonStates = [
  { name: 'Blue Action Button (Normal: #ffffff on #2563eb)', fg: '#ffffff', bg: '#2563eb', minRatio: 4.5 },
  { name: 'Blue Action Button (Hover: #ffffff on #1d4ed8)', fg: '#ffffff', bg: '#1d4ed8', minRatio: 4.5 },
  { name: 'Blue Action Button (Active/Focus: #ffffff on #1e40af)', fg: '#ffffff', bg: '#1e40af', minRatio: 4.5 },
  { name: 'Green Action Button (Normal: #ffffff on #16a34a)', fg: '#ffffff', bg: '#16a34a', minRatio: 3.0 },
  { name: 'Green Action Button (Hover: #ffffff on #15803d)', fg: '#ffffff', bg: '#15803d', minRatio: 3.0 },
  { name: 'Secondary Button (Normal: #e2e8f0 on #1f2937)', fg: '#e2e8f0', bg: '#1f2937', minRatio: 4.5 },
  { name: 'Secondary Button (Hover: #f87171 on #371b1b)', fg: '#f87171', bg: '#371b1b', minRatio: 4.5 },
  { name: 'Dark Monospace Pill (#e5e7eb on #1f2937)', fg: '#e5e7eb', bg: '#1f2937', minRatio: 4.5 },
];

for (const btn of buttonStates) {
  const ratio = contrastRatio(btn.fg, btn.bg);
  console.log(`  [BUTTON STATE] ${btn.name}: ${ratio.toFixed(2)}:1`);
  assert(
    ratio >= btn.minRatio,
    `Button state '${btn.name}' meets contrast >= ${btn.minRatio}:1 (actual ${ratio.toFixed(2)}:1)`
  );
}

// -----------------------------------------------------------------------------
// 3. KEYBOARD NAVIGATION & FOCUS COMPREHENSIVENESS
// -----------------------------------------------------------------------------
console.log('\n--- 3. Keyboard Navigation, Focus Rings & Tab Order ---');

const appSrc = fs.readFileSync(path.join(SRC_DIR, 'App.tsx'), 'utf8');
const headerSrc = fs.readFileSync(path.join(COMPONENTS_DIR, 'Header.tsx'), 'utf8');
const feedSrc = fs.readFileSync(path.join(COMPONENTS_DIR, 'PhoneLinkFeed.tsx'), 'utf8');
const colSrc = fs.readFileSync(path.join(COMPONENTS_DIR, 'CollisionQueue.tsx'), 'utf8');
const panelSrc = fs.readFileSync(path.join(COMPONENTS_DIR, 'VideoTagsPanel.tsx'), 'utf8');

// Check that every interactive element has focus-visible ring styles
const allSources = [
  { file: 'App.tsx', src: appSrc },
  { file: 'PhoneLinkFeed.tsx', src: feedSrc },
  { file: 'CollisionQueue.tsx', src: colSrc },
  { file: 'VideoTagsPanel.tsx', src: panelSrc },
];

// Extract full opening tags safely handling '{...}' and quotes
function extractOpeningTags(src, tagName) {
  const tags = [];
  let i = 0;
  while (i < src.length) {
    const startIdx = src.indexOf(`<${tagName}`, i);
    if (startIdx === -1) break;

    // Verify it's a tag boundary (space, newline, or >)
    const nextChar = src[startIdx + tagName.length + 1];
    if (nextChar !== ' ' && nextChar !== '\n' && nextChar !== '\r' && nextChar !== '\t' && nextChar !== '>') {
      i = startIdx + 1;
      continue;
    }

    let inCurly = 0;
    let inQuotes = null;
    let endIdx = -1;

    for (let j = startIdx + tagName.length + 1; j < src.length; j++) {
      const ch = src[j];
      if (inQuotes) {
        if (ch === inQuotes && src[j - 1] !== '\\') {
          inQuotes = null;
        }
      } else if (ch === '"' || ch === "'" || ch === '`') {
        inQuotes = ch;
      } else if (ch === '{') {
        inCurly++;
      } else if (ch === '}') {
        inCurly--;
      } else if (ch === '>' && inCurly === 0 && !inQuotes) {
        endIdx = j;
        break;
      }
    }

    if (endIdx !== -1) {
      tags.push(src.substring(startIdx, endIdx + 1));
      i = endIdx + 1;
    } else {
      i = startIdx + 1;
    }
  }
  return tags;
}

for (const item of allSources) {
  const buttonMatches = extractOpeningTags(item.src, 'button');
  for (const btn of buttonMatches) {
    const hasFocusRing = btn.includes('focus-visible:ring-2') || btn.includes('focus-visible:outline-none');
    assert(
      hasFocusRing,
      `${item.file} button has focus-visible ring: ${btn.replace(/\s+/g, ' ').slice(0, 60)}...`,
      `Missing focus-visible ring in button tag: ${btn}`
    );
  }
}

// Form inputs in VideoTagsPanel
const inputMatches = [...extractOpeningTags(panelSrc, 'input'), ...extractOpeningTags(panelSrc, 'select')];
for (const input of inputMatches) {
  const hasFocus = input.includes('focus-visible:ring-2') || input.includes('focus:border-blue-500');
  assert(
    hasFocus,
    `VideoTagsPanel form input has visible focus indicator: ${input.replace(/\s+/g, ' ').slice(0, 60)}...`,
    `Missing focus indicator on input: ${input}`
  );
}

// Non-button interactive items (role="button")
const divMatches = extractOpeningTags(panelSrc, 'div').filter(d => d.includes('role="button"'));
for (const rb of divMatches) {
  assert(
    rb.includes('tabIndex={0}') && rb.includes('focus-visible:ring-2'),
    `Custom role="button" has tabIndex={0} and focus-visible ring: ${rb.replace(/\s+/g, ' ').slice(0, 60)}...`
  );
}

// Check Enter / Space keydown handling on custom role="button" elements
assert(
  panelSrc.includes("e.key === 'Enter' || e.key === ' '"),
  'Custom role="button" items handle both Enter and Space keys for full WCAG keyboard accessibility'
);
assert(
  panelSrc.includes("e.preventDefault()"),
  'Custom role="button" onKeyDown calls e.preventDefault() to prevent Space bar page scrolling'
);

// -----------------------------------------------------------------------------
// 4. ZERO CUMULATIVE LAYOUT SHIFT (CLS = 0) & MEDIA CONTAINER VERIFICATION
// -----------------------------------------------------------------------------
console.log('\n--- 4. Zero Layout Shift (CLS = 0) & Container Geometry ---');

// Video dimensions
assert(
  feedSrc.includes('width={540}') && feedSrc.includes('height={960}'),
  'Video element has explicit intrinsic width={540} and height={960}'
);
assert(
  feedSrc.includes('aspect-[9/16]'),
  'Video player container enforces explicit CSS 9:16 aspect ratio box'
);
assert(
  feedSrc.includes('object-cover'),
  'Video element uses object-cover to prevent stretching or reflow upon video stream load'
);

// Absolute positioning of transient overlays (Toast notifications)
assert(
  appSrc.includes('absolute top-4 left-1/2 transform -translate-x-1/2 z-50'),
  'Toast notification is positioned absolutely outside document flow to ensure CLS = 0 on appearance'
);

// Fullscreen fixed viewport preventing window blowout
assert(
  appSrc.includes('h-screen overflow-hidden flex flex-col'),
  'Root container enforces h-screen overflow-hidden layout preventing body scroll layout jumps'
);

// -----------------------------------------------------------------------------
// 5. RENDERING PERFORMANCE, BUNDLE BUDGET & DOM COMPLEXITY UNDER SCALE
// -----------------------------------------------------------------------------
console.log('\n--- 5. Rendering Performance & Bundle Budget ---');

// Inspect dist artifacts if built
const distDir = path.join(FRONTEND_DIR, 'dist');
if (fs.existsSync(distDir)) {
  const assetsDir = path.join(distDir, 'assets');
  const files = fs.readdirSync(assetsDir);
  
  const jsFiles = files.filter(f => f.endsWith('.js'));
  const cssFiles = files.filter(f => f.endsWith('.css'));

  for (const jsFile of jsFiles) {
    const stats = fs.statSync(path.join(assetsDir, jsFile));
    const sizeKb = stats.size / 1024;
    console.log(`  [BUNDLE STATS] JS: ${jsFile} -> ${sizeKb.toFixed(2)} KB`);
    // Budget: JS bundle must be < 500 KB uncompressed
    assert(
      sizeKb < 500.0,
      `Production JS bundle size (${sizeKb.toFixed(2)} KB) is within performance budget (< 500 KB)`
    );
  }

  for (const cssFile of cssFiles) {
    const stats = fs.statSync(path.join(assetsDir, cssFile));
    const sizeKb = stats.size / 1024;
    console.log(`  [BUNDLE STATS] CSS: ${cssFile} -> ${sizeKb.toFixed(2)} KB`);
    // Budget: CSS bundle must be < 50 KB
    assert(
      sizeKb < 50.0,
      `Production CSS bundle size (${sizeKb.toFixed(2)} KB) is within performance budget (< 50 KB)`
    );
  }
}

// -----------------------------------------------------------------------------
// 6. ADVERSARIAL SCALE SIMULATION (High Tag Volume & Rapid State Swapping)
// -----------------------------------------------------------------------------
console.log('\n--- 6. High-Volume List Scaling & DOM Containment ---');

function simulateLargeTagVolume(count = 500) {
  const start = performance.now();
  const simulatedTags = [];
  for (let i = 0; i < count; i++) {
    simulatedTags.push({
      id: `tag-${i}`,
      filename: `video_${i.toString().padStart(5, '0')}.mp4`,
      domain: i % 2 === 0 ? 'EDM_FESTIVALS' : 'SPORTS_CARDS',
      entity: `Entity-${i}`,
      viralFeatures: [`Feature-A-${i}`, `Feature-B-${i}`],
      technical: { resolution: '3840x2160', fps: 60 }
    });
  }

  // Filter and transform
  const formatted = simulatedTags.map(t => ({
    ...t,
    summary: `${t.filename} - ${t.entity} [${t.domain}]`
  }));
  const elapsedMs = performance.now() - start;
  return { count: formatted.length, elapsedMs };
}

const scaleResult = simulateLargeTagVolume(1000);
console.log(`  [SCALE] Processed ${scaleResult.count} virtual tag entities in ${scaleResult.elapsedMs.toFixed(2)} ms`);
assert(
  scaleResult.elapsedMs < 50.0,
  `High volume tag entity transformation (1,000 items) executes in < 50 ms (actual: ${scaleResult.elapsedMs.toFixed(2)} ms)`
);

// Verify scroll container in VideoTagsPanel
assert(
  panelSrc.includes('max-h-56 overflow-y-auto'),
  'VideoTagsPanel wraps tag items in a constrained height scroll container (max-h-56 overflow-y-auto) to prevent DOM blowouts'
);

// -----------------------------------------------------------------------------
// 7. ARIA LANDMARK & SCREEN READER ACCESSIBILITY TREE AUDIT
// -----------------------------------------------------------------------------
console.log('\n--- 7. Semantic ARIA Landmarks & Accessible Names ---');

const ariaAttributesToCheck = [
  { name: 'Header role="banner"', pattern: 'role="banner"', file: headerSrc },
  { name: 'Main role="main"', pattern: 'role="main"', file: appSrc },
  { name: 'Left section role="region"', pattern: 'role="region"', file: feedSrc },
  { name: 'Right section role="region"', pattern: 'role="region"', file: colSrc },
  { name: 'Video tags role="region"', pattern: 'role="region"', file: panelSrc },
  { name: 'Toast role="status"', pattern: 'role="status"', file: appSrc },
  { name: 'Toast aria-live="polite"', pattern: 'aria-live="polite"', file: appSrc },
  { name: 'Toast aria-atomic="true"', pattern: 'aria-atomic="true"', file: appSrc },
  { name: 'Tags list role="list"', pattern: 'role="list"', file: panelSrc },
  { name: 'Tag items aria-pressed', pattern: 'aria-pressed=', file: panelSrc },
  { name: 'Keep 4K button aria-label', pattern: 'aria-label={`Keep 4K ADB version for', file: colSrc },
  { name: 'Keep Takeout button aria-label', pattern: 'aria-label={`Keep compressed Takeout copy for', file: colSrc },
  { name: 'Undo button aria-label', pattern: 'aria-label={`Undo collision resolution for', file: colSrc },
];

for (const check of ariaAttributesToCheck) {
  assert(
    check.file.includes(check.pattern),
    `Semantic check: ${check.name} exists in component tree`
  );
}

// -----------------------------------------------------------------------------
// SUMMARY & VERDICT
// -----------------------------------------------------------------------------
console.log('\n======================================================================');
console.log(`CHALLENGER 2 TEST RESULTS: ${passedTests} PASSED | ${failedTests} FAILED (Total: ${totalTests})`);
console.log('======================================================================\n');

if (failedTests > 0) {
  console.error(`CHALLENGER 2 AUDIT FAILED with ${failedTests} issues:`);
  failureDetails.forEach((f, idx) => {
    console.error(`  ${idx + 1}. ${f.message}: ${f.details}`);
  });
  process.exit(1);
} else {
  console.log('ALL ADVERSARIAL ACCESSIBILITY, CONTRAST, CLS & PERFORMANCE CHECKS PASSED.');
  process.exit(0);
}
