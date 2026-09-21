import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel


# =========================
# Environment
# =========================
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")


# =========================
# Structured AI Output
# =========================
class DocumentFieldAI(BaseModel):
    path: str
    field: str
    system: str
    pk: str
    type: str
    size: str
    description: str
    sample: str


class DocumentAnalysisAI(BaseModel):
    interface_id: str
    interface_name: str
    fields: list[DocumentFieldAI]


# =========================
# Interface context helpers
# =========================
def build_interface_context_prompt(interface_context):
    """
    Add domain-specific understanding to the document analyzer.

    The parser/file format and the interface context are intentionally
    separated.

    Example:
        File format: Excel
        Interface context: SAP_SOAP
    """

    if interface_context == "SAP_SOAP":
        return """
INTERFACE CONTEXT:
This document describes or represents an SAP SOAP interface.

Treat the content as SAP SOAP interface information even if the uploaded
artifact itself is Excel or JSON rather than raw SOAP XML.

When interpreting fields, pay special attention to:
- SOAP request / response semantics when they are present
- XML element hierarchy
- Parent / child business-object relationships
- Element Path
- Namespace information when explicitly available
- XSD data types when explicitly available
- minOccurs / maxOccurs when explicitly available
- Required / Optional semantics when explicitly available
- SAP business object meaning
- Repeated elements / segments
- The semantic meaning of a field inside its parent element

Example:
An element named "InternalID" under "ConsigneeParty" should be understood
as the ID of the consignee/receiving party, not simply as a generic ID.

IMPORTANT:
- SOAP context improves semantic interpretation only.
- Do NOT recreate WSDL/XSD/XML information that is absent from the uploaded
  document.
- Do NOT invent namespaces, minOccurs, maxOccurs, operation names,
  request/response direction, XSD types, or parent hierarchy.
- Missing information must remain "".
"""

    return """
INTERFACE CONTEXT:
Analyze this as a general enterprise interface document.
Use only information supported by the uploaded document.
"""


# =========================
# Document AI Analyzer
# =========================
def analyze_document_payload(
    document_payload,
    role,
    file_name="",
    interface_context="GENERAL",
):
    """
    Analyze parsed interface-document content with Claude.

    role:
        "source" -> extract Source / Sender side fields
        "target" -> extract Target / Receiver side fields

    interface_context:
        "GENERAL"
        "SAP_SOAP"

    Returns:
        {
            "interface_id": "...",
            "interface_name": "...",
            "fields": [
                {
                    "Path": "",
                    "Field": "...",
                    "System": "...",
                    "PK": "...",
                    "Type": "...",
                    "Size": "...",
                    "Description": "...",
                    "Sample": "",
                }
            ]
        }
    """

    if role not in ["source", "target"]:
        raise ValueError(
            'role must be either "source" or "target".'
        )

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY was not found."
        )

    if not workspace_id:
        raise ValueError(
            "ANTHROPIC_WORKSPACE_ID was not found."
        )

    client = Anthropic(
        api_key=api_key,
        default_headers={
            "anthropic-workspace-id": workspace_id
        },
    )

    role_description = (
        "Source / Sender / Sending side"
        if role == "source"
        else "Target / Receiver / Receiving side"
    )

    context_prompt = build_interface_context_prompt(
        interface_context
    )

    prompt = f"""
You are an enterprise interface-document analyst.

Analyze the interface specification below.

FILE NAME:
{file_name}

DOCUMENT ROLE:
{role.upper()}

{context_prompt}

Your primary task is to extract:

1. Interface ID
2. Interface Name
3. Interface fields belonging to the {role_description}

IMPORTANT RULES:

GENERAL:
- Never invent unsupported information.
- If a value cannot be determined from the document, return "".
- Preserve the original meaning of field names and descriptions.
- The document may contain Korean, English, or mixed-language labels.
- The document may contain merged cells or sparse Excel layouts.
- Cell positions may be included to help you understand nearby labels
  and values.

SOURCE / TARGET SELECTION:
- This document may contain both Source and Target field definitions.
- Because role="{role}", extract fields from the {role_description}.
- Do NOT mix fields from the opposite side.
- If the document contains only one interface field definition
  and does not distinguish Source and Target, extract that field definition.

INTERFACE INFORMATION:
- Extract Interface ID only when explicitly present.
- Extract Interface Name only when explicitly present.
- Do not generate an Interface ID or Interface Name yourself.

FIELD RULES:
- field:
  Extract the actual interface field / element name.

- path:
  Preserve an explicit field path or element hierarchy when the document
  provides one.
  For SAP SOAP, use the documented XML hierarchy/path when available.
  Otherwise return "".

- system:
  Extract the system name only when it is explicitly associated with the
  selected side.
  Otherwise return "".

- pk:
  Return "PK" only when the document explicitly identifies the field as a
  primary key.
  Otherwise return "".

- type:
  Extract the documented data type.
  For SAP SOAP, preserve documented XSD/XML types when available.
  Otherwise return "".

- size:
  Extract the documented field size/length.
  Otherwise return "".

- description:
  Extract the field description from the document.
  Otherwise return "".

- sample:
  Extract an explicit example/sample value only when present.
  Otherwise return "".

DO NOT:
- Infer Table names.
- Create Remark values.
- Guess PK status.
- Guess maximum Size from an example value.
- Invent missing SOAP/WSDL/XSD metadata.
- Force values when the document does not provide enough evidence.

DOCUMENT PAYLOAD:
{json.dumps(
    document_payload,
    ensure_ascii=False,
    indent=2,
)}
"""

    response = client.messages.parse(
        model=model_name,
        max_tokens=8000,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        output_format=DocumentAnalysisAI,
    )

    ai_result = response.parsed_output

    # =========================
    # Convert to shared format
    # =========================
    fields = []

    for item in ai_result.fields:
        fields.append(
            {
                "Path": item.path,
                "Field": item.field,
                "System": item.system,
                "PK": item.pk,
                "Type": item.type,
                "Size": item.size,
                "Description": item.description,
                "Sample": item.sample,
            }
        )

    return {
        "interface_id": ai_result.interface_id,
        "interface_name": ai_result.interface_name,
        "fields": fields,
    }
