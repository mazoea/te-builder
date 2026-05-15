# Security Notes
- Never commit `.env` file

# Critical principles:
- Use TDD, always include test (but reasonable one), and plan tests before implementation.
- Never add superfluous comments to self-explanatory names/methods/variables
- if you comment, then use brief and precisely comments
- always comment specific/complex/extraordinary things
- before implementation, plan and create tests
- before committing, all tests and pre-commit hooks must be executed and must pass
- no silent fallbacks
- do not invent patterns, read code first
- fix root cause, not symptoms
- Build Iteratively Start with minimal functionality and verify it works before adding complexity
- File Organization: Balance file organization with simplicity - use an appropriate number of files for the project scale
- Early Returns: Use to avoid nested conditions
- DRY Code: Don't repeat yourself
- Minimal Changes: Only modify code related to the task at hand
- Simplicity: Prioritize simplicity and readability over clever solutions

# Python:
- use f-string
- logging with _logger = ...
- argparse, tqdm (assume present)
- DO not use print, use logging
- strict typing everywhere
- use requirements.txt for dependencies

# Pull Requests and Commits
- check and suggest grammar improvements
- check and report obsolete documentation that is not useful because it mostly repeats self-explanatory method and class names
- Create a detailed message of what changed. Focus on the high level description of the problem it tries to solve, and how it is solved. Don't go into the specifics of the code unless it adds clarity.
- NEVER ever mention a co-authored-by or similar aspects. In particular, never mention the tool used to create the commit message or PR.
- Never commit and push on your own unless explicitly stated.
- If you create a PR, always wait for the GitHub Copilot review. Address each comment: if it makes sense, like + resolve it; if it does not make sense, reply + dislike. Only after every comment is handled may you continue.
- Always wait for the CI/CD pipeline to finish and be green. If it fails, investigate, fix, and iterate until it passes.

At the end of a task, always briefly summarize the plan and the results.

# Dir structure

- ./scripts/startme.bat: if a tool is updated/added, this should be updated to reflect the latest changes
- ./scripts: simple .bat files that call other scripts e.g., python scripts from ./tools
- ./tools: directory of helper python scripts, should be organized into subdirectories
