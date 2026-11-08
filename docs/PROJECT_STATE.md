# Interface Mapping Assistant 3.0 - Project State

Last Updated: 2026-11-09

## 1. Current status and evidence boundary

Phase one, actual-state reconciliation and core business relationship design closure, is complete within the confirmed scope. Module order: UI001 + UI005 -> UI002 -> UI004 -> UI003. Internal-standard creation-service work remains deferred. Full authentication, services and pages are later implementation, not phase-one blockers.

Customer creation and six internal-standard structures exist. CustomerInterface has a six-field ORM model, seven offline checks, explicit Alembic registration and prepared migration 4b8e2f6a91d3. **customer_interfaces has not been created in the inspected local database. Do not apply this migration unchanged: its default-locale lower(interface_code) uniqueness has an observed Unicode gap.**

Evidence categories below separate historical reports, earlier actual read-only inspections, today's offline closeout checks, and future work. No database connection, experiment, migration, application execution or dependency installation occurred during this Git closeout. Credentials, customer business data, workspace JSON and Chinese development logs are excluded. The user explicitly authorized the closeout Commit and ordinary Push; actual hash/result will be reported in chat without a follow-up commit to insert the hash here.

## 2. Actual database state verified earlier on 2026-11-09

These are the completed read-only inspections from earlier tasks, not rerun in this closeout. Transactions were explicitly read-only, rolled back, connections closed and pools disposed. Queries inspected catalogs, alembic_version and anonymous expressions, not customer business rows. No temporary objects, DDL/DML or sequence-changing calls were used.

- Local PoC: interface_mapping_management, role mapping_app, PostgreSQL 17.11, UTF8, schema public, search_path "$user", public.
- Applied revision: exactly c93a7d125e60. Current source chain: base -> 7f6ed0bcb03c -> c93a7d125e60 -> 4b8e2f6a91d3, one source head. Source head does not imply applied revision.
- Schema USAGE/CREATE, Customer REFERENCES and version-table UPDATE prerequisites were present. Customer and alembic_version were owned by mapping_app. No proposed customer-interface table/index/constraint/Identity-sequence name collision was found. Recheck before any eventual schema change.

| Existing business table | Model | Structural evidence |
| --- | --- | --- |
| customers | models/customer.py | Revision 7f6ed0bcb03c; 10 columns, PK, UQ, 4 Checks, country index. |
| systems | models/system.py | Revision c93a7d125e60; 7 columns, PK, UQ, 3 Checks. |
| standard_interfaces | models/standard_interface.py | Same revision; 9 columns, PK, UQ, 2 system FKs, 4 Checks, 2 lookup indexes. |
| standard_interface_versions | models/standard_interface_version.py | Same revision; 12 columns, PK, interface/version UQ, FK, 4 Checks. |
| standard_mapping_records | models/standard_mapping_record.py | Same revision; 10 columns, PK, 2 version UQs, FK, 3 Checks. |
| standard_mapping_fields | models/standard_mapping_field.py | Same revision; 16 columns, PK, record/side/order UQ, FK, 4 Checks. |
| standard_mapping_rules | models/standard_mapping_rule.py | Same revision; 9 columns, PK, record/order UQ, FK, 3 Checks. |

The seven tables matched current model and migration definitions: 73 columns/types/lengths/nullability, Identity presence/mode, defaults, 7 PKs, 8 UQs, 6 RESTRICT FKs, 25 Check expressions and 3 explicit indexes. Check deparsing casts/IN-to-ANY rewrites were semantically reviewed. No user-defined triggers or invalid/unready indexes were found. Applied migration definitions were reconstructed in memory for comparison without executing them against the database. This is structural verification, not current data-quality, rejection, concurrency, seed-content or ORM-onupdate behavior testing.

## 3. Implemented source and persistence boundaries

- db/base.py supplies shared Base and constraint naming. db/database.py supplies Engine/SessionLocal (autoflush=False, expire_on_commit=False). Customer creation service validates and add/flushes in a caller-owned Session; Registry submission owns commit/rollback/close. Returning an ORM object does not prove commit success.
- Customer customer_code uses the existing ASCII-uppercase rules; that is a different identifier from Unicode customer-interface codes. Customer names may repeat; country validation checks format only. No current requirement justifies rewriting the existing Customer or shared standard tables.
- streamlit_app.py and app.py provide Registry/AI navigation and scoped unsaved-work protection. services/project_service.py saves AI Workspace JSON files; this is not database-backed customer Mapping.
- models/customer_interface.py uses the shared Base and exactly customer_interface_id, customer_id, interface_code, interface_name, created_at, updated_at. BIGINT Identity, NOT NULL customer FK/RESTRICT and lookup index, VARCHAR(100)/VARCHAR(200), two nonblank Checks, TIMESTAMPTZ/default now()/ORM updated_at onupdate, global unique lower-code expression index. No name UQ, status, purpose, routes, user FK or audit columns.
- alembic/env.py registers CustomerInterface and all required existing models. Prepared revision: alembic/versions/4b8e2f6a91d3_create_customer_interfaces.py, down_revision c93a7d125e60. Upgrade contains only the new table/constraints/two indexes plus normal version bookkeeping. Downgrade removes its indexes then table. No timestamp trigger is defined.
- Customer-interface services, route/node models, customer Mapping/member/transformation/history storage, role enforcement and account/session revocation remain unimplemented. Trimming, ACTIVE-customer eligibility and permissions are not provided by the model's FK or Checks. Existing standard publication-state Checks do not implement freezing, version allocation or copying.

## 4. Confirmed core business rules and design

Authority is the user's explicit confirmations, not draft labels. See docs/architecture/CUSTOMER_INTERFACE_DESIGN.md for detailed recommendations.

- Customer -> Customer Interface -> Route. Interfaces can register/save independently with zero routes; one interface may later own multiple routes. Route owns Nodes and Mappings; Mapping Members belong to a Mapping and a node on the same Route. Recommend composite route_id/mapping_id and route_id/node_id FKs with parent UQs to prevent cross-route references.
- Route names are case-insensitively unique within an interface; different interfaces may share names. JSON field paths such as item[].sku are unrelated labels and have no global UQ.
- Per PoC route, each internal system occurs at most once and Customer occurs at most once. Branches are independent routes with isolated Mapping. Recommend a separate CUSTOMER node kind with NULL system_id, versus SYSTEM nodes referencing systems; do not add a CUSTOMER system seed.
- Renaming preserves route ID and Mapping ownership. Node/direction changes check Mapping impact; conflicts reject the entire save, retaining the draft without silent deletion/reassignment/semantic changes. Detailed conflict tests are technical recommendations, including referenced-node changes, invalidated conversion dependencies and stale revisions.
- Interface code: required, trimmed, <=100 characters, original case/Unicode/common symbols retained; globally case-insensitive unique. Name: required, trimmed, Unicode, <=200 characters and repeatable. Only interface-name maintenance is in scope; no code editing, customer reassignment, deletion or status/purpose expansion.
- Customer Mapping requires a registered interface owned by its customer and a route within it. Only concrete internal-interface references may be NULL; PoC maintains system nodes/order/direction. Customer Mapping is private, separate from shared standard details; optional future provenance may reference an explicit standard version without allowing customer edits to overwrite standards.
- Inactive business customers remain queryable by authorized active accounts, but block new interfaces, interface-name edits, Mapping additions/changes and Route/Flow changes. Inactive accounts cannot log in or continue any business query/write through existing sessions. ADMIN maintains business data; active USER is business-read-only.
- UI001 Mapping must show last modifier and actor/time/record/field/before/after history. Trusted identity and atomic history persistence are later physical-design dependencies, not optional requirements. Interface/other master-data full-history scope remains separately pending. Do not invent user FKs or treat timestamps as full audit.
- Route/node/Mapping deletion, customer copying, SSO, self-registration and approval/publication are not authorized in this stage.

Formal UI001 V04/UI005 V03 files remain missing locally; no formal-file synchronization is claimed. No independent Claude Code conclusions have been received or adopted. Missing formal-file traceability and that review are disclosed limits, not invented approvals or blockers to the explicitly confirmed relationship closure.

## 5. Unicode findings and migration gate

Completed earlier read-only observations, not rerun during closeout:

- Database LC_COLLATE/LC_CTYPE: Korean_Korea.949, libc provider; default collation deterministic. Database collation-version fields returned NULL. Current code/index has no explicit COLLATE and would inherit this environment.
- Default lower merges observed ASCII and mixed Korean/API case, but misses sharp S/capital sharp S (U+00DF/U+1E9E). Capital/ordinary sigma matches; final/ordinary sigma does not. Turkish dotted/dotless I boundaries were recorded. These expressions do not redefine business equivalence.
- Catalog found 784 ICU collations and no existing nondeterministic collation. Existing deterministic pg_catalog.und-x-icu stored/actual version 153.14 matched. Explicit ICU lower merges sharp-S capitalization and accented case, but still does not merge final/ordinary sigma. It preserves tested sharp-S/SS, accent, fullwidth/ASCII, composed/decomposed and slash/hyphen distinctions. Dotted-I lower becomes i plus combining dot, distinct from i.
- Preferred candidate: dedicated index-local ICU nondeterministic case-insensitive/accent-sensitive root comparison, und-u-ks-level2, preserving original display text and deterministic column Checks. This is an unvalidated recommendation. Added normalization/width/punctuation/expansion equivalences require explicit assessment; only acceptance-changing ambiguous business outcomes need user decisions.
- **Candidate-collation isolated creation/rollback experiment: pending, never executed.** Only existing-collation SELECT expressions have actual results. No candidate collation, real unique-index duplicate rejection or concurrency validation exists. Do not replace the gap with an unverified claim about citext or Python casefold.

## 6. Historical verification retained

These scoped reports are historical; the closeout does not rerun them. Local Git version baed0ef:docs/PROJECT_STATE.md (dated 2026-11-02) and the earlier 2026-11-04 snapshot read in this conversation provide provenance; original standalone execution logs were not located.

- User reported shared Engine/SessionLocal connectivity and startup/default Registry/basic navigation on 2026-10-25; limited empty-workspace/Remark/departure/save behavior on 2026-10-31. AI save feedback was not database customer-Mapping evidence.
- Customer migration/structure and 22 rollback-only database cases, ORM onupdate/raw-SQL distinction, 96 offline service checks and rollback-only integration were reported passing. Failure SAVEPOINT recovery and exact cleanup were checked; no test commits or sequence resets. Page reports recorded 15 stub cases plus AppTest with database substitutes. Later user feedback confirmed one page-created record externally; no customer identifiers are reproduced. Duplicate-code manual acceptance had no explicit result.
- Six-standard-table migration/structure/offline checks and separate rollback-only behavior rounds were reported. Initial 18 normal/35 rejection cases preceded a test assertion failure over overlapping Checks; targeted diagnosis and supplemental 89 rejection/2 normal plus 3 rejection/3 recovery publication-time cases passed. This was not one uninterrupted suite and did not implement standard business submission, allocation/copying/freezing.
- CustomerInterface model task recorded 7 passed in 0.76s after pytest default capture initially failed before collection because the read-only sandbox lacked writable temporary files. sys capture resolved it without installation. Migration preparation reran 7 checks in 0.54s and guarded offline registration/upgrade/downgrade comparisons passed. No customer-interface database migration was executed.
- Earlier saved-state regression from a newer snapshot to 2026-10-24 was reconciled using source/history; cause remains unknown. Downloads copies were not merged or overwritten. Main progress file is the AGENTS-designated docs/PROJECT_STATE.md.

Unverified: actual interface migration execution/rollback, unique-index and concurrent behavior, candidate Unicode equivalences, database timestamp behavior for the new model, real Customer commit-failure/concurrent/cross-tab paths, full AI upload/Grid/shortcut/navigation regression, standard downgrade/business submission and original test artifacts. Complete login/services/pages are not phase-one blockers.

## 7. Git closeout checks - 2026-11-09

This task modifies only this progress document. Existing related source/design files are included as saved, without further development. Initial branch main, upstream origin/main; initial index empty. Remote fetch/push target was verified as github.com/jasminemuyuxi/Interface-Mapping-Assistant-3.0 with no credential-bearing URL displayed. Related six standard models and c93a7d125e60 migration must accompany their registration imports; they are not omitted as unrelated dependencies. No Chinese development log is created/edited/staged.

Actual offline checks, exit 0:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.\.venv\Scripts\python.exe -B -m pytest -q --capture=sys -p no:cacheprovider tests/test_customer_interface_metadata.py
.\.venv\Scripts\python.exe -B -m alembic heads
.\.venv\Scripts\python.exe -B -m alembic history
```

Result: 7 passed in 0.56s; one head 4b8e2f6a91d3, complete three-revision chain. An additional stdin-only guarded offline audit compiled all eight registered model tables/indexes, resolved FKs/configured mappers, parsed Python syntax, generated only incremental customer-interface upgrade/downgrade SQL in memory, and checked scope. db.database/dotenv/driver imports and Engine connections were blocked; audit exit 0. No database experiments were run. Formatting/staged-file review precedes Commit. These checks do not establish actual database behavior or resolve the known Unicode issue. Commit/Push outcome is reported after execution in chat, not assumed here.

## 8. Next single execution step and limits

Subject to separate explicit DDL authorization, perform exactly one isolated candidate-collation experiment: verify validation schema/name ownership; create a dedicated nondeterministic ICU root candidate in one transaction, run the anonymous case/accent/width/normalization/symbol comparison matrix, then roll back all validation objects. No application table/index creation, migrations or business rows. Do not drop/reuse unknown objects. Actual uniqueness/concurrency tests remain later work. The next experiment is pending; stop after this Git closeout.

Keep 3.0 independent from 2.0 and local PoC only. Never expose secrets or use sensitive customer test data. No production/cloud scope, table deletion/clearing/reset or Git force/history rewriting is authorized. Necessary early structural corrections may use later authorized model changes and new incremental migrations, retaining applied history with explicit preservation/backfill/collision/recovery plans. Preserve unrelated work. Technical documentation is English; user explanations are Chinese. Full core design is docs/architecture/CUSTOMER_INTERFACE_DESIGN.md; historical reviews are docs/architecture/PROJECT_STRUCTURE_REVIEW.md and STREAMLIT_PAGE_ARCHITECTURE_REVIEW.md. Existing design documents are not modified by this closeout.
