# Customer Interface and Route Core Design

Last Updated: 2026-11-09
Status: Phase-one actual-state reconciliation and core business relationship closure completed within the scope below. Unicode uniqueness implementation remains a pre-migration technical gate. No new ORM, tests, migration, or database objects were changed by this design update.

## 1. Evidence and authority

Read AGENTS.md, the current PROJECT_STATE.md, this design, and relevant model/migration source. Reuse the verified seven-table structural results and default-locale observations in PROJECT_STATE sections 8d/8e; do not rerun them. The additional read-only comparison experiment in section 7 is current evidence.

The user's latest instructions explicitly confirm the business rules below, including Mapping last-modifier/history requirements. Do not infer confirmation solely from historical draft labels. Formal UI001 V04/UI005 V03 files remain absent from the project search; neither file was edited or claimed synchronized. Missing documents do not block closure of these explicitly confirmed relationships. The available Codex review and recorded preflight are integrated; no second independent Claude Code review findings have been received or adopted. Independent-review synthesis is limited accordingly.

This document supersedes earlier open questions about route-name scope, repeated systems, branching and route-edit behavior. It also supersedes the earlier default-lower implementation recommendation as a deployment-ready choice. Historical implementation/test evidence remains in PROJECT_STATE.md.

Use **Route** for system flow (user-facing Chinese: 流转路线). A JSON field path such as item[] or item[].sku is a different concept. Do not use a field path as a route key or impose global uniqueness on field paths.

## 2. Confirmed business contract

- Customer -> Customer Interface -> Route. One customer owns many interfaces; one interface may independently register/save with zero routes, and later own multiple independent routes.
- Customer-field Mapping must belong to a registered interface owned by that customer, through its Route. This required ownership is never nullable. Different routes/interfaces keep separate Mapping even if they reuse internal standards.
- Route names are case-insensitively unique within the same customer interface; different interfaces may use the same name. Each route has a stable independent ID and a persisted readable name.
- Within one PoC route, each internal system occurs at most once, and the Customer node occurs at most once. Branches are recorded as separate routes with independent Mapping; no in-route branch or repeated-system loop is introduced.
- Route renaming is allowed with existing Mapping, preserving ID and ownership. Changes to nodes or direction require Mapping-impact checks; conflicts reject the whole save with a clear message. No silent deletion, reassignment, or semantic reinterpretation of Mapping.
- PoC selects Customer/EDI/OMS/WMS/TMS nodes and their order/direction. Concrete internal-interface references may be NULL; interface/customer/route ownership may not. Future system expansion is supported without hardcoded fixed system columns.
- interface_code is required, trimmed, at most 100 characters, preserves original case, permits Unicode/common symbols, and is globally case-insensitively unique. interface_name is required, trimmed, Unicode-capable, at most 200 characters and repeatable.
- Interface maintenance currently changes the name only. No code editing, customer reassignment, physical deletion, status or purpose expansion.
- Inactive business customers remain queryable by authorized active users. They cannot receive new interfaces, interface-name edits, new/modified Mapping or Flow/Route changes.
- Inactive user accounts cannot log in; existing sessions are invalidated and cannot continue business queries/additions/changes. Active USER is business-read-only; ADMIN maintains business data subject to customer-status restrictions. Personal profile/preferences require a separate allowed-field policy.
- Customer Mapping is private data, independent of shared standard details. Future provenance may reference an explicit standard version (and relevant detail IDs); customer edits never overwrite shared standards, and upgrades never silently replace customer Mapping.
- UI001 Mapping shows its last modifier and history containing actor, time, record, field, before and after values. These are confirmed, not optional questions. Complete history scope for interface/other master data is separately undecided.
- Route, node and Mapping deletion features are not authorized. Discussing FK actions does not introduce delete operations. SSO, self-registration, customer copying and approval/publication remain outside this stage.

## 3. Recommended core relational structure (technical design, not implemented)

| Entity | Ownership and recommended keys |
| --- | --- |
| customers | Reuse existing customer_id. |
| customer_interfaces | Existing six-column ORM and unapplied migration; customer_id NOT NULL FK to customers. Stable customer_interface_id. |
| customer_routes | Proposed route_id PK, customer_interface_id NOT NULL FK, required route_name; case-insensitive UQ index scoped to customer_interface_id. Names are labels, never FK targets. |
| customer_route_nodes | Proposed node_id PK, route_id NOT NULL FK, node_kind, nullable system_id, positive position; UQ(route_id, node_id), UQ(route_id, position). |
| customer_mapping_records | Proposed mapping_id PK, route_id NOT NULL FK; UQ(route_id, mapping_id). Each record represents one logical Mapping group within one route. |
| customer_mapping_members | Proposed member_id PK, route_id/mapping_id/node_id NOT NULL, field definition and local ordering. FK(route_id, mapping_id) -> records(route_id, mapping_id); FK(route_id, node_id) -> nodes(route_id, node_id). |
| Mapping transformations/history | Later physical design must express input/output member sets and conversion rules, plus confirmed modifier/change-history data. Do not pretend group membership alone fully defines conversion semantics. |

Composite parent UQs allow the member FKs to enforce that both its Mapping and its node belong to exactly the same route. A simple mapping_id FK plus a simple node_id FK would permit cross-route mistakes. No extra customer/interface IDs need be stored on every member: derive them through the required ownership chain. If a future table stores such redundant IDs, add corresponding composite ownership constraints rather than trusting UI filters.

Recommend RESTRICT for ownership FKs, without ORM cascade deletion. This is protective integrity, not delete authorization. Do not create production tables from this conceptual design until the physical-model step is authorized.

### Customer node versus internal System node

Recommend node_kind CUSTOMER or SYSTEM, with a Check: CUSTOMER implies system_id IS NULL; SYSTEM implies system_id IS NOT NULL with FK to existing systems. Add UQ(route_id, system_id) for internal-system non-repetition and a partial unique route_id index WHERE node_kind='CUSTOMER' for Customer-at-most-once. Customer identity is derived from the interface's customer, not a fabricated shared System row. Do not change systems seeds to add CUSTOMER.

Route order establishes direction; do not maintain a contradictory independent direction flag. Minimum node count and additional route lifecycle policies are technical proposals for a later detailed model, not silently confirmed here. Internal-interface references remain deferred and optional; their future endpoint/system consistency needs separate constraints. No forced standard-interface code is required to register an interface or configure PoC nodes.

### What one customer Mapping means

A Mapping record groups related fields across nodes of one route. Members identify exact node instances and their field names/JSON field paths/types. Several source fields may produce one target or vice versa; explicit input/output membership and transformation applicability are required to preserve that meaning. A horizontal page row is a presentation, not five fixed database system columns. Repeated field paths across routes/groups are valid; any local deduplication policy requires a separate justified scope.

Keep customer Mapping records/members/rules independent from standard_mapping_records/fields/rules. Optional future source references identify a specific standard_interface_version_id, never an unversioned live alias. Copy/adoption semantics and source associations are later implementation; recording provenance is permitted, not prohibited by isolation.

## 4. Recommended route-edit conflict rules

These are **technical recommendations** implementing the confirmed atomic-rejection behavior:

1. Lock/read the current route and revision in one transaction, then validate the proposed node set/order and current customer/user eligibility. Reject stale-revision edits rather than overwriting concurrent work.
2. A name-only change keeps route_id and all node/Mapping IDs; validate only scoped name uniqueness and ordinary eligibility/concurrency rules. Do not rebuild the route or renumber IDs.
3. Reject removal/retyping/system replacement of a node referenced by any Mapping member. Keep stable node IDs for unchanged nodes; never match old Mapping to a new node merely by position or label.
4. Reject changes that remove/reverse a directed conversion dependency, change relative order of mapped input/output nodes, or invalidate a rule's node/system/interface assumptions. Compare before/after ordered nodes and every affected transformation's endpoints. Until a Mapping format can prove such edits harmless, conservatively reject structural edits affecting a mapped portion of a route; no automatic semantic conversion.
5. Allow an unreferenced-node edit only if all Mapping member FKs, effective endpoint order and transformation assumptions remain valid and the route's system uniqueness rules still hold. Merely retaining all node IDs is insufficient proof.
6. Save route/name/node changes as one transaction; on any conflict roll back everything, retain the user's draft, and identify affected Mapping IDs/fields in safe messages. No silent delete, reparent, or reinterpretation. No route/node/Mapping delete UI or service is added.

## 5. Customer-interface physical baseline

| Field | Type | Nullable | Default/configuration |
| --- | --- | --- | --- |
| customer_interface_id | BIGINT | No | Identity PK |
| customer_id | BIGINT | No | customers.customer_id FK, ON DELETE RESTRICT; lookup index |
| interface_code | VARCHAR(100) | No | No default; nonblank Check; global case-insensitive index needs correction |
| interface_name | VARCHAR(200) | No | No default; nonblank Check; no uniqueness |
| created_at | TIMESTAMPTZ | No | server_default=now() |
| updated_at | TIMESTAMPTZ | No | server_default=now(); ORM onupdate=now() |

Implemented files: models/customer_interface.py and tests/test_customer_interface_metadata.py. Alembic registration: alembic/env.py. Unapplied revision: alembic/versions/4b8e2f6a91d3_create_customer_interfaces.py, down_revision c93a7d125e60. The original global lower(interface_code) expression index is implemented in source but blocked from application unchanged by section 7 evidence. ORM onupdate is not a database timestamp trigger, actor identity, or full audit.

Keep existing nonblank Check names and customer lookup index unless a justified later correction requires change. Services must trim, enforce ACTIVE customer status, permit name-only changes and own the validation contract; the FK enforces existence only. Recommend caller-owned short-lived Sessions: services add/flush; the caller commits/rolls back/closes. Lock customer status changes consistently with writes. No live Session in UI state, and no success indication before known commit success.

## 6. Permissions and audit dependencies

Server-side trusted active identity/session and role checks are required for both reads and writes, not just disabled page buttons. Customer inactivity and account inactivity have different query semantics as confirmed above. Missing full login/services/pages is not a phase-one design blocker.

Mapping must display the last modifier and retain actor/time/record/field/before/after history. Recommend stable Mapping/member identifiers, a trustworthy actor identifier with an appropriate display snapshot, and atomic business-write/history persistence. Do not rely solely on a mutable display name or client-supplied principal. Define representation of NULL, complex values and multi-field edits in later detailed audit design.

No authoritative user schema is present yet; do not invent user-table FKs. Physical audit/principal integration is a later dependency before writable release, not a reason to reopen the confirmed Mapping-history requirement. Interface and other master-data full-history scope remains separately pending. Six current interface fields do not satisfy full auditing.

## 7. Unicode comparison: actual candidate evidence and recommendation

Reused 2026-11-09 default-environment evidence: PostgreSQL 17.11/UTF8, applied c93a7d125e60, schema public, Korean_Korea.949 libc default. Current default lower misses U+1E9E capital sharp S versus U+00DF sharp S. Thus migration 4b8e2f6a91d3 must not be applied unchanged.

This task made one additional explicit read-only transaction using existing local PoC configuration, querying catalog candidates and anonymous SELECT expressions only. Transaction read_only=on; rolled back, connection closed and pool disposed. No business rows, temporary objects, collation/index creation, sequence changes or DDL. Credentials were internal only.

Catalog evidence: **no existing nondeterministic collation was found**. Existing pg_catalog.und-x-icu is deterministic, provider ICU, stored/actual version 153.14. It is available for explicit lower(value COLLATE "pg_catalog"."und-x-icu") expressions, not inherently case-insensitive raw equality.

| Pair | Equality after explicit ICU lower | Interpretation of observation |
| --- | --- | --- |
| ASCII mixed case | true | Sample case conversion succeeds. |
| Chinese identical code/symbols | true | Text retained. |
| Korean plus API/api and symbols | true | Mixed-script sample succeeds. |
| U+00C9 / U+00E9 | true | Accented case pair succeeds. |
| U+00DF / U+1E9E | true | Improves on the Windows default. |
| U+00DF / SS | false | No observed sharp-S expansion merge. |
| U+03A3 / U+03C3 | true | Capital sigma sample succeeds. |
| U+03C2 / U+03C3 | false | Lower is not complete case folding. |
| I / i | true | ASCII pair succeeds. |
| U+0130 / i | false | ICU lower gives i plus combining dot versus i. |
| I / U+0131 | false | Dotless-i distinction retained. |
| e / U+00E9 | false | Accent distinction retained. |
| U+FF21 / A | false | Fullwidth/ASCII distinction retained. |
| U+00E9 / e + U+0301 | false | Composed/decomposed distinction retained. |
| A/B@1 / A-B@1 | false | Tested punctuation distinction retained. |

All distinct input pairs also had raw equality=false under this deterministic candidate; identical Chinese input had raw equality=true. These expressions are not unique-index rejection/concurrency tests. No complete Unicode coverage is claimed. Business confirmation concerns ignoring case; sharp-S/SS expansion, language-specific I policy and normalization/width equivalences are not automatically confirmed by either this experiment or a library's behavior.

**Explicit recommendation:** retain original VARCHAR display values and deterministic column defaults; validate a dedicated index-local ICU nondeterministic, case-insensitive but accent-sensitive root comparison (und-u-ks-level2) as the preferred candidate for both global interface-code uniqueness and per-interface route-name uniqueness. Do not adopt deterministic ICU lower as a complete fix merely because it handles sharp S. Do not change database-wide locale or systems seeds. Do not assume citext fixes the underlying lower/LC_CTYPE issue or that Python casefold equals PostgreSQL lower.

Adoption conditions: verify the candidate actually merges intended case pairs (including sigma); inventory added equivalences for normalization, width, punctuation and sharp-S/SS; obtain business decisions only for additional acceptance-changing equivalences; demonstrate real unique-index and concurrent behavior later. Scope route-name uniqueness to customer_interface_id. Keep the column deterministic because PostgreSQL 17 pattern-based nonblank Checks must not accidentally acquire nondeterministic matching semantics. Candidate collation ownership/versioning and downgrade cleanup must be explicit.

Because no usable nondeterministic candidate currently exists, this task cannot validate the preferred candidate without forbidden creation. **Next minimum validation:** under separate explicit authorization, create exactly one candidate collation in an isolated validation schema within a transaction, run the anonymous equality matrix, then roll back the entire transaction. Do not create tables/indexes or apply application migrations in that experiment. Check schema/name ownership first; do not drop/reuse unknown objects. This proposed future DDL was not executed here. Actual index/concurrency testing remains subsequent work.

The Unicode gate is a pre-interface-migration technical condition; it does not reopen confirmed business ownership/route rules or prevent phase-one relationship closure.

## 8. Reuse, changes and staged delivery

- Reuse Base, Customer, systems and five standard models; seven-table structure already verified against models/migrations. Existing Customer ASCII customer_code rules apply to a different identifier and need not be copied into customer interfaces. Shared two-end standards retain their own purpose.
- Adjust later: customer-interface comparison expression, its tests and migration design; add a dedicated collation only after validation/authorization. Preserve applied historical migrations and represent database changes through new revisions where appropriate. Do not assume a locally unapplied revision was never applied elsewhere; verify revision provenance before choosing revision-file handling.
- Add later: customer_routes, nodes, customer Mapping records/members and transformations; enforce composite ownership. No compatibility flags or misuse of standard details to impersonate private customer Mapping.
- Delivery sequence: comparison validation/correction -> interface migration preparation/application under separate scopes -> route/node physical models -> Mapping/member/transformation/history physical models -> authorized services/permissions/pages. Module priority remains UI001 + UI005 -> UI002 -> UI004 -> UI003.
- No route/node/Mapping physical deletion, table clearing or reset is authorized. Future structural corrections require concrete impact, stable-ID/backfill/collision handling and preservation/recovery plans, never silent merges/truncation. Actual row contents were not inspected.
- Next unique execution step: the isolated candidate-collation transaction experiment described in section 7, subject to separate DDL authorization. Stop before implementation or database table creation.
