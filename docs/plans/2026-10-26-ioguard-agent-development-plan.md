[![GitHub](https://img.shields.io/badge/GitHub-ioguard-181717)](https://github.com/ioplane/ioguard)

# ioguard Agent Development Plan

Date: 2026-10-26. Audited default branch: `master` at
`c668a609f78845ddbb1e0561083b4a419c4ac24b`. Planning audit: `ngtun-i8s.42.2`.
Durable execution work order: `ngtun-4zy.6` under independent portfolio `ngtun-4zy`.

Historical plans and local uncommitted August plans remain preserved. This dated
plan supplies the next validation/implementation contracts; it does not rewrite past
measurements, sprint completion records or current publish decisions.

## Verified baseline

The default tree contains the privilege-separated VPN modules, CSTP/TUN data handlers,
authentication backends and observability sources. Source presence does not establish
end-to-end client compatibility. `src/core/worker_loop.c:67-80` already calls
`iog_conn_data_process_tls`; the old roadmap's worker-loop TODO is historical.
`src/core/conn_data.c:29-35,48-53,201-207` needs explicit short-write and retained-buffer
qualification before the forwarding path is admitted. This is a review target, not a
reproduced runtime failure. README license wording differs from the GPLv3 LICENSE file;
resolve the source/document disposition without silently changing licensing.

## Next functional slice

Qualify one authenticated CSTP connection carrying a packet in both directions, including
fragmented input, short writes, WANT_READ/WANT_WRITE, queue exhaustion and disconnect.
Keep one owner for TLS state, pending buffers and operation completions. Correct a
reproduced violation in shared connection/data code; do not repeat the completed source
creation steps from the old Sprint 7 recipe.

| Order | Owned paths | Exit evidence |
| --- | --- | --- |
| 1 | `src/core/conn_data.*`, `worker_loop.*`, corresponding tests | Deterministic short-write/backpressure/cancellation reproduction; bounded ownership contract |
| 2 | Same owners plus existing `src/io/` integration when required | Exact payload equality, no duplicated/truncated packet, stable retries, quiescent teardown |
| 3 | Existing integration harness and English compatibility docs | Named client/profile, auth rejection, reconnect and isolated-lab round trip; separate TLS backend receipts |

## Dependencies and overlap

PR #22 owns base-image, contract and quality-tool migration; preserve its head and
review it in place before consuming the proposed runtime image. Parser admission requires
an exact qualified iohttpparser revision, strict consumer fixtures and retained span
lifetimes. Merely installing parser, iohttp, liboas or iojournal does not integrate them.
Admin HTTP and logger replacement remain later consumer decisions. Do not import ngtun
DTLS/wire/session policy or add ngtun as a dependency.

## Publication contract

Use the existing `master` contribution branch/PR workflow. Keep source, negative tests,
full container quality results and CHANGELOG in the same scoped change. Preserve both TLS
backend checks. Any live TUN/routes/namespace test requires a separately bounded procedure,
authorization and cleanup/readback. The present plan does not authorize that mutation.

## Execution and evidence rules

Read the target repository contract and applicable local skills before each leaf.
This independent portfolio does not gate ngtun release or require ngtun adoption.
Use an actually qualified project OCI; shared-base publication gates only its adoption.
Preserve dirty worktrees, unpublished plans, existing PRs and their path ownership.
Refresh exact default/PR identities before execution; keep compatibility explicit.
Record actual nonempty test/analyzer coverage and exact source/tool/image evidence.
Follow the repository task, changelog, review and delivery contract for each leaf.
This planning update claims no runtime success and authorizes no live mutation.
Repository quality gates remain pending until run; no host build or engine was used.

## Source baseline

- [Default README](https://github.com/ioplane/ioguard/blob/c668a609f78845ddbb1e0561083b4a419c4ac24b/README.md).
- [Default repository contract](https://github.com/ioplane/ioguard/blob/c668a609f78845ddbb1e0561083b4a419c4ac24b/CLAUDE.md); applicable dirty local contracts were read without importing their changes.
- [Existing PR #22](https://github.com/ioplane/ioguard/pull/22), audited head `51a6144d388b2cc90ffb1ba9271ee4b84b373862`; recheck the patchset before execution.
- [src/core/worker_loop.c:67](https://github.com/ioplane/ioguard/blob/c668a609f78845ddbb1e0561083b4a419c4ac24b/src/core/worker_loop.c#L67).
- [src/core/conn_data.c:29](https://github.com/ioplane/ioguard/blob/c668a609f78845ddbb1e0561083b4a419c4ac24b/src/core/conn_data.c#L29).
- [docs/plans/ROADMAP.md:118](https://github.com/ioplane/ioguard/blob/c668a609f78845ddbb1e0561083b4a419c4ac24b/docs/plans/ROADMAP.md#L118).
