# Dispatch Log

## 2026-08-25T23:48:43-07:00
Task Overview:
Build a Google Photos-style Media Gallery section for the Unified Ops Hub dashboard. The gallery must ingest and display albums of raw media pulled by the ingestion pipeline, allowing the user to visually browse, select, and trigger specific albums for Gemini Omni ML grading.

Requirements:
1. R1. SQLite Catalog Database
   Initialize a local SQLite database (`media_catalog.db`) with schemas for `Albums` and `Media`. It must track local proxy paths on the G: Drive, upload status, and grading results.
2. R2. Media Gallery UI (Next.js)
   Build a responsive, Google Photos-style gallery view that queries the SQLite database to organize and display local proxy videos into Albums. It must support zero-latency scrubbing of local files.
3. R3. Grading Trigger Mechanism
   Provide a UI mechanism (checkboxes/selection state) allowing the user to select an album or specific videos, and a "Grade Selected" button that dispatches a POST request to trigger the Spark/Gemini ML grading pipeline.

Acceptance Criteria:
- Backend Database Verification: A Python test script successfully creates the `media_catalog.db` schema, inserts a mock Album containing 3 mock Media entries (with local G: drive paths), and retrieves them via a `SELECT` join.
- UI Rendering & Trigger Verification:
  - A programmatic test (e.g., using `testing-library/react` or a mock DOM render) verifies that the Gallery component successfully maps over a list of mock Media objects and renders corresponding HTML `<video>` elements.
  - A programmatic test confirms that clicking the "Grade Selected" button successfully fires a mock API POST request containing the selected Media IDs.
