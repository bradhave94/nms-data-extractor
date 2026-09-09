---
name: new-game-version
description: Verified NMS release refresh across staged extraction, immutable snapshots, PNG images, and the sibling website.
---

# Refresh a No Man's Sky release

Use this skill when the user requests a game-data refresh. When changing the extractor itself, test in temporary fixtures or use --check-only; do not refresh the installed game as an incidental code-editing step.

Run the requested workflow yourself. Do not hand the user a list of commands to run when you have access to the environment. Stop and report missing authority, source data, or a verified baseline rather than guessing.

## Preflight

1. Read both repos' instructions and check their git status. Preserve unrelated changes.
2. Confirm the actual game release and installed PCBANKS path. Default: H:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS. An MBINCompiler version is not evidence of the installed game release.
3. Install Python requirements and the complete compatible MBINCompiler release package in tools/. Keep MBINCompiler.exe, libMBIN.dll, and any distributed mapping file from the same release. Read the chosen release's runtime requirements.
4. Check the previous-release snapshot and its provenance. A snapshot of the current release cannot stand in for the previous release. Never delete or overwrite baseline history to get past an error.
5. Check ImageMagick before planning PNG publication.
6. Run `python extract.py --list-sources` for the actual required tables and outputs. Do not use an old manual list of PAK filters.

## Extract and validate

Replace 7.00 below with the verified game release. Never delete data/ first.

```powershell
python -m unittest discover -s tests
python extract.py --pcbanks "H:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS" --game-version 7.00 --report
```

The command stages extraction and reports, checks source coverage and output integrity, then publishes validated directories with recoverable backups. Existing images remain until the separate image step. Do not launch a site import while extraction holds .extraction.lock.

For parser-only regeneration, use existing verified MXML:

```powershell
python extract.py --game-version 7.00 --report
```

For code verification without publishing:

```powershell
python extract.py --check-only --game-version 7.00 --report
```

--no-strict is diagnostic-only and requires --check-only. A failed parser, empty category, missing localization source, unexpected count drop, unresolved reference, unsupported building object, or malformed snapshot needs investigation. Do not skip the gate for a release.

## Verify the release comparison

- Confirm new.json uses the intended current and previous game releases.
- Inspect added, changed, and removed identities across categories. Category moves and extraction fixes are not game introductions.
- Preserve distinct expedition variants with their labels. Collapse only proven building overrides and identical reward reissues.
- Check that reports archive baseline/current inputs with integrity manifests. Same-release reruns must preserve the original prior-release baseline.
- Rebuild historical reports only from their associated archived inputs. If the archive is missing, recover a verified snapshot or perform an explicit documented bootstrap. Never guess a baseline from its folder name.
- Check source/output hashes in extraction-manifest.json.

For an intentional migration, inspect `python scripts/rebuild_new_from_report.py --help`. Bootstrap takes --release-version, --previous-version, --baseline-snapshot, --current-snapshot, and --building-mxml. Only pass paths whose versions have been verified. Normal report generation handles the existing verified legacy layout; its duplicate normalization audit preserves the original legacy files.

## Generate images

Run after JSON extraction. Texture sources must belong to the same release:

```powershell
python extract.py --images --pcbanks "H:\Steam\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS"
```

Use --extracted only for a verified current texture directory. Require every expected PNG to pass validation and check the image manifest. Partial conversions, DDS-only output, and stale old PNGs are not a successful refresh. Do not claim legacy PNGs have verified new-release provenance merely because the files exist.

## Update and check the website

Use the sibling nms repository's checked import workflow. Validate JSON manifests, PNG integrity/coverage, routes, and site release metadata before import. Preserve manual artwork outside the generated image inventory.

Run `pnpm run data:check`, then `pnpm run data:sync` in the site repo. Both default to the sibling extractor; use --source for another checkout. Importing legacy data or images needs explicit --allow-legacy after inspection. Do not use that flag to bypass a corrupt manifest or to claim new-release image provenance.

Run the website checks after import:

```powershell
pnpm run check:all
pnpm run test:data-import
pnpm run test:route-eligible
pnpm run build
pnpm run test:new-items
pnpm run test:legacy-redirects
```

Verify /new, one existing unchanged item, one changed item, an expedition variant, creature search results, and the corresponding images. Ensure new cards have supported routes and real icons; metadata rows must not create broken cards.

Report the actual game/compiler versions, new-item count, validation results, and anything not exercised. Push both repositories or deploy only when the user has requested it. Keep the previous-output backups until the update is verified.
