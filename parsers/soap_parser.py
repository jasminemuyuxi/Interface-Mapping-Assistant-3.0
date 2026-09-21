from io import BytesIO
import xml.etree.ElementTree as ET


# =========================
# XML helpers
# =========================
def split_tag(tag):
    """
    Split an XML tag into namespace URI + local name.

    Example:
        {http://schemas.xmlsoap.org/soap/envelope/}Envelope

    Returns:
        ("http://schemas.xmlsoap.org/soap/envelope/", "Envelope")
    """
    if tag.startswith("{") and "}" in tag:
        namespace, local_name = tag[1:].split("}", 1)
        return namespace, local_name

    return "", tag


def clean_attributes(attributes):
    """
    Convert XML attributes into a readable dictionary.

    Namespace-qualified attribute names are converted to their
    local names where possible.
    """
    result = {}

    for key, value in attributes.items():
        _, local_name = split_tag(key)
        result[local_name] = value

    return result


def detect_xml_document_type(root):
    """
    Detect the broad XML document type.

    Returns:
        SOAP_MESSAGE
        WSDL
        XSD
        XML
    """
    _, root_name = split_tag(root.tag)

    if root_name == "Envelope":
        return "SOAP_MESSAGE"

    if root_name in ["definitions", "description"]:
        return "WSDL"

    if root_name == "schema":
        return "XSD"

    return "XML"


def extract_namespaces(xml_bytes):
    """
    Extract namespace prefix -> URI declarations.

    Example:
        {
            "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
            "xs": "http://www.w3.org/2001/XMLSchema"
        }
    """
    namespaces = {}

    for event, item in ET.iterparse(
        BytesIO(xml_bytes),
        events=("start-ns",),
    ):
        prefix, uri = item

        # Default namespace has an empty prefix.
        display_prefix = prefix or "default"

        if display_prefix not in namespaces:
            namespaces[display_prefix] = uri

    return namespaces


# =========================
# XML structure parser
# =========================
def _walk_element(
    element,
    parent_path="",
    depth=0,
    rows=None,
):
    if rows is None:
        rows = []

    namespace, local_name = split_tag(element.tag)

    current_path = (
        f"{parent_path}.{local_name}"
        if parent_path
        else local_name
    )

    text_value = (
        element.text.strip()
        if element.text and element.text.strip()
        else ""
    )

    rows.append(
        {
            "Path": current_path,
            "Field": local_name,
            "Namespace": namespace,
            "Attributes": clean_attributes(
                element.attrib
            ),
            "Value": text_value,
            "Depth": depth,
            "Child Count": len(element),
        }
    )

    for child in element:
        _walk_element(
            child,
            parent_path=current_path,
            depth=depth + 1,
            rows=rows,
        )

    return rows


def read_soap_xml_file(uploaded_file):
    """
    Parse XML / SOAP XML / WSDL / XSD and preserve structural context.

    Supported file extensions:
        .xml
        .wsdl
        .xsd

    Output example:
        {
            "document_type": "SOAP_MESSAGE",
            "root": "Envelope",
            "namespaces": {...},
            "elements": [
                {
                    "Path": "Envelope.Body.CreateOrder.OrderNo",
                    "Field": "OrderNo",
                    "Namespace": "...",
                    "Attributes": {},
                    "Value": "SO001",
                    "Depth": 3,
                    "Child Count": 0
                }
            ]
        }
    """

    xml_bytes = uploaded_file.getvalue()

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(
            f"Invalid XML/WSDL/XSD: {exc}"
        ) from exc

    _, root_name = split_tag(root.tag)

    document_type = detect_xml_document_type(
        root
    )

    namespaces = extract_namespaces(
        xml_bytes
    )

    elements = _walk_element(
        root
    )

    return {
        "document_type": document_type,
        "root": root_name,
        "namespaces": namespaces,
        "elements": elements,
    }


# =========================
# AI-friendly SOAP payload
# =========================
def build_soap_ai_payload(parsed_xml):
    """
    Convert parsed XML/WSDL/XSD into an AI-friendly structure.

    Empty leaf values are preserved because WSDL/XSD frequently
    describe fields through tag names and attributes rather than
    example values.
    """

    compact_elements = []

    for element in parsed_xml["elements"]:
        compact_item = {
            "path": element["Path"],
            "field": element["Field"],
            "depth": element["Depth"],
        }

        if element["Namespace"]:
            compact_item["namespace"] = (
                element["Namespace"]
            )

        if element["Attributes"]:
            compact_item["attributes"] = (
                element["Attributes"]
            )

        if element["Value"]:
            compact_item["value"] = (
                element["Value"]
            )

        if element["Child Count"]:
            compact_item["child_count"] = (
                element["Child Count"]
            )

        compact_elements.append(
            compact_item
        )

    return {
        "document_type":
            parsed_xml["document_type"],
        "root":
            parsed_xml["root"],
        "namespaces":
            parsed_xml["namespaces"],
        "elements":
            compact_elements,
    }
