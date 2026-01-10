# Application Requirements

## 1. Purpose and Scope
- Provide a user-facing workflow to upload standards, generate test plans, edit sections, and create test cards.
- Provide an Admin page to manage prompts and agent configurations (no access control).
- Rename Collections to Folders in the UI (no backend or data model rename required).

## 2. Navigation and Pages
1. Home (User Workflow)
   1. Chat interface (moved from existing Home).
   2. Guided workflow for document upload, test plan generation, edit, and test card generation.
2. Admin
   1. Prompt and agent configuration management.
   2. No authentication or access control.
3. Files
   1. UI label changes: "Collections" -> "Folders".
4. Calendar
   1. Schedule and coordinate test plan and test card work.

## 3. Workflow Requirements (Home)
1. Upload
   1. Users upload standards/files into a folder (collection).
2. Prompt Preparation
   1. Users can update prompts (via Admin) to drive test plan generation based on the standard.
3. Test Plan Generation
   1. Generate a test plan broken down by each section of the uploaded file.
   2. Show per-section breakdown to the user.
4. Test Plan Editing (Form-Based)
   1. Provide a form-based editor for each test plan section.
   2. Saving edits auto-increments the test plan version.
5. Test Card Generation
   1. Test cards are broken down based on the updated test plan sections.
   2. Regeneration must be prompted and confirmed by the user.
   3. Regeneration uses the previous version as the baseline to recreate new test cards.
   4. Users can update test cards and add new sections using a form-based editor.
   5. Saving edits auto-increments the test card version.

## 4. Folders (UI Rename Only)
1. Replace "Collections" with "Folders" across UI labels and user-facing text.
2. Backend data structures and APIs remain unchanged (still collections under the hood).

## 5. Versioning Rules
1. Document versions
   1. Documents in folders can be versioned.
   2. Version numbers auto-increment on each save.
2. Test plan versions
   1. Auto-increment version numbers on save.
   2. Preserve prior versions for reference and regeneration baselines.
3. Test card versions
   1. Auto-increment version numbers on save.
   2. Preserve prior versions for reference and regeneration baselines.

## 6. Users
1. User records must include:
   1. Name
   2. Email
   3. Org
   4. Role
2. No audit trails required.

## 7. Calendar
1. Calendar events support:
   1. Test plan and test card references.
   2. Recurring events.
   3. Event ownership by a user.
2. Percent complete is user-populated (no earned value tracking).

## 8. Non-Functional Requirements
1. No access control for Admin.
2. Form-based editing for test plan and test cards.
3. Regeneration requires explicit user confirmation.

## 9. Acceptance Criteria (MVP)
1. Home page contains chat plus the full workflow (upload -> plan -> edit -> cards -> edit).
2. Admin page allows prompt updates without authentication.
3. UI labels show "Folders" instead of "Collections".
4. Test plan and test card edits create new versions with auto-increment.
5. Test card regeneration is user-confirmed and based on prior versions.
6. Calendar supports plan/card events, recurring schedules, and user ownership.
7. User profile stores name, email, org, and role.
