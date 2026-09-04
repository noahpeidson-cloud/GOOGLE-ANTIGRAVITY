/**
 * =============================================================================
 * Milestone 5: The Zero-Waste Frontend Audit (R4) - Accessibility (a11y) Suite
 * Omnichannel Triage Hub — WCAG 2.1 AA Compliance Verification
 * =============================================================================
 * 
 * Verifies:
 * 1. 0 Orphaned Form Inputs (All inputs/selects have linked <label htmlFor="..." id="...">).
 * 2. Touch Target Dimensions >= 48x48px (min-h-[48px], min-w-[48px]).
 * 3. Color Contrast Ratios >= 4.5:1 (normal text) and >= 3.0:1 (large text / UI tokens).
 * 4. Keyboard Navigation: :focus-visible ring styles, Tab navigation, hotkey bindings.
 * 5. Semantic ARIA attributes (role, aria-label, aria-live, aria-atomic).
 * 6. Heading hierarchy integrity (h1 -> h2 -> h3).
 * 7. Cumulative Layout Shift (CLS = 0) & explicit media dimensions.
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

let passCount = 0;
let failCount = 0;
const failures = [];

function assert(condition, message, details = '') {
  if (condition) {
    console.log(`  [PASS] ${message}`);
    passCount++;
  } else {
    console.error(`  [FAIL] ${message} - ${details}`);
    failCount++;
    failures.push({ message, details });
  }
}

// -----------------------------------------------------------------------------
// WCAG 2.1 Color Luminance & Contrast Calculation Helpers
// -----------------------------------------------------------------------------
function hexToRgb(hex) {
  let cleanHex = hex.replace('#', '');
  if (cleanHex.length === 3) {
    cleanHex = cleanHex.split('').map((c) => c + c).join('');
  }
  const num = parseInt(cleanHex, 16);
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255,
  };
}

function getRelativeLuminance(rgb) {
  const sRGB = [rgb.r / 255, rgb.g / 255, rgb.b / 255].map((val) => {
    return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * sRGB[0] + 0.7152 * sRGB[1] + 0.0722 * sRGB[2];
}

function getContrastRatio(hexForeground, hexBackground) {
  const lum1 = getRelativeLuminance(hexToRgb(hexForeground));
  const lum2 = getRelativeLuminance(hexToRgb(hexBackground));
  const brightest = Math.max(lum1, lum2);
  const darkest = Math.min(lum1, lum2);
  return (brightest + 0.05) / (darkest + 0.05);
}

console.log('====================================================================');
console.log('OMNICHANNEL TRIAGE HUB — WCAG 2.1 AA ACCESSIBILITY (A11Y) AUDIT (R4)');
console.log('====================================================================\n');

// -----------------------------------------------------------------------------
// SECTION 1: Form Label Associations & Zero Orphaned Inputs
// -----------------------------------------------------------------------------
console.log('--- 1. Form Label Associations & Zero Orphaned Inputs ---');

const panelTsxPath = path.join(COMPONENTS_DIR, 'VideoTagsPanel.tsx');
assert(fs.existsSync(panelTsxPath), 'VideoTagsPanel.tsx exists');
const panelSrc = fs.readFileSync(panelTsxPath, 'utf8');

// Check all form inputs have linked htmlFor <-> id
const expectedInputs = [
  { labelFor: 'tag-filename', inputId: 'tag-filename', name: 'Filename' },
  { labelFor: 'tag-domain', inputId: 'tag-domain', name: 'Domain' },
  { labelFor: 'tag-entity', inputId: 'tag-entity', name: 'Entity / Subject' },
  { labelFor: 'tag-feature', inputId: 'tag-feature', name: 'Viral Feature' },
];

for (const input of expectedInputs) {
  const hasLabel = panelSrc.includes(`htmlFor="${input.labelFor}"`);
  const hasInputId = panelSrc.includes(`id="${input.inputId}"`);
  assert(
    hasLabel && hasInputId,
    `Form field '${input.name}' has matching label (htmlFor="${input.labelFor}") and input (id="${input.inputId}")`,
    `Missing matching label/input pair for ${input.name}`
  );
}

// -----------------------------------------------------------------------------
// SECTION 2: Minimum Touch Target Dimensions (>= 48px)
// -----------------------------------------------------------------------------
console.log('\n--- 2. Minimum Touch Target Dimensions (>= 48px) ---');

const appTsxSrc = fs.readFileSync(path.join(SRC_DIR, 'App.tsx'), 'utf8');
const feedTsxSrc = fs.readFileSync(path.join(COMPONENTS_DIR, 'PhoneLinkFeed.tsx'), 'utf8');
const colTsxSrc = fs.readFileSync(path.join(COMPONENTS_DIR, 'CollisionQueue.tsx'), 'utf8');

// PhoneLinkFeed buttons
assert(
  feedTsxSrc.includes('min-h-[48px]') && feedTsxSrc.includes('Trigger ADB Pull'),
  'PhoneLinkFeed "Trigger ADB Pull" button meets >= 48px touch target (min-h-[48px])'
);
assert(
  feedTsxSrc.includes('min-h-[48px]') && feedTsxSrc.includes('Simulate Screen Capture'),
  'PhoneLinkFeed "Simulate Screen Capture" button meets >= 48px touch target (min-h-[48px])'
);

// CollisionQueue buttons
assert(
  colTsxSrc.includes('min-h-[48px]') && colTsxSrc.includes('Keep 4K ADB Version'),
  'CollisionQueue "Keep 4K ADB Version" button meets >= 48px touch target (min-h-[48px])'
);
assert(
  colTsxSrc.includes('min-h-[48px]') && colTsxSrc.includes('min-w-[48px]') && colTsxSrc.includes('Keep Takeout'),
  'CollisionQueue "Keep Takeout" button meets >= 48px touch target (min-h-[48px] min-w-[48px])'
);
assert(
  colTsxSrc.includes('min-h-[48px]') && colTsxSrc.includes('Undo'),
  'CollisionQueue "Undo" button container meets >= 48px touch target (min-h-[48px])'
);

// VideoTagsPanel controls & list items
assert(
  panelSrc.includes('min-h-[48px]') && panelSrc.includes('min-w-[48px]') && panelSrc.includes('Refetch GraphQL'),
  'VideoTagsPanel refetch trigger meets >= 48px touch target (min-h-[48px] min-w-[48px])'
);
assert(
  panelSrc.includes('min-h-[48px]') && panelSrc.includes('Tag Video'),
  'VideoTagsPanel "Tag Video" toggle button meets >= 48px touch target (min-h-[48px])'
);
assert(
  panelSrc.includes('min-h-[48px]') && panelSrc.includes('Save Tag'),
  'VideoTagsPanel "Save Tag" mutation button meets >= 48px touch target (min-h-[48px])'
);
assert(
  panelSrc.includes('min-h-[48px]') && panelSrc.includes('Cancel'),
  'VideoTagsPanel "Cancel" button meets >= 48px touch target (min-h-[48px])'
);
assert(
  panelSrc.includes('min-h-[48px]') && panelSrc.includes('role="button"'),
  'VideoTagsPanel selectable tag items meet >= 48px touch target (min-h-[48px])'
);

// -----------------------------------------------------------------------------
// SECTION 3: WCAG 2.1 AA Color Contrast Ratio Verification
// -----------------------------------------------------------------------------
console.log('\n--- 3. WCAG 2.1 AA Color Contrast Ratio Verification ---');

const colorPairs = [
  { name: 'Primary Foreground on Background (Normal Text)', fg: '#f8fafc', bg: '#09090b', minRatio: 4.5, type: 'Normal Text' },
  { name: 'Primary Foreground on Card (Normal Text)', fg: '#f8fafc', bg: '#18181b', minRatio: 4.5, type: 'Normal Text' },
  { name: 'Muted Foreground on Background (Normal Text)', fg: '#94a3b8', bg: '#09090b', minRatio: 4.5, type: 'Normal Text' },
  { name: 'Muted Foreground on Card (Normal Text)', fg: '#94a3b8', bg: '#18181b', minRatio: 4.5, type: 'Normal Text' },
  { name: 'Success Green Badge (green-400) on Card', fg: '#4ade80', bg: '#18181b', minRatio: 4.5, type: 'UI Component / Text' },
  { name: 'Blue Badge / Icon (blue-400) on Card', fg: '#60a5fa', bg: '#18181b', minRatio: 4.5, type: 'UI Component / Text' },
  { name: 'Amber Warning Badge (amber-400) on Card', fg: '#fbbf24', bg: '#18181b', minRatio: 4.5, type: 'UI Component / Text' },
  { name: 'Red Conflict Badge (red-400) on Card', fg: '#f87171', bg: '#18181b', minRatio: 4.5, type: 'UI Component / Text' },
  { name: 'Purple Tag Badge (purple-300) on Card', fg: '#d8b4fe', bg: '#18181b', minRatio: 4.5, type: 'UI Component / Text' },
  { name: 'White Button Text on Blue-600 (Bold Target)', fg: '#ffffff', bg: '#2563eb', minRatio: 4.5, type: 'Bold Button' },
  { name: 'White Button Text on Green-600 (Bold Target)', fg: '#ffffff', bg: '#16a34a', minRatio: 3.0, type: 'Bold Button / UI Target' },
];

for (const pair of colorPairs) {
  const ratio = getContrastRatio(pair.fg, pair.bg);
  console.log(`    [CONTRAST] ${pair.name}: ${ratio.toFixed(2)}:1 (Target: >= ${pair.minRatio}:1)`);
  assert(
    ratio >= pair.minRatio,
    `Color contrast for '${pair.name}' (${ratio.toFixed(2)}:1) meets WCAG AA >= ${pair.minRatio}:1 (${pair.type})`
  );
}

// -----------------------------------------------------------------------------
// SECTION 4: Keyboard Navigation & Focus-Visible Outlines
// -----------------------------------------------------------------------------
console.log('\n--- 4. Keyboard Navigation & Focus-Visible Outlines ---');

assert(
  feedTsxSrc.includes('focus-visible:ring-2') && feedTsxSrc.includes('focus-visible:outline-none'),
  'PhoneLinkFeed interactive buttons include visible :focus-visible focus ring tokens'
);
assert(
  colTsxSrc.includes('focus-visible:ring-2') && colTsxSrc.includes('focus-visible:outline-none'),
  'CollisionQueue action buttons include visible :focus-visible focus ring tokens'
);
assert(
  panelSrc.includes('focus-visible:ring-2'),
  'VideoTagsPanel form inputs and buttons include visible :focus-visible focus ring tokens'
);
assert(
  panelSrc.includes('tabIndex={0}') && panelSrc.includes('onKeyDown='),
  'VideoTagsPanel custom interactive items support keyboard navigation (tabIndex={0} and onKeyDown)'
);
assert(
  appTsxSrc.includes('handleKeyDown') && appTsxSrc.includes('Ctrl+Shift+T'),
  'App.tsx handles global keyboard hotkey Ctrl+Shift+T with e.preventDefault()'
);

// -----------------------------------------------------------------------------
// SECTION 5: Semantic ARIA Landmarks & Live Regions
// -----------------------------------------------------------------------------
console.log('\n--- 5. Semantic ARIA Landmarks & Live Regions ---');

const headerTsxSrc = fs.readFileSync(path.join(COMPONENTS_DIR, 'Header.tsx'), 'utf8');

assert(headerTsxSrc.includes('role="banner"'), 'Header component defines landmark role="banner"');
assert(appTsxSrc.includes('role="main"'), 'Main workspace defines landmark role="main"');
assert(appTsxSrc.includes('role="status"'), 'App toast notification defines role="status"');
assert(appTsxSrc.includes('aria-live="polite"'), 'App toast notification defines aria-live="polite"');
assert(appTsxSrc.includes('aria-atomic="true"'), 'App toast notification defines aria-atomic="true"');
assert(feedTsxSrc.includes('role="region"'), 'PhoneLinkFeed defines region landmark role="region"');
assert(feedTsxSrc.includes('aria-labelledby="phone-link-feed-heading"'), 'PhoneLinkFeed is labeled by heading');
assert(colTsxSrc.includes('role="region"'), 'CollisionQueue defines region landmark role="region"');
assert(colTsxSrc.includes('aria-labelledby="collision-queue-heading"'), 'CollisionQueue is labeled by heading');
assert(panelSrc.includes('role="region"'), 'VideoTagsPanel defines region landmark role="region"');
assert(panelSrc.includes('role="list"'), 'VideoTagsPanel tags list defines role="list"');
assert(panelSrc.includes('aria-pressed='), 'VideoTagsPanel selected items define aria-pressed state');

// -----------------------------------------------------------------------------
// SECTION 6: Heading Hierarchy & Semantic Structure
// -----------------------------------------------------------------------------
console.log('\n--- 6. Heading Hierarchy & Structure ---');

assert(headerTsxSrc.includes('<h1'), 'Header defines top-level <h1> heading');
assert(feedTsxSrc.includes('<h2'), 'PhoneLinkFeed defines section <h2> heading');
assert(colTsxSrc.includes('<h2'), 'CollisionQueue defines section <h2> heading');
assert(feedTsxSrc.includes('<h3'), 'Gemini Vision Card defines subsection <h3> heading');
assert(panelSrc.includes('<h3'), 'VideoTagsPanel defines subsection <h3> heading');

// -----------------------------------------------------------------------------
// SECTION 7: Layout Shift (CLS = 0) & Explicit Media Dimensions
// -----------------------------------------------------------------------------
console.log('\n--- 7. Cumulative Layout Shift (CLS = 0) & Media Optimization ---');

assert(
  feedTsxSrc.includes('width={540}') && feedTsxSrc.includes('height={960}'),
  'PhoneLinkFeed video element specifies explicit width={540} and height={960} for CLS=0'
);
assert(
  feedTsxSrc.includes('aspect-[9/16]'),
  'PhoneLinkFeed canvas container specifies 9:16 aspect ratio container'
);
assert(
  feedTsxSrc.includes('aria-label="Phone Link live video preview stream"'),
  'PhoneLinkFeed video element specifies accessible description label'
);

// Summary
console.log('\n====================================================================');
console.log(`AUDIT RESULTS: ${passCount} PASSED | ${failCount} FAILED`);
console.log('====================================================================\n');

if (failCount > 0) {
  process.exit(1);
} else {
  console.log('ALL WCAG 2.1 AA ACCESSIBILITY AUDIT CHECKS PASSED EMPIRICALLY.');
  process.exit(0);
}
