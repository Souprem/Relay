# Relay bench: narrow decisions per call vs latency

Dataset gen-v0.3-dev, 40 cases (--limit 40 --sample-seed 11); model jev-1.13.0; q-v0.3 ordering.

| Questions per call | Calls | Errors | p50 latency (ms) | p95 latency (ms) | Mean latency (ms) | Mean input tokens | Est. cost / case |
|---|---|---|---|---|---|---|---|
| 1 | 40 | 0 | 178 | 230 | 186 | 982 | $0.000041 |
| 5 | 40 | 0 | 177 | 225 | 183 | 1526 | $0.000064 |
| 10 | 40 | 0 | 186 | 207 | 186 | 2534 | $0.000106 |
| 20 | 40 | 0 | 191 | 290 | 202 | 4207 | $0.000177 |

Total estimated cost: $0.0155

- Batching: Each call is one system_one request carrying all k questions for one case (typesafe-sdk==0.7.1); the client does not split a request.
- Per-question latency: Not measured: typesafe-sdk==0.7.1 returns no per-question timing (one HTTP request per call).
- Padding: Size 20 is q-v0.3's 19 questions plus 'diagnosis_support_padding', a duplicate of 'diagnosis_support' under another id (controlled padding).
- Size order: size order rotated per case (offset = (sample seed 11 + case index) mod len(sizes), a Latin square), so each size appears equally often in each call position.
- Calls ran one at a time; latency is wall time around one request, retries included.
- Latency-only: these runs' decisions are not scored.
- Question ordering: diagnosis_support, documentation_complete, material_contradiction, missing_evidence, mtx_start_month, mtx_start_day, mtx_start_year, mtx_end_status, mtx_end_month, mtx_end_day, mtx_end_year, mtx_inadequate_response, mtx_interrupted, mtx_pause_month, mtx_pause_day, mtx_pause_year, mtx_restart_month, mtx_restart_day, mtx_restart_year, diagnosis_support_padding
