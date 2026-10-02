import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="editor-tests-"))
os.environ["EDITOR_DATA_DIR"] = str(_TMP / "data")
os.environ["EDITOR_AI_PROVIDER"] = "deterministic"
os.environ["EDITOR_QC_MAX_RETRIES"] = "1"


@pytest.fixture(scope="session")
def dataset():
    from editor import testmedia

    return testmedia.make_dataset(_TMP / "media", n_clips=12, n_songs=2, with_reference=True, clip_seconds=(3.0, 5.0), w=640, h=360)


@pytest.fixture(scope="session")
def project(dataset):
    """A project with every asset uploaded and analysed (via the service layer)."""
    from editor import service as S

    p = S.create_project("Test Fest")
    for c in dataset["clips"]:
        with open(c, "rb") as fh:
            S.add_asset(p["id"], c.name, fh)
    for s in dataset["songs"]:
        with open(s, "rb") as fh:
            S.add_asset(p["id"], s.name, fh, "music")
    with open(dataset["reference"], "rb") as fh:
        S.add_asset(p["id"], "reference.mp4", fh, "reference")
    with open(dataset["logo"], "rb") as fh:
        S.add_asset(p["id"], "logo.png", fh, "logo")
    S.analyze_project(p["id"], "fast")
    return p
