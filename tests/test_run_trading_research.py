import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_trading_research", ROOT / "scripts" / "run_trading_research.py"
)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runner)


def test_research_runner_discovers_migrated_scripts():
    scripts = runner.available_scripts()
    assert "compare_supertrend_timeframes" in scripts
    assert "replay_unified_decisions" in scripts
    assert all(Path(name).name == name for name in scripts)
