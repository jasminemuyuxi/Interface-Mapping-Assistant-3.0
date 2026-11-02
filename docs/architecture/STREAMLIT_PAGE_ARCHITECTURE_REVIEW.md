# Step 11.9 — Streamlit Main Page Architecture Review

Project: Interface Mapping Assistant 3.0

Review date: 2026-10-25

Review mode: Read-only source, installed-package metadata, and local documentation analysis

## Scope and Evidence

The intended architecture makes Mapping Registry the 3.0 landing page, preserves the inherited AI Mapping workflow as an independent AI Workspace, and later imports AI results into Registry Drafts for human review. Both workspaces must run within one Streamlit application. The separate 2.0 project must remain independent.

**Observed** identifies facts supported by inspected project source or the installed Streamlit package. **Recommended** identifies a proposed future implementation. **Risk assessment** identifies behavior that must be verified, not a failure reproduced during this review.

No files were modified during the underlying analysis. No Python execution, application tests, Git operations, database operations, or actual refactoring were performed. Sensitive configuration, credentials, uploaded customer documents, and saved project contents were not read. The user reported that a Git Refactoring Baseline had been created and the workspace was clean; those conditions were not independently checked with Git.

The project state document still identifies Step 11.1 as the next development step. This review follows the user's requested Step 11.9 scope without assuming that intervening tasks have been implemented or verified.

Code locations below refer to the source inspected during the analysis and may shift after future changes. Paths to installed Streamlit files are evidence references, not proposed application dependencies or imports from private library APIs.

## 1. Current Application Architecture

### Observed: Single-Script Application

`app.py` is approximately 5,800 lines long and executes as a top-level Streamlit script. It has no separate `main()` function, page-body function, `st.navigation` router, or `st.Page` registration.

The application directly imports:

- Streamlit, pandas, Pydantic, and the Anthropic SDK.
- `exporters/excel_exporter.py` for workbook generation.
- `mapping/mapping_service.py` for mapping-row construction.
- `parsers/excel_parser.py`, `parsers/json_parser.py`, and `parsers/soap_parser.py`.
- `services/document_ai_service.py` for structured document analysis.
- `models/interface_package.py` for source and target upload containers.
- `services/project_service.py` for local JSON project operations.
- `ui/mapping_grid.py` for the editable AG Grid view.

The application does not currently import the shared database Engine or SessionLocal. The Registry is therefore a future application capability, not an existing database-backed home page.

### Observed: Current UI Execution Order

```text
Configuration, schemas, helpers, and constants
→ Page configuration and existing title
→ Project management and workspace state
→ Sticky Save toolbar and keyboard shortcut
→ Source / Target package uploads
→ Structure preview and file-signature checks
→ AI Analysis & Mapping
→ Interface Information
→ Transmission Information
→ Mapping Specification
→ Return Value
→ Deferred workspace actions and Project Save
→ Excel Export
```

The existing title and page configuration still identify the application as Interface Mapping Assistant 2.0. This is observed inherited branding, not evidence that the 3.0 repository depends on the separate 2.0 repository.

### Observed: Main Source Locations

| Location | Responsibility |
|---|---|
| `app.py:28–58` | Imports of local production modules. |
| `app.py:90–193` | Pydantic AI response models. |
| `app.py:258`, `422`, `1175`, `1218` | Field normalization, structure analysis, Excel analysis, and package analysis. |
| `app.py:2061` | `reset_data()` initializes editable workspace DataFrames and editor state. |
| `app.py:2378` | `build_export_mapping_df()` adapts internal mapping rows to formal workbook columns. |
| `app.py:2493–2507` | Page configuration, title, and caption. |
| `app.py:2517–2723` | Workspace digests, unsaved-change checks, queued actions, and guard helpers. |
| `app.py:2782–2947` | Clearing/restoring a workspace, state defaults, and project selection preparation. |
| `app.py:2949` onward | Project controls. |
| `app.py:3399–3530` | Sticky Save toolbar and parent-document keyboard shortcut. |
| `app.py:3551–3627` | Source/Target upload widgets and InterfacePackage construction. |
| `app.py:3744–3752` | File-signature comparison and reset behavior. |
| `app.py:3802` onward | AI generation action and orchestration. |
| `app.py:4882–5316` | Editable business sections and state synchronization. |
| `app.py:5320` onward | Deferred workspace actions after editor synchronization. |
| `app.py:5391` onward | Deferred Project Save. |
| `app.py:5701` onward | Excel export preparation and downloads. |

## 2. Streamlit Initialization and Session State Analysis

### Observed: Installed Version and Evidence Limits

The project virtual environment contains `streamlit-1.66.0.dist-info`. Its `METADATA` declares Streamlit **1.66.0**.

The following local files were inspected as version-matched evidence:

- `.venv/Lib/site-packages/streamlit-1.66.0.dist-info/METADATA`.
- `.venv/Lib/site-packages/streamlit/commands/navigation.py`.
- `.venv/Lib/site-packages/streamlit/navigation/page.py`.
- `.venv/Lib/site-packages/streamlit/commands/page_config.py`.
- `.venv/Lib/site-packages/streamlit/runtime/state/session_state.py`.
- `.venv/Lib/site-packages/streamlit/elements/widgets/file_uploader.py`.
- Bundled `developing-with-streamlit` references for multipage applications and session state.

No Python version-discovery script was run. The running application's interpreter and environment were not checked, so the metadata establishes the installed project environment version, not the environment of any independently started server.

### Observed: Page Initialization

`app.py:2493` calls `st.set_page_config()` with a wide layout. The title and caption immediately follow.

In the installed version, `st.set_page_config()` may be called multiple times during one script run. Calls are additive, and later specified values override earlier ones. An outer entrypoint and the existing AI page therefore do not inherently produce a duplicate-configuration exception. However, the old AI page's explicit title and configuration will still affect its display.

### Observed: Session State Categories

| Category | Representative keys or values | Navigation implication |
|---|---|---|
| Editable working data | `interface_info_df`, `source_transmission_df`, `target_transmission_df`, `mapping_df`, `return_value_df` | Preserve current values independently of widget lifetimes. |
| Project identity | `current_project_id`, `current_project_created_at`, `project_name`, `project_last_saved_at` | Registry state must not overwrite these keys. |
| Editing and evidence | `editor_version`, `file_signature`, `reference_review_conflicts` | Changes can rebuild editors or reset working data. |
| Deferred actions | `pending_workspace_action`, `pending_workspace_payload`, `project_save_requested`, `generate_mapping_requested` | Preserve ordering; do not execute actions prematurely in a router. |
| Unsaved-change protection | `last_saved_workspace_digest`, `unsaved_guard_visible`, `pending_guard_action`, follow-up action payloads | Existing protection must be extended to deliberate page departure. |
| Widget-associated state | Uploaded files, project selectors, and editor widgets | Shared session state alone does not guarantee preservation after widgets stop rendering. |

State defaults are applied only when keys are absent around `app.py:2895–2917`. The existing workspace should continue to own its defaults initially; a new router should not initialize or reset its business data on every rerun.

### Observed: Unsaved Work and Deferred Actions

Important functions include:

- `_workspace_digest()` at `app.py:2517`: hashes editable snapshot content while excluding project display metadata.
- `_current_workspace_digest()` at `app.py:2548`: calculates the current workspace digest from session state.
- `_workspace_has_meaningful_content()` at `app.py:2567`: distinguishes actual user work from default values.
- `_workspace_has_unsaved_changes()` at `app.py:2658`: compares saved and current content or checks a new workspace for meaningful work.
- `_queue_workspace_action()` at `app.py:2688`: records a requested action for later processing.
- `_request_unsaved_guard()` at `app.py:2705`: prepares the existing confirmation flow.

The current guarded actions are New Project, Load Project, Delete Project, and Regenerate Mapping. They do not include multipage navigation.

The code near `app.py:5320` explicitly delays destructive workspace decisions until the editable sections have synchronized their latest values. Save processing near `app.py:5391` follows the same principle. A navigation callback that immediately leaves the AI page cannot be assumed to preserve the final active-cell edit.

### Observed: File Signatures and Reset Risk

The application builds a signature from structure types, uploaded filenames, and file-content hashes. Around `app.py:3744`, a changed signature calls `reset_data(source_preview_fields)`.

Switching away from a page can remove widget-associated state when the widget is no longer rendered. If upload widgets return empty values after navigation, a previously populated signature may become different and trigger workspace reset on return.

The installed ordinary-widget persistence facilities are not a universal solution: `file_uploader.py` does not expose a `persist_state` parameter. Its state also cannot simply be restored through ordinary assignment to its widget key. Upload handling needs an explicit compatibility design and runtime validation.

### Recommended: State Ownership

- Keep existing AI workspace keys and initialization behavior initially.
- Use a `registry_` prefix for new Registry state and a separate prefix for application navigation state if needed.
- Do not clear all session state when changing pages.
- Distinguish durable working data from widget-associated state.
- Handle navigation departure as its own guarded action, with a policy for uploaded files and unsaved edits.
- Do not claim persistence across browser refreshes, new tabs, or server restarts; session state is not permanent storage.

## 3. Existing AI Workspace Dependencies

### Observed: AI Processing

The active workspace combines deterministic processing and AI interpretation:

```text
Source / Target InterfacePackage
→ JSON or XML structure analysis and Excel reference parsing
→ Normalization and reference enrichment
→ Structured AI field mapping and return-value analysis
→ Mapping-row assembly
→ Hierarchy, conflict, and review-reason rules
→ DataFrame editing
→ JSON snapshot and Excel export
```

Relevant functions include `analyze_uploaded_interface()`, `analyze_excel_reference()`, `analyze_interface_package()`, `enrich_structure_fields()`, `build_mapping_rows()`, `apply_reference_conflicts_to_mapping_rows()`, and `apply_review_reasons_to_mapping_rows()`.

The document AI service contains part of the AI implementation. Excel fallback, batched mapping, retry handling, and return-value analysis also remain inside `app.py`. The initial routing task should not extract or alter them.

### Observed: JSON Project Persistence

`services/project_service.py` defines `PROJECTS_DIR = Path("projects")` near line 11. Its storage path is relative to the process working directory.

The service constructs and persists snapshots containing:

- Interface information.
- Source and target transmission information.
- Mapping rows.
- Return values.
- Reference conflict review state.
- Project metadata.

Uploaded file binaries are not persisted. `_restore_project_workspace()` at `app.py:2821` restores editable data and metadata, clears upload widget state, sets `file_signature` to the empty-package signature, advances `editor_version`, and refreshes the saved digest.

JSON loading is therefore not equivalent to reconstructing the complete in-memory upload context. Navigation should not silently save and reload a project as a substitute for preserving that context.

### Observed: UI and Editing Dependencies

`ui/mapping_grid.py:365` defines `render_mapping_grid()`. It enables `stopEditingWhenCellsLoseFocus`, assigns temporary `__row_id` values, and merges edited visible rows back into the complete dataset. This protects non-visible rows during filtering.

The sticky Save toolbar and keyboard handler at `app.py:3399–3530` are coupled to the current page. The handler attaches to the parent document, blurs the active editor, waits briefly, and searches for an enabled button whose text is `Save`.

The listener uses a parent-window installation marker. Navigating away does not by itself establish that the listener is removed. A future Registry button with the same label could be affected unless the shortcut is scoped or cleaned up.

### Recommended: Preserve the Workspace as a Whole Initially

Do not change parsers, mapping rules, AI prompts, JSON formats, Grid behavior, or export templates merely to establish navigation. Register the existing script as a file page and defer internal extraction to later tasks.

The future AI-to-Registry handoff should use explicit conversion and validation into a Draft. Registry services should not treat the AI page's `mapping_df` as an already approved persistent record.

## 4. Available Multipage Navigation Approaches

### Observed: Supported Native Mechanism

Installed Streamlit 1.66.0 supports:

- `st.navigation()` in a common entrypoint.
- `st.Page()` definitions backed by a Python file or callable.
- An explicit default page.
- Sidebar, top, or hidden navigation.
- Execution of the selected page through `.run()`.

The common entrypoint runs on every rerun. Only the selected registered page should be executed. File pages run in their own execution namespace; helpers defined in the router are not automatically visible within the page script.

The local `Page.run()` implementation executes a file page as a script with its file path set. This is different from a normal Python import, which caches modules.

Once `st.navigation()` is used, the legacy `pages/` auto-discovery directory is ignored. Use an explicitly registered `app_pages/` directory for new page scripts.

### Recommended: Comparison of Approaches

| Approach | Initial change | Advantages | Disadvantages and compatibility risks | Assessment |
|---|---|---|---|---|
| Add a new entrypoint using `st.navigation`, directly registering existing `app.py` as AI Workspace. | Add a small router and Registry page. | Uses the installed native API; no initial relocation or indentation of the large script; simple fallback to the old command. | Page switching still requires state preservation and departure guards. A different startup command is introduced. | Recommended. |
| Insert a selector into existing `app.py`, render Registry in one branch, and end that branch early. | Modify the original entrypoint and add Registry content. | Can preserve the existing startup filename and avoid moving the large body. | Mixes routing and legacy behavior; placement relative to imports and initialization is delicate; hidden widgets still have cleanup risks. | Feasible, but a weaker long-term boundary. |
| Move the original script to `app_pages/ai_workspace.py`. | Move the large file and create a router. | Produces an immediately cleaner directory layout. | Adds path, import, review, and regression concerns before functional separation is proven. | Defer. |
| Wrap the entire existing body in `render_ai_workspace()`. | Extensive indentation and scope changes. | Provides a callable page. | Changes global/local scope, nested functions, and execution assumptions across thousands of lines. | Not recommended for the first step. |
| Add a legacy auto-discovered `pages/` directory. | Add page files. | Small initial code addition. | Original AI script remains the primary entry; less natural fit for a Registry default home; should not be mixed with native navigation. | Not preferred. |
| Render the old script through `import app`. | Add an importing wrapper. | Superficially simple. | Import caching does not provide reliable per-rerun page execution; top-level effects become difficult to manage. | Not recommended. |
| Build a custom `exec` or `runpy` wrapper. | Add a custom execution adapter. | Avoids moving the script. | Requires maintaining execution context and rerun behavior already handled by native file pages. | Not recommended. |

All approaches that unmount the AI UI still need an explicit state strategy. Reducing file movement does not remove navigation-related compatibility work.

## 5. Recommended Navigation Architecture

### Recommended: Lightweight New Entrypoint

```text
One Streamlit service
└── streamlit_app.py
    ├── Mapping Registry — default landing page
    └── AI Workspace — existing app.py
```

The router should register a default Registry file page and an AI Workspace file page pointing directly to `app.py`. It should execute only the selected page through the native `.run()` mechanism, without importing or executing the AI script when the Registry page is selected.

Use sidebar navigation initially to minimize interference with the current main-content layout and sticky toolbar. Avoid adding a duplicate global page heading above the existing AI heading. Page branding can be changed later as a small, separately validated task.

The router should not initialize AI business DataFrames, list saved projects, or load AI configuration merely to render the Registry home page. Registry can initially be a clearly labeled page skeleton without database queries or fabricated records.

### Why This Is the Lowest-Risk Starting Point

- The existing AI script stays in its current location.
- Its internal execution order remains intact.
- Existing imports, parser behavior, JSON persistence, Grid editing, and export behavior remain unchanged initially.
- The old startup path remains available as a fallback.
- The target single-service architecture is established using the installed native navigation mechanism.
- No custom script runner or broad function-scope rewrite is needed.

This recommendation is about the safest initial structure. It is not a claim that unrestricted page switching is safe without additional work.

### Recommended: Two Acceptance Boundaries

1. **Routing skeleton:** Prove that Registry is the default page and the inherited script runs as AI Workspace. Do not consider this a complete daily-use migration.
2. **Workspace compatibility:** Implement and verify protected departure, upload-context policy, editing synchronization, and keyboard shortcut scoping before accepting normal use with active AI work.

The final workflow should be:

```text
AI Workspace
→ Explicit data conversion and validation
→ Registry Draft
→ Human review
→ Publication
```

That integration is outside the initial navigation task. AI confidence and mapping quality flags must not substitute for approval.

## 6. Proposed Directory Structure

### Recommended: First-Phase Structure

```text
streamlit_app.py                 # New 3.0 entrypoint and navigation.
app_pages/
    mapping_registry.py         # New Registry home-page skeleton.

app.py                          # Existing AI Workspace, retained in place.
parsers/                        # Unchanged.
mapping/                        # Unchanged.
models/                         # Unchanged.
services/                       # Unchanged.
exporters/                      # Unchanged.
ui/                             # Unchanged.
db/                             # Unchanged.
docs/                           # Existing documentation.
```

`app_pages/` is an explicit page organization convention, not a legacy auto-discovery directory. No wrapper file is initially required for the AI Workspace because `st.Page` can point to the existing script.

Future page separation, service extraction, and Registry persistence should follow in approved small tasks. There is no need to create the full target architecture in this step.

## 7. Files That Would Need Modification

All actions in this section are proposals, not changes performed by the analysis.

| File | Proposed action | Purpose and scope |
|---|---|---|
| `streamlit_app.py` | Create in the first routing task. | Configure the outer app, register pages, select Registry by default, and run the selected page. |
| `app_pages/mapping_registry.py` | Create in the first routing task. | Render an honest Registry entry skeleton without connecting to the database or displaying invented implementation results. |
| `app.py` | Leave unchanged for the initial routing proof; make narrowly scoped changes in a subsequent compatibility task. | Later support protected departure, upload/state handling, and page-scoped keyboard behavior. |
| `docs/PROJECT_STATE.md` | Update only in a separately approved documentation task after validation. | Record actual implementation and verification results. |

The following files do not need changes merely to establish the entrypoint:

- Parsers and field extraction modules.
- AI service and mapping-row construction module.
- `models/interface_package.py`.
- `services/project_service.py`.
- `ui/mapping_grid.py`.
- Excel exporter.
- Shared database module and connection diagnostic.

Do not rename all existing state keys, move the large script, change persistence formats, or upgrade dependencies as part of the initial routing task.

## 8. Compatibility Risks

These are source-supported risks and future acceptance conditions. No navigation prototype or runtime test was executed.

| Risk | Severity | Evidence | Recommended control |
|---|---|---|---|
| Upload state disappears and returning resets mapping results. | High | Page-specific widgets can be cleaned up; signature changes near `app.py:3744` call `reset_data()`. | Define upload-context preservation or an explicit save/departure policy. Verify populated-workspace round trips before normal use. |
| The active Grid cell is not synchronized before navigation. | High | Current actions are deliberately deferred until after editor output has been copied into session state. | Treat departure as a request processed after synchronization; test immediate navigation while editing. |
| Existing unsaved-change guards do not intercept page navigation. | High | Current action constants cover project replacement/deletion and regeneration, not navigation. | Extend the action/guard flow in a separate compatibility task; native menu selection alone is not proof of protection. |
| Ctrl+S remains active on Registry. | Medium | Parent-document listener searches for an enabled button named `Save` and uses a persistent installation marker. | Scope or remove the listener on departure; verify it cannot trigger a Registry save unexpectedly. |
| Session-state key collisions. | Medium | AI keys such as `project_name` and `mapping_df` are not namespaced. | Prefix new Registry and navigation keys; avoid global clearing. |
| New and old page configuration or headings overlap. | Low | Both router and AI page may configure the page; AI body still renders its own title. | Use version-supported additive configuration and avoid duplicate outer headings. Change old branding separately. |
| Project storage location changes. | Medium | `PROJECTS_DIR` is relative to the process working directory. | Keep both launch commands rooted in the project directory; verify saved-project visibility using synthetic projects. |
| Refresh, direct URL access, or a new tab loses in-memory work. | Medium | Session state is temporary; URL-based access may create a new session. | Distinguish same-session navigation from durable persistence, and require explicit saving where appropriate. |
| Project JSON is mistaken for a complete upload-context backup. | Medium | Snapshots omit uploaded binaries, and restore explicitly clears upload widgets. | Do not use save/reload as an undocumented workaround for navigation state. |
| Native pages are assumed to share Python globals. | Medium | File pages execute in their own namespace. | Place future shared helpers in modules; share deliberate per-user values through session state. |

### Risk Assessment: Acceptance Gate

It is reasonable to establish a routing skeleton before modifying the AI script. However, a populated AI Workspace must not be considered compatible until switching away and returning has been tested for uploads, mapping data, unsaved edits, pending actions, and shortcuts.

Simply copying ordinary session keys or setting a generic persistence flag is not an established solution for upload widgets or third-party Grid editing. The exact compatibility implementation should be scoped after the initial routing proof and approved before modification.

## 9. First Small Implementation Task

### Recommended Task

**Step 11.9.1 — Add the Registry default entrypoint and register the existing AI Workspace.**

Proposed file scope:

1. Create `streamlit_app.py`.
2. Create `app_pages/mapping_registry.py` and its required directory.

Leave the existing `app.py` and all supporting modules unchanged.

### Proposed Acceptance Criteria

- Fresh access opens Mapping Registry by default.
- Registry is explicitly identified as an entry skeleton; it does not imply that CRUD, Search, or database-backed records already exist.
- Selecting AI Workspace executes the existing `app.py` as a native file page.
- Registry rendering does not invoke AI analysis, JSON project operations, or database queries.
- Existing standalone startup remains available.
- Empty-workspace navigation works without exceptions or obvious state contamination.

This first task proves routing feasibility only. A separate next task must implement and validate protected departure and workspace-state compatibility before unrestricted use with active AI work.

No AI generation call is necessary for the routing proof. Full AI regression testing may be separately authorized later.

## 10. Manual Testing and Rollback Plan

The commands and checks below are a future plan. They were not executed during the analysis or report preparation.

### Proposed Launch Command

From the project root, using the project's virtual environment:

```powershell
.\.venv\Scripts\streamlit.exe run streamlit_app.py
```

Expected initial behavior: one Streamlit application opens Mapping Registry as the default page, with AI Workspace available through navigation.

### Proposed Manual Checks

Use synthetic files and disposable local test projects. Do not use real customer data. The populated-workspace checks are acceptance gates for the compatibility task, not claims that the routing skeleton alone will pass them.

| Check | Expected result |
|---|---|
| Open the new entrypoint in a fresh session. | Registry opens by default without requiring an AI request or database connection. |
| Select AI Workspace. | Existing Project controls, upload areas, business sections, and export controls render. |
| Switch between empty workspaces. | No exceptions, duplicate-widget errors, or unintended state clearing. |
| Upload synthetic files, switch away, and return. | Upload and mapping behavior follows the agreed preservation/departure policy; silent result reset is a failure. |
| Edit a Grid cell and immediately request navigation. | The latest edit is synchronized and protected, or departure is explicitly prevented; silent loss is a failure. |
| Cancel a departure request. | The current workspace remains intact and usable. |
| Save before departure. | The latest editable values are persisted before the selected follow-up action; upload limitations remain explicit. |
| Save and load a synthetic JSON project. | Interface information, both transmission sections, mappings, return values, and conflicts restore consistently. |
| Press Ctrl+S in AI Workspace. | Behavior matches the intended AI Save action and commits active editor values. |
| Press Ctrl+S in Registry after visiting AI Workspace. | No unintended AI or Registry save is triggered by a stale listener. |
| Filter the Grid, edit a visible row, and export. | Non-visible rows remain in the full dataset and exported content. |
| Export English and Korean workbooks. | Existing data and workbook formatting remain consistent. |
| Return to the original startup path. | The inherited workspace remains independently usable. |

If AI generation regression is later authorized, verify the existing parsing, enrichment, batched mapping, review rules, and return-value analysis separately. Do not infer that they passed from successful page rendering.

### Proposed Rollback

If the new entrypoint fails acceptance:

1. Save any work that can be safely saved under the current workflow.
2. Stop the new Streamlit entrypoint.
3. From the same project root, start the existing entrypoint:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Because the proposed first task leaves the existing script and data services unchanged, functional fallback does not require a database rollback. No file deletion or Git reset is required merely to use the old entrypoint.

New and old server instances or browser sessions must not be assumed to share in-memory session state. Save work explicitly before changing startup paths where possible.

### Final Review Status

The recommended direction is a new lightweight native router with Registry as the default page and the existing script retained as AI Workspace. No migration of the large script is required for the initial entrypoint. Upload state, unsaved edits, pending actions, and keyboard scope remain explicit compatibility gates before normal multipage use.

All implementation, testing, and rollback actions in this document remain proposals requiring subsequent authorization. No actual refactoring has been performed.
