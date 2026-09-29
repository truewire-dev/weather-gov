#!/usr/bin/env bash
# TRU-406: every command the CI `gates` job runs appears in AGENTS.md's Gates section
# character for character, after dropping `.venv/bin/`, `python -m ` and pytest's
# cosmetic `-q -rs`. Arguments that change the result (pyright's --project, ruff's
# paths) must stay. The final `git diff` may be described in prose instead. Then run the note's pyright/ruff exactly as written from the root.
# Usage: review/TRU-406/check.sh [rev]   (run from the repo root; needs .venv with [dev])
set -u
rev=${1:-HEAD}
gates=$(git show "$rev":AGENTS.md | sed -n '/^## Gates/,$p' | tr -s ' \n' '  ')
fail=0
while IFS= read -r cmd; do
  if [[ "$gates" == *"$cmd"* ]] || { [[ $cmd == "git diff"* ]] && [[ "$gates" == *'`git diff`'* ]]; }; then echo "ok      $cmd"; else echo "MISSING $cmd"; fail=1; fi
done < <(git show "$rev":.github/workflows/ci.yml | python3 -c '
import sys, yaml, re
for s in yaml.safe_load(sys.stdin)["jobs"]["gates"]["steps"]:
    for line in s.get("run", "").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "uv ")):   # install is not a gate
            continue
        line = line.replace(".venv/bin/python -m ", "").replace(".venv/bin/", "")
        print(re.sub(r" -q -rs$", "", line))
')
echo "--- the note's commands exactly as written, from the repo root:"
.venv/bin/pyright >/dev/null 2>&1; echo "pyright                                                 exit=$?"
.venv/bin/pyright --project packages/python/pyrightconfig.json >/dev/null 2>&1; echo "pyright --project packages/python/pyrightconfig.json    exit=$?"
.venv/bin/ruff format --check --config packages/python/ruff.toml >/dev/null 2>&1; echo "ruff format --check --config ... (no paths)             exit=$?"
.venv/bin/ruff format --check --config packages/python/ruff.toml packages/python/src packages/python/test >/dev/null 2>&1; echo "ruff format --check --config ... src test              exit=$?"
exit $fail
