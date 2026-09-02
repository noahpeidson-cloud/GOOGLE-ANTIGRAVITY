# Modern Web Guidance Skill Reference
Source: C:\Users\noahp\.gemini\config\plugins\modern-web-guidance-plugin\skills\modern-web-guidance\SKILL.md

Mandates search-first for modern web development best practices:
- Search command: `npx.cmd -y modern-web-guidance@latest search "<query>"`
- Retrieve command: `npx.cmd -y modern-web-guidance@latest retrieve "<id>"`

### Key Dashboard Best Practices Discovered:
1. `efficient-background-processing`:
   - Use `content-visibility: auto` on off-screen heavy components with `contain-intrinsic-size`.
   - Listen to `contentvisibilityautostatechange` events to pause high-frequency polling / WebSockets / animations when elements are offscreen, and resume when visible.
2. `interactions-in-complex-layouts`:
   - Isolate grid/column layout calculations with `content-visibility: auto` and `contain-intrinsic-size` to prevent global layout recalculation and keep INP low.
3. `css-layout` & Modern React:
   - Modern CSS Grid, subgrid, container queries `@container`, anchor positioning.
