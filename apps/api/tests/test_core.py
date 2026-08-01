from pathlib import Path
import pytest
from brixta_twin.models import BlendComponent,BlendCreate,RunRequest
from brixta_twin.seed import seed
from brixta_twin.simulation import Engine
from brixta_twin.storage import Repository


def test_baseline(tmp_path:Path):
    repo=Repository(tmp_path/"test.sqlite3");seed(repo)
    result=Engine(repo).run(RunRequest(blend_id="blend_reference_ppc",route_id="route_integrated_baseline",target_output_tph=100))
    assert result.achievable_output_tph==pytest.approx(73.8)
    assert result.events[-1].level=="RESULT"


def test_invalid_blend():
    with pytest.raises(ValueError):
        BlendCreate(name="bad",family="PPC",components=[BlendComponent(material_id="x",percentage=90)])

