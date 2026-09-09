# NMS data extractor

Extract No Man's Sky game tables and icons for [No Man's Sky Recipes](https://nomansskyrecipes.com/). The website is in the sibling `nms` repository.

## Requirements

- Python and `pip install -r requirements.txt`.
- A complete MBINCompiler package matched to the installed game release. Install `MBINCompiler.exe`, `libMBIN.dll`, and any mapping file distributed with that release in `tools/`. Do not mix versions. See [MBINCompiler releases](https://github.com/monkeyman192/MBINCompiler/releases) for runtime requirements.
- ImageMagick (`magick` on PATH) for publishable PNG images. DDS files are not website-ready output.
- The installed game's `GAMEDATA/PCBANKS` directory for a full refresh. The default is `H:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS`.
- A verified previous-release snapshot. Do not substitute an older snapshot just to make a command pass.

## Check the current extraction

These commands do not publish data or advance the live report snapshots:

```powershell
python -m unittest discover -s tests
python -m utils.smoke --strict-duplicates
python extract.py --check-only --game-version 7.00
```

Use the actual game release for `--game-version`. Compiler provenance is recorded separately, and all required MXML headers must agree. A compiler version is not proof of the installed game version.

`--check-only` runs the JSON pipeline in a temporary workspace using existing MXML. Add `--report` to exercise report generation there too. `--no-strict` is available only with `--check-only` for diagnosis; it cannot publish output.

## Refresh for a new game release

Confirm the installed game version, install its matching compiler package, and check the previous-release snapshot. Then run a full refresh with an explicit version and a report. Do not delete `data/` first.

```powershell
python extract.py --refresh --game-version 7.00 --report
# Or choose another game installation:
python extract.py --pcbanks "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS" --game-version 7.00 --report
```

The command checks prerequisites, extracts into a temporary workspace, converts the required MBINs, parses the tables, validates the result, and publishes validated directories. Previous JSON, MXML, and reports are retained under `.refresh-backups/`. A JSON refresh does not delete existing images.

Missing sources, parser errors, incompatible compiler headers, unresolved recipe references, uncategorized items, unsupported building objects, and count drops over 20% stop publication. Review the sources and update the relevant explicit rules or tests when a change is legitimate. Do not bypass validation to ship an update.

Publication uses directory renames and rolls back ordinary failures. It is not one filesystem-wide atomic transaction: do not run site imports during publication. `.extraction.lock` prevents concurrent extractor commands. After a terminated process, inspect the lock's PID, staging directories, and backups before recovering. Never delete a lock belonging to a running process.

To regenerate JSON from existing MXML without unpacking the game:

```powershell
python extract.py --game-version 7.00 --report
```

## Images are a separate step

Run image extraction after JSON extraction so the icon inventory comes from the new data:

```powershell
python extract.py --images --pcbanks "X:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
# Reuse textures only after verifying their game release:
python extract.py --images --extracted "X:\verified-current-textures\EXTRACTED"
```

The website requires complete PNG output. Missing textures, failed conversions, or missing ImageMagick fail the operation. Unpacking without `--extracted` uses a fresh temporary directory so stale textures cannot satisfy missing files. Image manifests record file integrity and coverage.

Keep source data and images from the same release. A PNG existing on disk does not prove its source version or that its artwork is current.

## Release identity and reports

`new.json` contains genuinely added item IDs, `ChangedItems` for item-page details, and removed IDs. Category moves are not new items. Explicit building overrides and identical reissued rewards do not get duplicate new-item cards. Different expedition variants remain new and carry `ReleaseVariant` metadata.

Reports archive their baseline and current inputs with integrity manifests. Same-release reruns retain the same previous-release baseline. Saved reports must be rebuilt from their archived inputs, not live JSON or a guessed snapshot directory.

Do not repair a missing baseline by snapshotting the new release as its own predecessor. Recover a verified prior release first. Bootstrap is a separate explicit operation; follow the repository refresh skill.

For an intentional migration of verified existing data, inspect the paths and versions first, then use the bootstrap interface:

```powershell
python scripts/rebuild_new_from_report.py --bootstrap --release-version 7.00 --previous-version 6.40 --baseline-snapshot "reports/_latest_snapshot" --current-snapshot "data/json" --building-mxml "data/mbin/basebuildingobjectstable.MXML"
```

That example applies only when those directories have been verified as 6.40 and 7.00 respectively. Normal report generation migrates the existing verified legacy layout automatically. Legacy duplicate normalization is recorded in the snapshot manifest. It never changes the original legacy snapshot.

To rebuild from a new archived report, run `python scripts/rebuild_new_from_report.py <report.json>`. This writes data/json/new.json. A historical rebuild is not a complete release export: regenerate and validate the extraction manifest before importing data into the site.

## Website handoff

Use the website's checked import workflow after data and images pass validation. Validate manifests, recipe references, PNG coverage, and release metadata before replacing `src/datav2` and generated files in `public/images/items`. Preserve manual artwork not owned by the extraction manifest.

```powershell
pnpm run data:check
pnpm run data:sync
```

Both commands default to the sibling extractor; `--source <path>` selects another checkout. Legacy output requires explicit `--allow-legacy` during import and must be reviewed separately. That flag does not establish current-release provenance for old PNG files.

Then run in the website repository:

```powershell
pnpm run check:all
pnpm run test:data-import
pnpm run test:route-eligible
pnpm run build
pnpm run test:new-items
pnpm run test:legacy-redirects
```

Check /new, a changed item, expedition variants, creature search results, and images. Commit source changes and corresponding data deliberately. Push or deploy only when requested.

## Source and output inventory

Print the actual manifests instead of maintaining a separate manual PAK filter list:

```powershell
python extract.py --list-sources
```

`MBIN_FILTERS` and `EXPECTED_MXML_AFTER_REFRESH` in extract.py define required game sources. `EXPECTED_JSON_FILES` in utils/smoke.py defines data outputs. This includes arena rewards, egg modifiers, and creature globals.

There are currently 31 required MXML files (including eight English localization tables), 25 parser jobs, and 19 data JSON outputs. Supporting output includes localization, controller mappings, uncategorized diagnostics, new.json, and extraction-manifest.json. The extraction manifest records source/output hashes and game/compiler versions.

## Development

- Parsers must use `utils.workspace.workspace_root()` for related-table and localization lookups so staging cannot accidentally read live data.
- utils/categorization.py owns exact group-to-file routing. The first matching category wins. New groups need explicit rules.
- utils/coverage.py lists reviewed object-only building exceptions. Do not invent product names, icons, or recipes for object-table entries. New uncovered objects stop publication.
- utils/smoke.py validates all data files, nested creature identities, recipe references, content, and count changes. Intentional ID overlaps have location-specific exceptions.
- utils/report.py owns release snapshots and classification. utils/images.py owns icon inventory, conversion, and integrity.
- .cursor/skills/new-game-version/SKILL.md is the release checklist; .cursor/rules/nms-extraction.md describes repository conventions.

Use temporary fixtures for failure-path tests. Tests must not alter the real snapshots or game installation.

Run `python -m unittest discover -s tests` and `python scripts/check_release_archive.py --game-version 7.00` to check failure handling and a detached real-data archive round trip.
