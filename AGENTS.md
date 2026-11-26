# Repository workflow

- The active scope is the text trajectory baseline. Initial pilot: 30 ScreenSpot-v2
  inputs. Current team run: all 1,271 valid ScreenSpot-v2 inputs, seed 42, eight
  batches via --batch-count 8, two subscription CLI teachers, English output.
  About four workers claim dynamically; eight input batches create sixteen provider
  tasks. Read docs/screenspot-team-run.md. Keep pilot_dev and reserve ScreenSpot-Pro
  for evaluation.
- Use `./pipeline` for project commands. `doctor` and `generate` run on the host
  with existing user CLI authentication; other commands use the selected backend
  (Docker by default, or project `.venv` after
  `./team setup --backend local`). Local mode installs only pinned project dependencies
  into `.venv`, never system Python packages. Keep development checks in the container.
- Build the container with `docker build -t gui-trajectory:0.1 .`.
- Check changes with `make check`: Ruff lint/format, meaningful unit and integration
  tests, and a wheel build all run in the container. Do not install host packages.
- Never print, copy, package, or commit CLI credentials. Authentication checks must
  return only a provider, method and readiness boolean. Do not use API fallback.
- Live generation uses the CLI default model unless the user specifies one, and stays sequential.
  Do not run live inference merely to run tests; use fake CLI integration fixtures.
- Update `docs/pipeline-usage.md` and `.agent/CONTINUITY.md` for behavior changes.
- Team entrypoint: `./team`; read `QUICKSTART.md`, `docs/agent-manual.md`, and
  `docs/dataset-adaptation.md` for operating and extending the distribution.
- `./team release` creates an allowlisted software ZIP. Dataset and result bundles
  must include original images and relative manifest paths, never authentication.
- Primary distribution is GitHub clone/pull. Keep operational docs in the repository;
  real datasets, generated results, local research files, and credentials stay excluded.
- GitHub Actions runs `make build` and `make check` with fake teachers only.

# Repository-only shared configuration exception

- The user explicitly authorized committing root `.env` with GUI_TEAM_KEY and
  GUI_TEAM_URL for this short-lived (1-2 day) repository. This is intentional,
  repository-specific sharing, not a general credential-handling policy.
- Team commands load these defaults automatically. Do not ask workers to edit env
  files, export variables, or enter a key. Unless the user changes this decision,
  preserve the shared file rather than removing it as generic secret cleanup.
- This exception covers only the public team connection and its software release
  ZIP. Never print the key or include CLI credentials, OAuth/service-account keys,
  `.team/`, `.env.local`, or other personal secrets. Read docs/repository-only-settings.md.

# Shared assignment

- Default team distribution uses a seeded campaign catalog and Google Sheets through
  `apps-script/Code.gs`. Read `docs/shared-assignment.md` for one-time owner deployment.
- Workers use join/acquire/run/submit; they never maintain sheet rows or score CSVs.
- `.team/` contains participation keys and claim state; exclude it from Git and archives.
- submit records local ZIP creation, not file upload or human acceptance.
- Tests use fake HTTP and Node Apps Script fixtures; no live Google deployment is implied.

# Role-specific usage requests

- Treat `/사용법 담당자` and `/사용법 팀원` as requests for step-by-step instructions.
  Read `.agents/skills/gui-trajectory-usage/SKILL.md` and the selected role reference.
- Explain the commands and expected files in Korean. A usage request does not start
  generation, modify files, or upload anything. If no role is supplied, ask which role.
- Codex clients that reject an unknown slash command can invoke the same skill as
  `$gui-trajectory-usage 담당자` or `$gui-trajectory-usage 팀원`.
