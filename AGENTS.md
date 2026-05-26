
# Common Priorities

## Setup & Commands
Keep these names so agents can rely on them across repos:

- Run entry for humans:      `scripts\startme.bat`
- Single test:    `pytest path/to/test_x.py::test_y -q`
- Lint + format:  `pre-commit run --all-files`
- C++ build:      `cmaker.continue.bat nopause`       *(CI: `build-scripts/ci.build.u22.bat nopause`)*

If you add or rename anything under `tools/`, update `scripts/startme.bat` in the same change.

## Critical principles
- **TDD**: plan tests, write a failing test, then implement. Tests pass before commit.
- **No silent fallbacks**: no bare `except`, no `except Exception: pass`, no `or <default>` that swallows API errors. Raise or `_logger.error(...)`.
- **Reuse before adding**: grep for an existing helper before writing a new one; cite the file you read in your reply.
- **Diagnose, don't paper over**: if a test fails, explain the cause in your reply *before* changing code. Never edit a test only to make it pass.
- **Minimal blast radius**: touch only code related to the task. No drive-by reformatting, re-importing, or renaming.
- **Comments on non-obvious *why* only**: never restate function/variable names. One line where possible. Comment edge cases, known bugs, and the reason behind complex code.

## Code style

### Python
- f-strings only; no `%` or `.format()`.
- Logging: `_logger = logging.getLogger(__name__)`. Never `print()`.
- Strict typing on all new/changed signatures.
- CLI: `argparse`. Progress: `tqdm`. Both assumed present.
- Deps pinned in `requirements.txt`.
- Use relative paths, use `/` separator.

### C++
- Follow the existing CMake structure. No new dependencies without discussion.
- No raw `new` / `delete`. Use RAII / smart pointers.
- Mark overrides `override`. Const-correct accessors.
- Do not modify `third_party/**` or vendored sources.

### Frontend / JS
- Match the existing module pattern; do not introduce new build tooling without discussion.

## Agent conduct
- **May run without asking**: tests, linters, formatters, read-only git (`status`, `diff`, `log`), file reads, greps, builds.
- **Must ask before**: installing deps, editing `requirements.txt` / `CMakeLists.txt`, network calls, any `git commit` / `push` / `tag`, deleting files, touching `.env*` or `secrets/`, modifying `third_party/**`.
- Never bypass hooks (`--no-verify`) or disable commit signing (`--no-gpg-sign`).
- Never amend or force-push to a protected branch.
- When stuck, stop and ask. Do not invent APIs or file paths.
- At the end of every task, post a short summary: plan, what changed, test results.

## Before you commit
1. `pre-commit run --all-files` is green.
2. Tests are green.
3. New behaviour has a test written *before* the implementation (TDD).

## Pull requests and commits

Commit / PR-body format (repos squash-merge, so the PR body becomes the commit message):

    <area>: <imperative summary, <= 72 chars>

    Why:  <1-3 sentences on the problem being solved>
    How:  <1-3 sentences on the approach, only if non-obvious>
    Refs: <issue or ticket id, optional>

Rules:
- Focus on *why*, not a line-by-line recap of the diff.
- **Never** include `Co-Authored-By:` trailers, "Generated with" lines, or any mention of Claude / Codex / Copilot / Cursor / the tool used. CI enforces this; violations block merge.
- **Never** `git push` or open a PR unless the human explicitly asks. Local commits are fine.
- Reviewers and required checks come from branch protection + CODEOWNERS - do not try to bypass them.
- Check and suggest grammar improvements in changed prose; flag obsolete documentation that only repeats self-explanatory names.

When a PR is open (only after the human asks you to push):
1. `gh pr checks <num> --watch --fail-fast` - block until green.
2. Triage every Copilot review comment exactly once:
   - Correct  -> fix in a new commit, thumbs-up, **resolve** the thread.
   - Wrong    -> reply with a one-sentence reason, thumbs-down, resolve.
   - Conflict -> stop, tag the human Code Owner, do not guess.
3. After pushing fixes, re-request Copilot: `gh pr edit <num> --add-reviewer Copilot`. The automatic review does not re-run.
4. Flaky CI -> `gh run rerun <id> --failed` **once**. A second failure is a real failure.
5. Never force-push to `main` or `master` or any protected branch.

## Security
- Never stage files containing secrets: `.env`, `.env.*`, `*.pem`, `*.key`, anything under `secrets/`, anything matching `*credentials*`.
- Never include the literal value of an env var in code, logs, or PR comments - reference by name only.
- `.gitignore`, `gitleaks` pre-commit, and GitHub push protection are the safety net. Treat the rule as primary, not them.
- If you find a secret already in git history: **stop**, surface it to the human, do not rewrite history yourself.

## Cross-platform
- **Shell**: do not use PowerShell on Windows.
- **Wrappers**: every entry point in `scripts/` exists as `name.bat`; bash equivalents only when CI needs them.
- **`nopause`**: `.bat` wrappers pause for humans by default; pass `nopause` as the last arg in CI and agent runs to skip prompts.

## Layout
- `scripts/`         thin `.bat` / `.sh` wrappers; `startme.bat` is the canonical entry point. Update it when tools change.
- `tools/`           Python helpers, grouped into subdirectories by concern.
