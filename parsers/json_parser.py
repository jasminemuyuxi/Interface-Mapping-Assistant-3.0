def flatten_json(data, parent_path=""):
    """
    Flatten JSON into a shared field structure.

    Supported structures:
    - Root object: {...}
    - Root array: [{...}]
    - Nested objects
    - Nested arrays of objects
    - Arrays of primitive values
    - Empty arrays

    Output example:
    {
        "Path": "order.items[].skuCode",
        "Field": "skuCode",
        "Type": "str",
        "Sample": "SKU001",
    }
    """

    fields = []

    # =========================
    # 1. JSON Object
    # =========================
    if isinstance(data, dict):

        for key, value in data.items():

            if parent_path:
                path = f"{parent_path}.{key}"
            else:
                path = key

            # -------------------------
            # Nested Object
            # -------------------------
            if isinstance(value, dict):

                fields.extend(
                    flatten_json(
                        value,
                        path,
                    )
                )

            # -------------------------
            # Array
            # -------------------------
            elif isinstance(value, list):

                # Array of objects
                #
                # Example:
                # "items": [
                #     {
                #         "skuCode": "SKU001"
                #     }
                # ]
                #
                # Path:
                # items[].skuCode
                if (
                    len(value) > 0
                    and isinstance(value[0], dict)
                ):

                    fields.extend(
                        flatten_json(
                            value[0],
                            path + "[]",
                        )
                    )

                # Array of primitive values
                #
                # Example:
                # "barcodes": [
                #     "111",
                #     "222"
                # ]
                else:

                    fields.append(
                        {
                            "Path": path,
                            "Field": key,
                            "Type": "array",
                            "Sample": str(value),
                        }
                    )

            # -------------------------
            # Primitive Value
            # -------------------------
            else:

                fields.append(
                    {
                        "Path": path,
                        "Field": key,
                        "Type": type(value).__name__,
                        "Sample": (
                            ""
                            if value is None
                            else str(value)
                        ),
                    }
                )

        return fields

    # =========================
    # 2. Root Array
    # =========================
    #
    # Example:
    # [
    #     {
    #         "orderNo": "O001",
    #         "customerCode": "C001"
    #     }
    # ]
    #
    # Previously this case returned [].
    # =========================
    if isinstance(data, list):

        # Empty root array
        if len(data) == 0:
            return fields

        # Root array of objects
        if isinstance(data[0], dict):

            return flatten_json(
                data[0],
                parent_path,
            )

        # Root array of primitive values
        fields.append(
            {
                "Path": (
                    parent_path
                    if parent_path
                    else "root"
                ),
                "Field": (
                    parent_path
                    if parent_path
                    else "root"
                ),
                "Type": "array",
                "Sample": str(data),
            }
        )

        return fields

    # =========================
    # 3. Unsupported Root Value
    # =========================
    return fields