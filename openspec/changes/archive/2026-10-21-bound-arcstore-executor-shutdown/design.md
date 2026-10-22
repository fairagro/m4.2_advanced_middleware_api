# Design

## Context

See proposal.md for why shutdown should wait. `GitRepo` and `ConsolidatedGitArcStore` each own a `ThreadPoolExecutor`
and today call `shutdown(wait=False, cancel_futures=True)`. `GitRepo._cleanup_workdir` already logs an `OSError` from
`rmtree`. The catalog publish path uses `shutil.rmtree(..., ignore_errors=True)` and does not log. Stale directories are
reclaimed by `reclaim_stale_git_cache_dirs` (6-hour TTL). Python 3.12 `Executor.shutdown` has no timeout argument.

## Goals / Non-Goals

**Goals:**

- One shutdown helper used by both stores: cancel work that has not started, wait up to a fixed bound for work that has
  started, then return.
- Catalog workdir deletion logs a warning on failure and does not raise, matching `GitRepo._cleanup_workdir`.

**Non-Goals:**

- A new sweeper, a TTL change, or a new config knob.
- Cleanup after SIGKILL.
- Making pool threads daemon threads.
- An unbounded `shutdown(wait=True)`.

## Decisions

1. **Wait up to 60 seconds, then return.** `EXECUTOR_SHUTDOWN_TIMEOUT_S = 60` lives next to the helper. Sixty seconds
   covers a typical in-flight clone long enough for its `finally` to delete the workdir, and it still caps how long
   Celery `worker_shutdown` sits in `BusinessLogic.shutdown`. `command_timeout` is not this bound: it is optional, and
   when unset there is no per-command limit, so using it would make shutdown unbounded. A new operator knob is more
   surface than this hardening needs. The 6-hour reclaim remains the backstop when 60 seconds is not enough.
2. **Implement the bound with a daemon waiter around `shutdown(wait=True, cancel_futures=True)`.** `cancel_futures`
   drops work that has not started. `wait=True` lets the running Git call finish, including workdir cleanup. The waiter
   is joined for at most 60 seconds. Joining private executor threads would depend on `_threads`. A daemon waiter does
   not keep the process alive after the bound. Pool threads stay non-daemon, as they are today.
3. **One workdir-delete helper for the ephemeral directory.** It no-ops when the path is already gone, logs a warning
   with the path on `OSError`, and does not raise. `GitRepo._cleanup_workdir` and the catalog `finally` both call it.
   The per-file cleanup inside an existing clone (delete children other than `.git`) stays where it is. That path is not
   the orphan-directory problem.

## Risks / Trade-offs

- [60 seconds is shorter than a large clone.] → The workdir stays until reclaim. Shutdown does not wait longer.
- [After the bound, a non-daemon pool thread can still delay interpreter exit.] → Accepted. The helper's job is to stop
  blocking `worker_shutdown` past 60 seconds. It does not switch pool threads to daemon, which would drop `finally` on
  the way out.
- [A logged delete failure leaves the directory.] → Reclaim removes it after the TTL. The warning is the signal that the
  immediate delete failed.
