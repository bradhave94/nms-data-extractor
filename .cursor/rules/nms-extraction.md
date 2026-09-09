---
description: NMS extraction safety, source coverage, categorization, and release conventions.
globs:
  - "parsers/**/*.py"
  - "utils/**/*.py"
  - "extract.py"
  - "tests/**/*.py"
  - "README.md"
---

# NMS extraction rules

Read this rule when changing the extractor. Use extract.py as the entry point.

## Data flow

The current pipeline has 25 parser jobs and 19 data JSON files. Run `python extract.py --list-sources` for authoritative PAK filters, required MXML files, and output files. Do not copy an old filter list into a release procedure.

Full refreshes use a new staging workspace. Related-table, localization, and controller lookups must use `utils.workspace.workspace_root()`, not paths relative to a parser's source file. Never clean the live data tree before validation. Publication retains recoverable backups.

Required sources, parser errors, empty outputs, unexpected category omissions, and unsupported building objects must fail the refresh. Do not continue with partial data. Smoke validation checks nested creature sections and explicit ID-overlap rules too.

## Parser and categorization conventions

- Keep game IDs. Do not create synthetic IDs or invent display names, icons, or recipes for records lacking catalog data.
- Use EXMLParser.translate() and normalized game icon paths. Missing control metadata has deterministic defaults; unknown control slots get readable labels rather than invented key bindings.
- Route by exact Group matches in utils/categorization.py. The first matching category wins.
- Specialized recipe, fish, trade, and substance parsers seed their outputs before categorization. Food keeps merge-style duplicate handling; other flat outputs keep the deterministic category policy.
- Creatures.json is sectioned metadata. Nested IDs need section-aware identity. A species, pet-shop reference, and flat product can share an ID only under an explicit rule.
- Building objects enrich existing catalog products. utils/coverage.py guards object-only omissions; review its exception list when the game adds an unsupported object.

## New-release semantics

Compare against a verified previous release across categories. A category move or extractor fix is not an item introduction. Keep field changes in ChangedItems for item pages. Suppress only proven building/reward aliases, never duplicates inferred from a shared name or icon alone. Keep expedition variants with different recipes or behavior and label them.

Game version and compiler version are separate metadata. Publication needs an explicit game version and matching compiler provenance. Preserve immutable release baseline/current archives and their integrity manifests. Never advance a snapshot after a failed new-item build.

## Verification and handoff

Use temporary fixtures for failure-path tests. Run `python -m unittest discover -s tests` and a staged `python extract.py --check-only --game-version <release> --report` before publication.

Images are a separate PNG-only publication step. Verify complete coverage and integrity before the site imports them. Imports must preserve manual website artwork. Follow .cursor/skills/new-game-version/SKILL.md for the full release workflow.
