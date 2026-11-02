# Interface Mapping Assistant 3.0 — Project State

Last Updated: 2026-11-02

## 1. Project Context and Stack

- Independent 3.0 internal logistics IT PoC; keep separate from Interface Mapping Assistant 2.0.
- Local Windows + VS Code environment with a project Python virtual environment.
- Stack: Python, Streamlit + AG Grid, PostgreSQL, SQLAlchemy, Alembic, Psycopg, Anthropic Claude API; Git/GitHub and DBeaver support development.
- Verified target in the reported 2026-10-31 database inspection: PostgreSQL 17.11, UTF8, database `interface_mapping_management`, application role `mapping_app`, schema `public`.

## 2. Current Priority and Design Decisions

- Prioritize Mapping Registry. Further AI Workspace improvements are deferred.
- Current phase: implement master data, interface definitions, and segment mappings in batches; save and query one OMS → WMS internal standard using anonymous sample data.
- Maintain internal standards by segment: initially EDI—OMS and OMS—WMS. The structure must support future OMS—TMS segments and branching interface chains.
- Manage interface definitions, interface relationships, and field mappings. Actual interface execution, scheduling, and runtime monitoring are outside scope.
- Separate corrections to shared standards from customer-specific adjustments.
- Customer configurations reference explicit standard versions; standard upgrades must not automatically overwrite customer configurations.
- Multiple customer interfaces may reuse the same EDI interface and fields, while maintaining their own data scopes and trigger conditions.
- Preserve original interface identifiers as documented, including cross-system interface identifiers. Do not invent separate sender/receiver identifiers when they are not provided. Manage transmission information for both sides at the version level.
- Detailed structures for all tables are not finalized. The Customer model is implemented; subsequent table designs remain open.

## 3. Confirmed Customer Model

- One customer profile represents one business country or region; `country_code` is stored directly in `customers`.
- English name is required; local-language name is optional. Names are not restricted to ASCII.
- Customer names may repeat; `customer_code` is unique. Contracting entity names are not unique.
- Do not add customer-country association, business-scope, or project tables at this stage.
- Future customer copying will create independent drafts of customer-specific interfaces and mappings. Shared standards remain reused through explicit version references. Customer copying is not implemented.
- Exact fields and constraints are defined by `models/customer.py`. The country code check validates format only, not actual country-code membership.
- The single-customer creation service trims optional text and converts blank input to NULL; its verification scope is recorded in Section 6.

## 4. Historical Setup and Database Runtime Verification

The following records are retained from earlier development; they are not current database inspection results.

- Independent repository, Python virtual environment, and application dependencies were prepared; the existing Streamlit application was launched successfully.
- PostgreSQL and DBeaver connectivity, database and application-role creation, application-role login, and public-schema CREATE permission were historically verified.
- `.env` was recorded as ignored by Git and untracked; this was not rechecked in this documentation update.
- Steps 10.14 and 10.15: the user confirmed shared Engine and SessionLocal connectivity on 2026-10-25 using `python db_connection_test.py`. The test used `SELECT current_database(), current_user` and reported the expected database and role. Codex did not rerun it during this update.
- Steps 11.9.1–11.9.4: the user manually verified startup with `python -m streamlit run streamlit_app.py`, Registry as the default page, and basic navigation on 2026-10-25. These checks covered the navigation foundation only.

## 5. User Manual Verification — 2026-10-31

These results were supplied by the user in conversation; they were not independently executed by Codex.

- Bidirectional Registry ↔ AI Workspace navigation worked with an empty workspace.
- Returning from an empty workspace required no confirmation and caused no error, blank page, or repeated navigation.
- An unsaved Remark produced the departure warning and Continue / Cancel controls.
- Cancel retained the workspace and Remark and removed the confirmation prompt.
- Continue opened Registry successfully.
- Reopening AI Workspace caused no unexpected navigation or stale confirmation; the Remark remained in this particular test.
- Leaving again required confirmation; the previous Continue approval was not reused.
- The user subsequently confirmed that saving the Mapping succeeded.

These are limited scenario results, not complete workspace-state preservation or overall acceptance. They do not establish database-backed persistence.

The controlled navigation implementation in `streamlit_app.py` and `app.py` uses requested/confirm/one-time-approved states. It supersedes the earlier one-way navigation restriction. Confirmation does not automatically save data or guarantee restoration after departure.

No passing results were supplied in this round for uploaded files, conflicting operations, AG Grid final-cell synchronization, filtered-row completeness, standalone `app.py` startup, or Ctrl+S behavior. These remain pending. Uploaded-file restoration, automatic saving, browser-level departure protection, and cross-session recovery are not implemented by the navigation changes. Further AI Workspace work is currently deferred.

## 6. Customer Database Implementation and Verification — 2026-10-31

The results below are recorded from local Codex execution reports supplied by the user. They were not rerun during this documentation update. Earlier source reviews covered Base, database configuration, Customer, and Alembic. This update inspected `services/customer_service.py` and `models/customer.py` and found no discrepancy with the reports. Offline checks, database runtime tests, and user manual checks are separate evidence.

### ORM and Offline Verification

- `db/base.py` defines the unified SQLAlchemy 2.x `DeclarativeBase` and naming conventions for indexes, unique constraints, checks, foreign keys, and primary keys. Check constraints require explicit semantic names.
- Import and in-memory metadata checks passed. Metadata was empty when Base was imported without model registration.
- The module does not import `db.database`, load `.env`, or connect to the database.
- `models/customer.py` defines the typed Customer ORM model using the shared Base, without changing `models/interface_package.py` or the empty `models/__init__.py`.
- Offline checks of field types, nullability, Identity, defaults, constraints, indexes, and PostgreSQL SQL compilation passed.

### Alembic and Initial Migration

- Alembic is initialized. `target_metadata` uses `db.base.Base.metadata`; `models.customer` is explicitly imported to register Customer.
- Offline mode uses a credential-free `postgresql+psycopg` dialect configuration without importing `db.database`, loading `.env`, or opening a connection.
- Online mode imports and reuses the shared Engine inside the online migration function; this path has now executed successfully.
- No real connection string or credentials are stored in `alembic.ini`; no connection URL or sensitive-parameter logging is configured.
- Initial revision `7f6ed0bcb03c` in `alembic/versions/7f6ed0bcb03c_create_customers_table.py` has `down_revision = None` and was generated without autogenerate, then manually implemented.
- History and heads checks confirmed one initial revision and one head. Offline upgrade SQL matched the Customer model's fields, constraints, and index; checks exited with code 0. Alembic version-management SQL was distinguished from customer-table SQL.
- Offline environment verification confirmed that `env.py` actually passed shared Base metadata containing `customers`, without importing `db.database` or `dotenv`.

### Database Inspection and Applied Structure

- Shared-Engine inspection confirmed PostgreSQL 17.11, UTF8, database `interface_mapping_management`, role `mapping_app`, and `public` as the actual default target schema with USAGE and CREATE privileges.
- The initial inspection found no non-system ordinary or partitioned tables and no `customers`, `alembic_version`, or other same-name relation objects. Inspection used a read-only transaction, which was rolled back before releasing the connection.
- Migration prerequisites were rechecked before application. `.\.venv\Scripts\python.exe -B -m alembic upgrade 7f6ed0bcb03c` exited with code 0.
- Read-only post-migration checks confirmed `public.customers`, `public.alembic_version`, and recorded version `7f6ed0bcb03c`.
- All ten customer columns, types, nullability, Identity, database defaults, primary key, unique constraint, four Check constraints, and the `country_code` index matched the migration. The Identity sequence and constraint-backed indexes were present; no user-defined triggers existed.
- Post-migration inspection transactions were rolled back and connections released. Structure verification is distinct from the data-behavior tests below.

### Database Behavior Tests

- The execution report records 22 passing cases and exit code 0, using anonymous records only.
- Successful cases covered Identity generation, default ACTIVE status, timezone-aware timestamp defaults, optional NULL fields, Chinese/Korean Unicode round trips, duplicate names with different customer codes, and explicit INACTIVE status.
- Actual rejected inserts verified unique, NOT NULL, all four Check constraints, and VARCHAR length limits. SQLSTATE and applicable constraint names were checked: 23505 (unique), 23502 (NOT NULL), 23514 (Check), and 22001 (length).
- All tests used one outer transaction, with independent SAVEPOINTs for expected failures and no commit. After outer rollback, a new read-only transaction found zero remaining records using exact test identifiers; resources were released.

### ORM updated_at Behavior

- A Session bound to a shared-Engine Connection used `join_transaction_mode="create_savepoint"` within an outer transaction.
- After ORM insertion, flush, and refresh, changing only `remark` caused the captured ORM UPDATE to include `updated_at=now()` automatically. Test code did not explicitly assign `updated_at`; `created_at` remained unchanged.
- Raw SQL changed only `remark` and did not invoke ORM onupdate. This conclusion combined the actual UPDATE SQL, refreshed values, and the confirmed absence of user-defined triggers. An earlier comparison timestamp was returned as an auxiliary baseline without changing stored timestamps.
- PostgreSQL `now()` returns the transaction start time. Equal insertion and update timestamps within one transaction were not treated as an update failure or used alone as proof of success.
- The test exited with code 0. The Session was closed, the outer transaction rolled back, the temporary SQL listener removed, and resources released. A new read-only transaction found zero records for the exact random customer code.
- Rollback does not restore Identity sequence numbers. Tests consumed sequence values and did not reset the sequence or require consecutive IDs.

### Single-Customer Creation Service

- `services/customer_service.py` implements `create_customer(session, ...)`: validate and normalize all inputs, construct Customer, add/flush, and return the ORM object. Returning does not mean commit succeeded; flush may include other pending Session objects.
- Customer and country codes are trimmed and only ASCII lowercase letters are converted to uppercase. Unicode names and internal spaces are preserved; optional blank text becomes None. Omitted status is explicitly written as ACTIVE by the service; explicit status values are strictly validated.
- The service performs no duplicate lookup, creates no Session or SAVEPOINT, and does not commit, roll back, or close the caller's Session. The caller owns transaction completion and recovery after flush failure.
- Safe exceptions distinguish input errors, duplicate customer codes, and other persistence errors. Duplicate classification requires IntegrityError and all matching structured diagnostics: SQLSTATE 23505, schema public, table customers, constraint uq_customers_customer_code. Missing or different diagnostics are persistence errors.
- Error messages exclude raw input, SQL, parameters, and connection details. `raise ... from None` suppresses displayed exception chaining; it does not remove the original exception object entirely.

### Service Offline Checks

- The execution report records 96 passing offline stub checks and exit code 0, covering input normalization and validation, exception classification, import isolation, and Session boundaries.
- The module did not import `db.database`, dotenv, or Streamlit. Stub checks verified invalid inputs failed before object construction/add/flush and only add/flush were used for valid persistence attempts.
- These are offline stub results, not evidence of real database writes, real driver diagnostics, or transaction recovery.

### Service Rollback-Only Database Integration

- The execution report records passing integration tests and exit code 0, using the shared Engine Connection, an outer transaction, and `Session(join_transaction_mode="create_savepoint")` with anonymous records only.
- Actual inserts and refresh verified code normalization, Unicode and internal-space preservation, optional blanks becoming NULL, same-name customers with different codes, explicit INACTIVE, Identity generation, and timezone-aware timestamps.
- Omitted status produced ACTIVE explicitly assigned by the service; this did not revalidate the database status default.
- A duplicate normalized code raised DuplicateCustomerCodeError with the fixed safe message. Real driver diagnostics matched 23505 / public / customers / uq_customers_customer_code.
- Before creating the failure SAVEPOINT, the Session had no pending writes. The caller rolled back that failed SAVEPOINT, not the entire Session transaction; the same Session then inserted another valid customer, and the outer transaction remained active.
- An input validation failure did not invalidate the Session; a subsequent valid insertion succeeded in the same Session.
- Temporary monitoring detected zero service calls to commit, rollback, close, begin, or begin_nested; monitoring patches were restored.
- No commit occurred. After closing the Session and rolling back the outer transaction, a new read-only transaction checked the exact set of five random customer codes and found zero remaining records. The verification transaction was rolled back and resources released.
- Identity sequence values were consumed and were not reset. This integration round did not rerun every offline input case.

Customer database structure, the reported behavior cases, and rollback-only creation-service integration are verified within the stated scope. Actual commit success/failure handling, concurrent competition, other database faults, and Registry UI remain unverified. Database read/write services as a whole and the overall Mapping Registry are not complete.

### Customer Creation Page and Offline Checks

- `app_pages/mapping_registry.py` now provides the seven-field Create customer form, preserving existing planning text, AI Workspace guidance, and navigation. Inputs are retained after success or failure.
- Only form submission loads SessionLocal and creates a short-lived Session. The page owns commit, error rollback, and final close; only ordinary result values are retained after commit returns successfully.
- Safe messages cover validation, duplicate codes, persistence/configuration failures, uncertain commit outcomes, and cleanup failures. A known successful commit remains successful if cleanup fails; no automatic write retry is performed.
- Prior execution reports record 15 passing page-stub scenarios and passing Streamlit AppTest checks with database substitutes; both scripts exited with code 0. They covered fields/defaults, submit gating, retained inputs, old-result removal, non-writing reruns, error/cleanup paths, and success timing.
- These checks did not load real database configuration or connect to a database and were not rerun during this documentation/Git task. They are not actual commit or manual UI evidence.
- Manual UI, real commit, real database error handling, navigation regression, and cross-tab behavior remain unverified for the new page.

## 7. Outstanding Work

- The minimal Customer creation service and its input normalization are implemented, with offline and rollback-only integration verification recorded above. Actual commit success and commit-failure handling remain unverified.
- The Customer creation page is implemented and offline-checked, but manual UI, real commit, and real database error handling remain unverified. Concurrent competition and other database faults remain unverified. Customer list-query service is not implemented; other Customer operations are outside the completed scope.
- Finalize subsequent table designs and implement remaining ORM models, interface definitions/relationships, and segment Mapping functionality.
- Detailed auditing and import logs are deferred.
- AI Workspace scenarios listed in Section 5 remain pending; deeper improvements are deferred behind Registry work.

## 8. Next Single Execution Step

Start `streamlit_app.py` and manually inspect the seven-field Customer form without clicking Create customer.

This next step must not submit the form or write to the database. It has not been performed as part of this documentation/Git task.

## 9. Operating Rules and Constraints

- Local PoC only; do not introduce cloud deployment.
- Do not expose credentials or use real customer-sensitive sample data.
- The user explicitly authorized committing and pushing this development batch on 2026-11-02, superseding the earlier deferral. Future Git publication requires authorization within its task scope.
- Advance one executable step at a time; inspect current source and explain proposed changes before modification.
- Preserve existing functionality and keep changes small, modular, and limited to the approved scope.
- Use English for code comments, docstrings, and technical documentation.
- Record offline checks, database runtime verification, and user manual verification separately; do not treat configuration presence or historical results as current runtime proof.
- Obtain explicit approval before destructive database operations.
- This documentation/Git task updated only `docs/PROJECT_STATE.md` before committing the reviewed development files. It did not read `.env`, connect to a database, rerun tests, install dependencies, create models or revisions, execute migrations, or create tables.
