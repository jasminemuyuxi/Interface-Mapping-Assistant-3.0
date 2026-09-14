def _source_match(ai_mappings, source):
    """
    Find the AI mapping for a Source field.

    Path is preferred because nested JSON can contain duplicate leaf field names.
    Field Name is used only as a fallback.
    """
    source_path = source.get("Path", "")
    source_field = source.get("Field", "")

    if source_path:
        for item in ai_mappings:
            if item.get("source_path") == source_path:
                return item

    for item in ai_mappings:
        if item.get("source_field") == source_field:
            return item

    return None


def _find_target(target_fields, match):
    """
    Resolve the real Target field selected by AI.

    Target Path is preferred, then Field Name is used as a fallback.
    """
    target_path = match.get("target_path", "")
    target_field = match.get("target_field", "")

    if target_path:
        for target in target_fields:
            if target.get("Path") == target_path:
                return target

    if target_field:
        for target in target_fields:
            if target.get("Field") == target_field:
                return target

    return None


def _target_key(target):
    return target.get("Path") or target.get("Field", "")


def build_mapping_rows(source_fields, target_fields, ai_mappings):
    """
    Build the unified Mapping Specification rows.

    Status rules:
    - Mapped: Source and Target were reliably matched.
    - Source Only: Source exists but no valid Target was found.
    - Target Only: Target exists but was not matched by any Source.

    Unknown values stay blank. Table and Remark remain manual-entry fields.
    """
    rows = []
    matched_target_keys = set()

    # =========================
    # Source side
    # =========================
    for seq, source in enumerate(source_fields, start=1):
        match = _source_match(ai_mappings, source)
        target = _find_target(target_fields, match) if match else None

        if match and target:
            matched_target_keys.add(_target_key(target))

            rows.append(
                {
                    "source_path": source.get("Path", ""),
                    "source_system": source.get("System", ""),
                    "source_seq": seq,
                    "source_table": "",
                    "source_pk": source.get("PK", ""),
                    "source_field": source.get("Field", ""),
                    "source_type": source.get("Type", ""),
                    "source_size": source.get("Size", ""),
                    "source_description": source.get("Description", ""),
                    "source_remark": "",

                    "mapping": "->",
                    "mapping_status": (
                        "Review Required"
                        if match.get("confidence", 100) < 75
                        else "Mapped"
                    ),

                    "target_path": target.get("Path", ""),
                    "target_system": target.get("System", ""),
                    "target_table": "",
                    "target_pk": target.get("PK", ""),
                    "target_field": target.get("Field", ""),
                    "target_type": target.get("Type", ""),
                    "target_size": target.get("Size", ""),
                    "target_description": target.get("Description", ""),
                    "target_remark": "",

                    "confidence": match.get("confidence", ""),
                    "ai_reason": match.get("reason", ""),
                }
            )
            continue

        # =========================
        # Source Only
        # =========================
        rows.append(
            {
                "source_path": source.get("Path", ""),
                "source_system": source.get("System", ""),
                "source_seq": seq,
                "source_table": "",
                "source_pk": source.get("PK", ""),
                "source_field": source.get("Field", ""),
                "source_type": source.get("Type", ""),
                "source_size": source.get("Size", ""),
                "source_description": source.get("Description", ""),
                "source_remark": "",

                "mapping": "",
                "mapping_status": "Source Only",

                "target_path": "",
                "target_system": "",
                "target_table": "",
                "target_pk": "",
                "target_field": "",
                "target_type": "",
                "target_size": "",
                "target_description": "No matching target field found.",
                "target_remark": "",

                "confidence": match.get("confidence", "") if match else "",
                "ai_reason": match.get("reason", "") if match else "",
            }
        )

    # =========================
    # Target Only
    # =========================
    for target in target_fields:
        if _target_key(target) in matched_target_keys:
            continue

        rows.append(
            {
                "source_path": "",
                "source_system": "",
                "source_seq": len(rows) + 1,
                "source_table": "",
                "source_pk": "",
                "source_field": "",
                "source_type": "",
                "source_size": "",
                "source_description": "No matching source field found.",
                "source_remark": "",

                "mapping": "",
                "mapping_status": "Target Only",

                "target_path": target.get("Path", ""),
                "target_system": target.get("System", ""),
                "target_table": "",
                "target_pk": target.get("PK", ""),
                "target_field": target.get("Field", ""),
                "target_type": target.get("Type", ""),
                "target_size": target.get("Size", ""),
                "target_description": target.get("Description", ""),
                "target_remark": "",

                "confidence": "",
                "ai_reason": "",
            }
        )

    return rows
