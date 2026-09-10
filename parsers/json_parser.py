def flatten_json(data, parent_path=""):
    fields = []

    if isinstance(data, dict):

        for key, value in data.items():

            if parent_path:
                path = f"{parent_path}.{key}"
            else:
                path = key

            if isinstance(value, dict):

                fields.extend(
                    flatten_json(
                        value,
                        path,
                    )
                )

            elif isinstance(value, list):

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

                else:

                    fields.append(
                        {
                            "Path": path,
                            "Field": key,
                            "Type": "array",
                            "Sample": str(value),
                        }
                    )

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