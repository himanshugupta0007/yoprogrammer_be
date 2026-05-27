VALID_TAG_TYPES = {"lang", "project", "domain", "general"}


def parse_input_tags(tags_raw: list) -> list[str]:
    """
    Accept [{type, value}] objects or "type:value" / plain strings.
    Returns deduplicated "type:value" strings ready for DynamoDB storage.
    Raises ValueError with a user-facing message on invalid input.
    """
    tags = []
    for t in tags_raw:
        if isinstance(t, dict):
            tag_type = str(t.get("type", "general")).strip().lower()
            tag_value = str(t.get("value", "")).strip().lower()
        else:
            raw = str(t).strip().lower()
            tag_type, tag_value = raw.split(":", 1) if ":" in raw else ("general", raw)

        if tag_type not in VALID_TAG_TYPES:
            raise ValueError(
                f"invalid tag type '{tag_type}', must be one of: {', '.join(sorted(VALID_TAG_TYPES))}"
            )
        tag_value = tag_value.strip()
        if not tag_value:
            continue
        if len(tag_value) > 50:
            raise ValueError("each tag value must be 50 characters or fewer")

        tags.append(f"{tag_type}:{tag_value}")

    return list(dict.fromkeys(tags))  # deduplicate, preserve order


def serialize_tags(stored_tags: list) -> list[dict]:
    """Convert stored "type:value" strings to [{type, value}] objects for API responses."""
    result = []
    for t in stored_tags or []:
        tag_type, tag_value = t.split(":", 1) if ":" in t else ("general", t)
        result.append({"type": tag_type, "value": tag_value})
    return result
