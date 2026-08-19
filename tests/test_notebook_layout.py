import json
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
NOTEBOOK_DIR = REPO_ROOT / "research" / "notebooks"
EXPECTED_NOTEBOOKS = {
    "q3-riskparity-btc-practice.ipynb",
    "q6-momentum-trend-riskparity-practice.ipynb",
    "q7-supertrend-riskparity-robustness-practice.ipynb",
    "q8-btc-trend-satellite-practice.ipynb",
    "q9-btc-supertrend-satellite-robustness-practice.ipynb",
    "q10-live-readiness-stress-practice.ipynb",
    "q11-supertrend-lvt-cross-validation-practice.ipynb",
    "q12-supertrend-replace-lvt-trend-confirmation-practice.ipynb",
    "q13-scan-v2-right-side-5-portfolio-practice.ipynb",
    "q14-scan-v2-pit-universe-practice.ipynb",
    "q15-all-bull-flip-long-sample-practice.ipynb",
    "q16-all-bull-flip-defense-practice.ipynb",
    "theme-alpha-q1-strong-theme-screening-practice.ipynb",
    "theme-alpha-q1-theme-enhancement-validation-practice.ipynb",
    "theme-alpha-q2-lowvol-trend-walkforward-practice.ipynb",
    "theme-alpha-q3-structure-robustness-practice.ipynb",
    "theme-alpha-q4-core-satellite-practice.ipynb",
    "theme-alpha-q5-bear-market-stress-practice.ipynb",
    "theme-alpha-q6-bear-defense-benchmark-completion-practice.ipynb",
    "theme-alpha-q7-production-realism-practice.ipynb",
    "theme-alpha-q8-signal-live-readiness-practice.ipynb",
    "theme-alpha-q12-long-sample-proxy-validation-practice.ipynb",
}


def test_all_practice_notebooks_live_in_research_directory():
    root_notebooks = {path.name for path in REPO_ROOT.glob("*-practice.ipynb")}
    moved_notebooks = {path.name for path in NOTEBOOK_DIR.glob("*-practice.ipynb")}

    assert root_notebooks == set()
    assert moved_notebooks == EXPECTED_NOTEBOOKS


def test_every_practice_notebook_has_repo_root_bootstrap():
    for path in NOTEBOOK_DIR.glob("*-practice.ipynb"):
        notebook = json.loads(path.read_text())
        first_code_cell = next(cell for cell in notebook["cells"] if cell["cell_type"] == "code")
        source = "".join(first_code_cell["source"])

        assert "find_repo_root" in source, path.name
        assert "os.chdir(REPO_ROOT)" in source, path.name
