import shutil
from datetime import date
from pathlib import Path

from wsf.protocol import canonical_json, scientific_config_hashes

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_yaml_dates_are_canonical_json_strings() -> None:
    assert canonical_json({"day": date(2022, 2, 24)}) == '{"day":"2022-02-24"}'


def test_milestones_are_part_of_scientific_hash(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    shutil.copytree(PROJECT_ROOT / "config", config_dir)
    before = scientific_config_hashes(config_dir)
    path = config_dir / "milestones.yaml"
    path.write_text(path.read_text() + "\n# hash-change\n", encoding="utf-8")
    after_comment = scientific_config_hashes(config_dir)
    assert after_comment == before, "comments must not alter canonical scientific hashes"
    path.write_text(path.read_text().replace("2022-02-10", "2022-02-11"), encoding="utf-8")
    after_value = scientific_config_hashes(config_dir)
    assert after_value["milestones.yaml"] != before["milestones.yaml"]
