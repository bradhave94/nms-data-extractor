# Code review guidelines

How changes to this repo get reviewed, and what reviewers check. These guidelines are shared with BH's other game-site repos and adapted here for a data extractor. `AGENTS.md` has the repo's rules and commands; this file is how to review against them.

## When a change needs review

- **New extraction stages, output files or fields, and parsers** (anything the site will show players) get independent review before they reach `main`. Review them together with the site change that consumes them. One-shot reviews don't count.
- **Plain fixes and refreshes for a new game version** ship after your own checks (below), without a review round.
- **Reviewers** are Claude Opus 5.5 subagents, independent of the author. Use two for a big change and one for a small one. Don't use other models unless BH asks.
- **Rounds:** round 1 is a full review. Later rounds are delta-only: re-run every earlier repro, and review only the changed code for regressions. Stop when nothing blocking remains.
- **Branches:** work on a branch in its own git worktree.
- **Speed:** BH wants things finished quickly, so keep briefs tight and re-reviews to the delta.

## Reviewer report

Write the report to `_output/<site>/<feature>-review[-rN]/<reviewer>/REPORT.md`. If your tool can't write files, put it in your final message instead.

- **Findings:** rank each one **blocking / should fix / nit**. Give a repro, measured numbers, `file:line`, expected vs actual, and a suggested fix.
- **Evidence:** verify every claim against the game files; don't guess.
- **Scope:** label pre-existing issues as such, and list what you couldn't test.
- **Fixer's reply:** a **Finding → Fix (commit) → How verified** table, plus "Not changed (why)" and "Decisions for BH" sections.

## Checklist

- **Game data is the source of truth.**
  - Every value comes from the game files (tables, assets, decompiled code), and the code says where.
  - Nothing is hand-typed or guessed.
  - When the data can't decide (a bit offset, an ambiguous mapping), the output says so and the question goes to BH, who can check in game.
- **Lookups are exact.**
  - IDs map exactly, with no first-word or fuzzy matches.
  - Unmatched IDs are reported. They are never silently dropped or swapped for a plausible neighbour.
- **Counts and names mean what they say.** Hidden copies, test or placeholder assets and unused content are flagged, so the site can fold or hide them.
- **Failures are loud.**
  - A new game version, a missing input or an unknown format stops with a clear error or a listed warning. It never writes output that looks right but is wrong.
  - A partial run never overwrites good output.
- **Output is deterministic.** The same input gives the same bytes (sorted keys and lists), so diffs between versions show only real changes.
- **Output is diffed before publishing.**
  - Diff against the previous run and explain every large change.
  - Never invent history.
- **Only what's needed is committed.**
  - No game binaries and no raw dumps.
  - No saves, and nothing read from a save (account names, Steam/EOS IDs).
  - Outputs go where `AGENTS.md` says, usually `_output`, outside the repo.
- **Tests cover real and synthetic data.**
  - The parser is tested on real data copies (counts only, skipped when the copies are absent) and on synthetic fixtures.
  - Every review finding gets a regression check.
- **The site still builds with the new output.** Run the site's data import (`pnpm run data:sync` in `nms`) and `pnpm build`, and check that its dist checks pass.
- **Safety:** never send input to the real desktop, and never touch BH's real save folders (copy first).

## This repo

- Commands: see `README.md` (`python -m unittest discover -s tests`, `python -m utils.smoke --strict-duplicates`, `python extract.py --check-only --game-version <actual version>`). Never substitute an older snapshot to make a check pass; the MBINCompiler package must match the installed game.
