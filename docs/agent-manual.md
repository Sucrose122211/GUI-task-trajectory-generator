# Agent operations manual

## Purpose and boundaries

Generate concise English visual observations for GUI grounding from D(I, q, a): an original screenshot, an instruction, and a reference target. Outputs are demonstrations conditioned on the supplied answer, not independent predictions. Use an existing Codex ChatGPT or Claude subscription login. Default model selection remains with the CLI; `job.json` may optionally override `model`.

Read `AGENTS.md`, `QUICKSTART.md`, and this file before operating. Do not install system Python packages, copy credentials, invoke API fallback, or run inference just to test changes. `setup`, `init`, `doctor`, `plan`, `review`, `status`, `submit`, `release`, and dataset conversion do not call a model. `run` does. Execute it only within the user's authorized input and quantity. Generation is sequential. Do not translate the original instruction or repair invalid annotations silently.

For `/사용법 담당자`, `/사용법 팀원`, or `$gui-trajectory-usage`, read `.agents/skills/gui-trajectory-usage/SKILL.md` and only the selected role reference. Return Korean step-by-step instructions with commands and expected artifacts; do not execute those commands merely because the user asked for usage. See `docs/usage-skill.md` for client invocation details. The Claude Code `/사용법` entrypoint routes to the same canonical skill.

## Active ScreenSpot team run

Use `docs/screenspot-team-run.md` as the operational source for this run. Dataset: OS-Copilot/ScreenSpot-v2, revision `5efbb1f1b5463a575f2eb7bc30fe29e49c15f93c`. Use all 1,271 valid inputs, not the historical 30-input sample or synthetic demo. Preserve the single invalid annotation in the prepare report. Role remains `pilot_dev` and excludes the data from final SFT; ScreenSpot-Pro remains for evaluation.

Campaign: `screenspot-v2-team8-v1`, seed 42, `--batch-count 8`, both codex and claude, local catalog `data/screenspot-v2/campaign-team8.json`. Counts are [159,159,159,159,159,159,159,158]; expected fingerprint `8c0030d9b36dc071f1c55c876dc23dadf53bc179fd0af28dd966c622e0fede92`. Eight input batches produce sixteen provider tasks and 2,542 planned responses. About four workers claim one batch at a time. Two Codex and two Claude workers are a suggested staffing split, not assigned identities. No fixed per-worker batch count; faster workers acquire remaining tasks for their provider.

Every worker can fetch, prepare and generate the same catalog using the pinned commands in the run guide; no per-worker input ZIP is required. The coordinator registers that campaign once. Existing Apps Script deployment supports this catalog without redeployment; Google registration for this new campaign is not implied by local preparation. Keep the old demo and pilot runs separate. When --config is used, retain it on all subsequent commands, including any next-step suggestion printed without it.

## Shared assignment (default team workflow)

Read `docs/shared-assignment.md` for the complete coordinator setup. An owner creates a Sheet, pastes `apps-script/Code.gs`, runs setup, and deploys as owner with anonymous web-app access. The owner keeps the authoritative code in Script Properties. For this repository only, the user explicitly authorized sharing the matching GUI_TEAM_KEY and GUI_TEAM_URL in tracked root .env for a 1-2 day run. Read docs/repository-only-settings.md. This is not a general policy for other repos, and never applies to CLI/OAuth/service-account credentials. Do not print keys or require worker configuration. Workspace policies may prevent this deployment. Do not claim a real deployment was tested without an actual /exec endpoint.

Create the active catalog with `./pipeline campaign --manifest data/screenspot-v2/manifest.jsonl --name screenspot-v2-team8-v1 --seed 42 --batch-count 8 --providers codex claude --output data/screenspot-v2/campaign-team8.json`. Exact count uses partition_version 2; legacy batch-size catalogs retain version 1 and their fingerprints. The two CLI partition flags are mutually exclusive. Exact count rejects more batches than screen groups. Register it once with `./team register --campaign ... --url ...`. Workers prepare the same full dataset independently, then `join --campaign ... --manifest ... --url ... --worker member-a --provider codex`, `acquire`, `doctor`, `plan`, `run`, `submit`, `acquire`. `join` loads the committed .env automatically, without exporting its contents to child processes. Explicit process GUI_TEAM_KEY/URL settings override the file and --url overrides the address. Without a key it retains hidden-input fallback. The active ScreenSpot manifest and catalog paths are join defaults, so workers use `./team join --worker member-a --provider codex`. Workers do not edit Sheets or score CSVs.

The catalog checks paths-independent data identity, image hashes, whole-screen groups, prompt/schema and partition version. Each batch/provider is one task. Apps Script holds a ScriptLock across claim and state mutations; repeated acquire by the same worker/provider returns their active claim. CLI defaults remain in force. A local per-config flock prevents overlapping commands. `.team/` contains keys and claims and is excluded from Git and all archives. It must remain for resume.

Run polls cumulative latest results and updates Sheets at start, approximately every 30 seconds and on exit. Only offline/network failures are deferred; explicit rejected claims abort. A durable pending update is retried on run, sync or acquire. No new offline acquisition is allowed. `generated` means all responses exist, not human acceptance. `submit` creates a local ZIP and records its name/hash automatically; full completion yields `submitted`, partial completion cannot unlock the next task. Submitted means locally packaged, not uploaded or human-reviewed. Actual ZIP transfer remains separate; `submit --result-url https://...` records a supplied link without editing the sheet. Submitted tasks remain terminal during repeat run/sync. Unstarted tasks can be returned; no automatic expiry or reassignment of partial work is implemented.

`campaign.py` builds and validates catalogs; `coordination.py` handles HTTP, allocation state and cumulative progress; `apps-script/Code.gs` is the deployed service. Tests use fake teachers/HTTP and a Node-based Apps Script mock, not Google credentials or live models. `make check` includes both Python and JavaScript tests in containers.

## Entrypoints

Clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git and run commands from the checkout root. `./team` changes to that root so relative arguments have a single base. It uses host Python 3.10+ and its standard library. `./pipeline doctor` and `generate` also run on the host to reuse existing CLI authentication. Other `pipeline` commands use the backend selected by `./team setup`: `--backend local` creates `.venv` and installs pinned Pillow from `requirements-local.txt`; `--backend docker` builds the project image. The choice is saved in ignored `.pipeline-backend`. Without a saved choice, setup and pipeline default to Docker for compatibility. A later `./team setup` reuses the saved backend. Local mode requires Python venv/pip and initial download access, needs no activation, and never invokes Docker. Teacher commands always use host Python and existing CLI authentication. System Python packages are unchanged. Keep input, image, configuration and output paths inside this root; external paths are not mounted. A dataset can be prepared and bundled in another checkout before transfer.

```bash
./team setup --backend local
./team init --provider codex --manifest data/assignment-a/manifest.jsonl
./team doctor
./team plan
./team run --limit 1
./team run
./team status
./team review
./team submit --output dist/worker-a-results.zip
```

Use `--provider claude` for Claude. `./team --config jobs/worker.json <command>` selects a separate job. The global `--config` must precede the subcommand. `init` resolves its arguments from the project root, then stores paths relative to the configuration file. `init --output runs/worker-a` chooses the run directory. No existing configuration or delivery ZIP is overwritten.

Configuration created by `init`:

```json
{
  "schema_version": 1,
  "provider": "codex",
  "manifest": "data/assignment-a/manifest.jsonl",
  "output": "runs/codex",
  "model": null,
  "timeout": 300,
  "retries": 1
}
```

`timeout` is a positive integer in seconds per input. `retries` is 0-5 additional retries for eligible transient execution/timeout failures. `--limit` counts newly attempted inputs in this invocation, not already completed jobs. Completed invalid explanations are kept for review and are not automatically regenerated. Authentication, quota and setup errors halt generation. Same run settings and input identity are required for resume; a changed CLI version, model, template or manifest requires a new run directory. Exit 2 means invalid input, a failed check, a halted run or generated failures. Keyboard interruption of `team` exits 130.

## Module map

| File | Responsibility |
| --- | --- |
| `team` and `src/gui_trajectory/team.py` | Small workflow wrapper and job configuration |
| `pipeline` and `cli.py` | Detailed commands and host/container routing |
| `data.py` | Source adapters, coordinate normalization, pixel groups, pilot selection |
| `io.py` | Manifest paths, hashes and atomic JSON/JSONL writes |
| `runner.py` | Run identity, locking, resume, per-input execution |
| `providers.py` | Existing subscription CLI invocation and image delivery audit |
| `validation.py` | Output structure, reference coordinates and review flags |
| `review.py` | HTML, CSV, summary and manually approved export |
| `operations.py` | Whole-screen sharding and conflict-aware merging |
| `bundles.py` | Portable dataset/run ZIPs, allowlisted software release |
| `resources/teacher-v1.txt` | Common prompt with instruction and reference answer |
| `resources/teacher.schema.json` | Required teacher JSON structure |

## Data contracts and files

`manifest.jsonl` has one UTF-8 JSON object per line. `schema_version=1`; each row includes `sample_id`, `source`, `role`, `image`, `instruction`, `answer`, `group_id`, `source_group`, and `attributes`. Paths in `image.path` are relative to the manifest. The source records the dataset, revision, annotation file, record ID, adapter and adapter version. Images retain original bytes and SHA-256. Internal `answer.point=[x,y]` and optional `answer.bbox=[x1,y1,x2,y2]` use normalized original-image coordinates. `answer.original` preserves source coordinates and units. A box-only input derives its center and records `answer_origin=derived_box_center`.

Teacher response: `status` is `ok` or `needs_review`; `visual_steps` is an English string array; `final_click` is `{x,y}` or null; `review_reason` is a string. The prompt requests 2-6 short visible observations without fictional actions. Codex receives the screenshot as an image attachment. Claude receives a Read instruction and the pipeline checks actual image delivery. Internal CLI prompts/reasoning are not exported. The template, CLI details and schema are documented in `docs/pipeline-usage.md` and the pilot Notion specification.

Run layout:

```text
runs/<name>/
  run.json                   # immutable cohort config and manifest identity
  manifest.jsonl             # inputs with paths relocated to this run
  summary.json               # latest invocation counts, not cumulative totals
  jobs/<job_id>/
    attempt-0001.json         # sanitized attempt record
    result.json              # latest result, config, response/error, validation, usage
  review/
    review.html              # original screenshot, reference target and response
    scores.csv               # job_id, evidence, target_match, usefulness,
                             # consistency, decision, reviewer, notes
```

`state=completed`, teacher `status=ok`, and `validation.valid=true` are separate signals. None substitutes for human review. `status` reports automatic result categories, not human acceptance counts. `review` preserves previous CSV decisions and adds new jobs. `submit` preserves the latest results, all assigned inputs and their original images, run settings and optional `review/scores.csv`; it excludes private CLI logs, attempt history and authentication. A submission may be partial or include failures; inspect result counts before calling it complete. ZIPs include `BUNDLE.json` and `SHA256SUMS.txt`.

## Manual assignment compatibility and result collection

```bash
./pipeline shard --manifest data/custom/manifest.jsonl --count 3 --output data/shards
./pipeline bundle-data --manifest data/shards/shard-000.jsonl --output dist/assignment-a.zip
```

Distribute the GitHub repository URL and access permissions, then each worker's assignment ZIP. Do not alter sample identities or roles when assigning work. To compare teachers, give the same assignment to one Codex and one Claude worker. Repository operations and CI are described in `docs/github-distribution.md`. CI builds the project container and runs `make check` with fake teachers. Stop active generation before pulling changes, rebuild with `./team setup`, and use a new run directory if identity changes.

The optional `./team release` command creates `dist/gui-trajectory-team-0.1.0.zip` for offline transfer. It contains explicitly selected program files, docs, tests and the synthetic example; its root README is the quick-start manual. Real datasets, run outputs, machine context and authentication directories are excluded.

Extract submissions under `runs/incoming/`, then:

```bash
./pipeline merge --runs runs/incoming/worker-a-results runs/incoming/worker-b-results \
  --output runs/merged
./pipeline review --run runs/merged --output runs/merged/review
```

Merging verifies image hashes, permits identical samples stored at different image paths, preserves different teacher jobs, and rejects conflicting sample contents or different results for the same job ID. Merged output must be empty. `merge` does not aggregate human score sheets: submissions retain them separately. Copy reviewed rows by `job_id` into the merged CSV, reject duplicates and conflicting judgments, then export. Do not mark any sample accepted based solely on the user's general assessment of the pilot.

```bash
./pipeline export --run runs/merged --scores runs/merged/review/scores.csv \
  --output runs/merged/expert.jsonl
```

Export requires human `accept`, a nonempty reviewer, four integer scores of 1-2 with sum >=6, valid automatic checks and teacher `ok`. ScreenSpot-v2 is reserved for `pilot_dev`. Pilot export needs `--allow-pilot` and retains `exclude_from_training=true`; validation/test cannot be exported. No SFT or Harvard projection sampling is performed here.

## Adapting and changing code

First try `prepare --adapter mapped` as described in `docs/dataset-adaptation.md`. Add adapter code only if the source cannot be represented by field paths and explicit coordinates. Preserve original screenshots, provenance and coordinate semantics. Add meaningful fixture tests for a new format, including at least one invalid annotation.

For Docker mode, run `make build` after changing package code because preprocessing uses the installed container package. Local mode reads the checkout source directly; run `./team setup` after dependency changes. Then `make check` runs Ruff lint/format, subprocess-level fake-teacher tests and a wheel build inside Docker. Do not use a real subscription for CI. Tests cover portable archive transfer and the wrapper workflow. Linux container checks are not proof of a separate physical WSL environment.
