"""Exercise real-data archive/rerun/rebuild behavior in a temporary copy only."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from utils.report import build_new_json_document, generate_refresh_report, resolve_report_archive  # noqa: E402


def document(report_path, root):
    archive = resolve_report_archive(report_path, repo_root=root)
    report = archive['report']
    return build_new_json_document(
        root, version_key=report['version_key'], previous_run=report.get('previous_run'),
        generated_at=report['generated_at'],
        baseline_snapshot_dir=archive['baseline_snapshot_dir'],
        current_snapshot_dir=archive['current_snapshot_dir'],
        building_mxml_dir=archive['building_mxml_dir'],
    ), archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='nms-archive-check-') as temporary:
        root = Path(temporary)
        shutil.copytree(REPO / 'data/json', root / 'data/json')
        shutil.copytree(REPO / 'reports', root / 'reports')
        (root / 'data/mbin').mkdir()
        shutil.copy2(REPO / 'data/mbin/basebuildingobjectstable.MXML', root / 'data/mbin/basebuildingobjectstable.MXML')
        first = generate_refresh_report(root, version_key=args.game_version)
        before, archive = document(first['report_json'], root)
        baseline = (archive['baseline_snapshot_dir'] / 'manifest.json').read_bytes()
        second = generate_refresh_report(root, version_key=args.game_version)
        same, _ = document(second['report_json'], root)
        if before != same:
            raise AssertionError('An identical rerun changed the release document')

        products = root / 'data/json/Products.json'
        rows = json.loads(products.read_text(encoding='utf-8'))
        rows.append({'Id': '__ARCHIVE_CHECK_ONLY__', 'Name': 'Temporary test item', 'Icon': 'probe.png'})
        products.write_text(json.dumps(rows), encoding='utf-8')
        corrected = generate_refresh_report(root, version_key=args.game_version)
        after, corrected_archive = document(corrected['report_json'], root)
        if after['Summary']['Added'] != before['Summary']['Added'] + 1:
            raise AssertionError('Same-release correction did not use the original baseline')
        if baseline != (corrected_archive['baseline_snapshot_dir'] / 'manifest.json').read_bytes():
            raise AssertionError('Same-release correction changed the baseline')
        historical, _ = document(first['report_json'], root)
        if historical != before:
            raise AssertionError('Historical report depended on live current files')
        print(f"Verified {before['Summary']['Added']} real added identities, identical rerun, corrected rerun, and detached historical rebuild. Live files untouched.")


if __name__ == '__main__':
    main()
