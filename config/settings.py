import json
from pathlib import Path

_data = json.loads((Path(__file__).parent / "test_data.json").read_text())

BASE_URL: str = _data["base_url"]
CFG: dict = _data
