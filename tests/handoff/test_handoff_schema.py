import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
ROOT = Path(__file__).resolve().parents[2]


def test_schema_is_valid_and_accepts_minimal_handoff():
    schema = json.loads((ROOT / "agents" / "handoff_schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    doc = {
        "task_id": "P1-DATA-001", "agent": "data-engineer", "agent_version": "a0.1",
        "objective": "x", "data_cutoff": "2026-10-08T00:00:00Z", "method": "y", "results": {},
        "limitations": [], "reproducibility": {"commit": "abc"}, "recommendation": "z",
        "artifacts": [], "audit_status": "NOT_AUDITED", "next_action": "n", "created_at": "2026-10-08T00:00:00Z",
    }
    jsonschema.validate(doc, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**doc, "audit_status": "LOOKS_FINE"}, schema)
