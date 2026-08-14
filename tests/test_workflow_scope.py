from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_webapp_changes_do_not_launch_every_engine_build():
    engine_workflow = (ROOT / ".github/workflows/build-engines.yml").read_text()
    webapp_workflow = (ROOT / ".github/workflows/build-webapp.yml").read_text()

    assert "- 'webapp/**'" not in engine_workflow
    assert "- 'scripts/convert_book.py'" not in engine_workflow
    assert "- 'webapp/**'" in webapp_workflow
    assert "- 'scripts/convert_book.py'" in webapp_workflow
    assert "fail-fast: false" in engine_workflow


def test_chatterbox_installs_the_official_matched_cuda_pair():
    dockerfile = (ROOT / "chatterbox/Dockerfile").read_text()

    assert "torch==2.6.0 torchaudio==2.6.0" in dockerfile
    assert "https://download.pytorch.org/whl/cu126" in dockerfile
    assert "https://download.pytorch.org/whl/cu124" not in dockerfile


def test_workflows_do_not_use_deprecated_node20_action_majors():
    workflows = "\n".join(
        path.read_text() for path in (ROOT / ".github/workflows").glob("*.yml")
    )

    for deprecated in (
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "docker/login-action@v3",
        "docker/build-push-action@v6",
        "actions/upload-artifact@v4",
    ):
        assert deprecated not in workflows
