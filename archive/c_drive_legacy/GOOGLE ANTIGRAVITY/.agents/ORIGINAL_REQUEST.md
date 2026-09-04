# Original User Request

## Initial Request — 2026-08-27T11:12:06Z

Task Overview:
Build the foundation of the "Omnichannel Triage Hub" web application based on the `triage_ui_mockup.html` design.

Requirements:
1. R1. The React Vite Foundation
   Initialize a React Vite frontend in `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/frontend`. Configure Tailwind CSS. Replicate the two-column layout from `triage_ui_mockup.html` using React components.
2. R2. The Python FastAPI Bridge
   Initialize a FastAPI project in `g:/My Drive/GOOGLE ANTIGRAVITY/omnichannel_triage_hub/local_daemon`. Expose `POST /api/trigger-adb-pull` and `POST /api/capture-screen` endpoints.
3. R3. Firebase Data Connect Integration
   Configure the React frontend to initialize Firebase. Generate the Firebase Data Connect SDK (`@firebase/data-connect`) so the frontend can query the `video_tags` PostgreSQL table directly using GraphQL.
4. R4. The Zero-Waste Frontend Audit (`R4`)
   Before final delivery, the Red Team must execute a memory leak and accessibility audit to ensure the frontend has 0 detached DOM nodes and passes semantic a11y checks.

Acceptance Criteria:
- Running `npm run dev` in the frontend directory loads the two-column dashboard on `localhost:5173`.
- Running `uvicorn main:app --reload` launches the Python bridge on `localhost:8000`.
- Clicking a mock "Trigger ADB" button in the React UI successfully hits the FastAPI endpoint without CORS errors.
