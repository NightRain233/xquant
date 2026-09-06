"""Reject changed archives; verify the checked-in original evidence inventory."""
from pathlib import Path
import importlib.util
import hashlib
import json
import shutil
import zipfile
import pytest


def test_recovered_archive_inventory_and_corruption_detection(tmp_path):
    root = Path(__file__).resolve().parents[1]/'research/trading-ledger-2026-09-05/core90_recovery_2026_09_05'
    spec = importlib.util.spec_from_file_location('recovery', root/'reproduce.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.verify_archive(root)
    assert len(manifest['files']) == 301
    assert sum(row['matches'] for row in manifest['originalFixtureComparison']) == 6
    shutil.copyfile(root/'source_manifest.json', tmp_path/'source_manifest.json')
    (tmp_path/'original_xquant.zip').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='SHA256 mismatch'):
        module.verify_archive(tmp_path)


def test_repaired_baseline_manifest_covers_both_repository_boundaries():
    xquant = Path(__file__).resolve().parents[1]
    package = xquant / 'research/trading-ledger-2026-09-05'
    trading = xquant.parent / 'trading'
    output = package / 'core90_current_contract_2026_09_05/validated_2_1'
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['baseGitCommit']
    assert len(manifest['sourceHashes']) == 28
    assert any(name.startswith('trading/') for name in manifest['sourceHashes'])
    assert any(name.startswith('xquant/') for name in manifest['sourceHashes'])
    for name, expected in manifest['sourceHashes'].items():
        root = xquant if name.startswith('xquant/') else trading
        path = root / name.split('/', 1)[1]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    with zipfile.ZipFile(output / 'source_bundle.zip') as bundle:
        names = set(bundle.namelist())
    assert set(manifest['sourceHashes']) == names


def test_repaired_variant_ledgers_pass_audit():
    package = Path(__file__).resolve().parents[1] / 'research/trading-ledger-2026-09-05/three_asset_variant_comparison_2026_09_05'
    audits = json.loads((package / 'repaired_ledgers/audit.json').read_text())
    assert {row['variant'] for row in audits} == {
        'pure_risk_parity', 'core90_cash', 'core_supertrend_filter',
        'pure_risk_parity_delay1', 'core90_ma200_bull10_repaired',
    }
    assert all(row['passed'] for row in audits)
