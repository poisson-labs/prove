S0: repository scaffold.
S0.1: move lifelines to dev; core is numpy/pandas/scipy/pyarrow.
M1: Episode contract and Rollout protocol.
M4: Parquet store, run manifest, config_hash, resume support.
S3: Go1 v0/v1 golden fixture and published numbers.
S3.1: fixture provenance keyed on last manifest-touching commit.
M5: Kaplan–Meier, Aalen–Johansen, Wilson, cell survival table.
M6: run diff — Fisher/BH, paired McNemar, log-rank, MDE.
M2: grid / sobol / scenarios samplers, axis typing, SweepSpec, TOML loader, tool-reliability preset.
M3: local executor — seed derivation, plan/pair/resume, pre-flight, batched runs, timeout, caps.
M7: report — delta heatmap, worst-cells table, MDE honesty block, markdown/SVG/HTML.
M3: modal backend — image spec, parallel map, infra retry, cost guard, parity with local.
M10: CLI — sweep, diff, report, check, inspect, runs; keyless mock-agent quickstart.
M6: multi-event diff — per-event CIF comparison, single BH family, trade detection, max_mde_unchanged.
M7: multi-event report — per-event panels on a shared scale, trade line and marker, max_mde_unchanged honesty, saturation marker, forest plot, single-run survival report.
M10: multi-event CLI — inferred events, repeatable --event, check requires explicit events, single-run report, forest flag, readable receipt, local import_path.
Fix: competing set is constructed in one place; check refuses unknown events; zero-n cells render as holes.
M12: proofload.trace/1 schema with span parentage, wall-clock timing and code location; from_otel and from_litellm converters; record() and @step; inspect and the mock agent read and write the new shape.
Fix: inspect emits tab-delimited trace columns, so a span name or error message containing spaces cannot shift them; proofload.record aliases proofload.trace.record.
M12: episode stamper — proofload.otel.EpisodeStamper tags every span with proofload.run_id and proofload.episode from a per-context episode() block, behind the [agent] extra.
M12: kind ladder extended — fetch_response and execute_task mapped; openinference.span.kind and traceloop.span.kind typed as a rung below gen_ai.operation.name.
M3: in-process trace capture — the executor activates the instrumentors named in the sweep file, stamps every span with its episode, and carries the trace into Episode.meta.
Fix: max_spans keeps the earliest-started spans and drops the deepest, so a capped trace keeps its root.
M4: Store.read(meta=False) and Store.read(keys=) project and filter at the Parquet reader and Store.count reads the footers; diff, report, check and runs never decode meta, and inspect decodes only the rows it prints.
M3: a timed-out episode keeps its trace — the child drains a snapshot of its closed and open spans on SIGTERM, proofload.trace/1 gains truncated, errored rows carry meta, retention never strips an errored row, and inspect selects by error as well as outcome.
Fix: the drain pipe is created beside the outcome pipe on every timed call, capture or not, and a Modal errored result whose meta is not a mapping is refused like an invalid episode instead of being stored without it.
M3: a crashed episode keeps its trace — the error payload takes the dict form on both backends, complete up to the raise with the failing span marked, truncated None.
Pilot: golden-suite agent under examples/golden_pilot — HumanEval at 32 seeds through the full loop, chat completions only, own-span paths scrubbed; the first real integration's span count, dropped and other share recorded.
