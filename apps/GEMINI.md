# [APPS] Application Engineering & Architecture Standards

<system>
## Operational Scope & Domain Context
This directory (`/apps`) contains general software applications, dashboards, API services, and tooling built for Noah Eidson's workspace.
Operational focus: Production-grade web applications (Streamlit, React/Vite), SQLite transactional data layers, and modular automation utilities.
</system>

## Architectural Principles & Design Standards
- **Clean Architecture & Decoupling**: Strictly separate presentation layers (UI/Streamlit components), domain business logic, and data access layers (SQLite / Pandas adapters).
- **Modularity & Interface Contracts**: All functions and classes must feature explicit type annotations, docstrings, and clean boundary interfaces.
- **Resilience & Fault Tolerance**:
  - Implement comprehensive error handling and structured logging.
  - Implement graceful degradation when upstream services or data sources are unavailable.
  - Wrap database operations in transactional contexts with proper commit/rollback handling.

## Approved Tooling & Frameworks
- **Frontend / UI**: `streamlit`, React + Vite.
- **Data & Storage**: `sqlite3`, `pandas`.
- **Backend / Utility**: Standard Python 3.10+ libraries.
- **Dependency Discipline**: No unapproved external dependencies or heavy ORMs without explicit authorization.

## Verification & Quality Assurance Protocol
- **Unit & Integration Tests**: Implement executable unit tests for core logic using `pytest` or `unittest`.
- **UI Verification**: Validate Streamlit application launch and page routing without runtime exceptions.
- **Data Integrity**: Verify database migration scripts and schema definitions before deployment.

## Proactive Verification Workflows
- **CWV Performance Enforcer**: For React/Vite dashboards, read the `debug-optimize-lcp` skill to use Chrome DevTools MCP. Automatically trace page loads (`performance_start_trace`) and enforce a Largest Contentful Paint (LCP) of < 2.5s before final deployment, actively correcting render delays.
- **Mobile Layout Validator**: For any user-facing UI, read the `android-cli` skill to start an emulator and run `android layout` and `android screen` capture. Mechanically verify that Streamlit dashboards and 9:16 web views render correctly within mobile constraints.

## Domain Isolation
- **Domain Containment**: Keep generic application components decoupled from specific hobby schemas (Sports Cards 21-variable schema or Content Creation FFmpeg transcoding presets) unless an app is explicitly designed as a dedicated domain client in a dedicated sub-package.
