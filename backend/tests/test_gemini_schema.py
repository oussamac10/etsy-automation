import json

from app.providers.gemini import clean_gemini_schema
from app.providers.openai import ResearchSynthesisSchema


def test_clean_gemini_schema_strips_additional_properties_and_defs() -> None:
    raw_schema = ResearchSynthesisSchema.model_json_schema()
    cleaned = clean_gemini_schema(raw_schema)
    dumped = json.dumps(cleaned)

    # Ensure no additionalProperties or $defs or $ref exist in the sanitized schema
    assert "additionalProperties" not in dumped
    assert "$defs" not in dumped
    assert "$ref" not in dumped

    # Ensure valid structure
    assert cleaned["type"] == "object"
    assert "properties" in cleaned
    assert "concepts" in cleaned["properties"]
    assert "keyword_clusters" in cleaned["properties"]

    concepts_schema = cleaned["properties"]["concepts"]
    assert concepts_schema["type"] == "array"
    assert "items" in concepts_schema
    assert concepts_schema["items"]["type"] == "object"
    assert "properties" in concepts_schema["items"]
    assert "title" in concepts_schema["items"]["properties"]
    assert "prompt" in concepts_schema["items"]["properties"]
