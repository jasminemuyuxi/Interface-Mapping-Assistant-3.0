from dataclasses import dataclass, field
from typing import Any


@dataclass
class InterfacePackage:
    """
    Represents one side of an interface mapping.

    Each Interface Package contains:
    - one Structure File
    - zero or more Reference Documents
    """

    structure_file: Any = None

    reference_files: list[Any] = field(
        default_factory=list
    )

    role: str = ""