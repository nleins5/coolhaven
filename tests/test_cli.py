import json

from coolhaven.cli import main
from coolhaven.model import load_city


def test_cli_can_generate_and_load_a_reproducible_fixture(tmp_path):
    main(["generate", "--out", str(tmp_path)])
    city = load_city(tmp_path / "synthetic_city.json")
    assert len(city.sites) == 24
    assert len(city.demand) == 72


def test_cli_solution_includes_inputs_and_recomputable_outputs(tmp_path):
    main(["solve", "--out", str(tmp_path), "--population", "8", "--generations", "2"])
    result = json.loads((tmp_path / "solution.json").read_text())
    assert result["evaluation_calls"] == 24
    assert len(result["recommended"]["selected_sites"]) == 5
    assert "provenance" in result["city"]
