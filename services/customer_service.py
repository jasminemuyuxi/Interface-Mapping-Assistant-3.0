"""Create individual customers using a caller-owned SQLAlchemy Session."""

import re

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from models.customer import Customer


_ASCII_UPPER = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


class CustomerInputError(ValueError):
    """Expose a field name and fixed validation code without input values."""

    def __init__(self, field: str, code: str) -> None:
        self.field = field
        self.code = code
        super().__init__(f"Invalid customer input: {field} ({code}).")


class DuplicateCustomerCodeError(Exception):
    """Report a customer-code unique constraint violation safely."""

    def __init__(self) -> None:
        super().__init__("Customer code already exists.")


class CustomerPersistenceError(Exception):
    """Report database persistence failures without database details."""

    def __init__(self) -> None:
        super().__init__("Customer could not be saved.")


def _normalize_text(
    value: str | None,
    field: str,
    *,
    required: bool,
    max_length: int | None = None,
) -> str | None:
    """Validate text type and content before trimming and length checks."""
    if value is None:
        if required:
            raise CustomerInputError(field, "required") from None
        return None
    if not isinstance(value, str):
        raise CustomerInputError(field, "invalid_type") from None
    if "\x00" in value:
        raise CustomerInputError(field, "null_character") from None
    normalized = value.strip()
    if not normalized:
        if required:
            raise CustomerInputError(field, "required") from None
        return None
    if max_length is not None and len(normalized) > max_length:
        raise CustomerInputError(field, "too_long") from None
    return normalized


def create_customer(
    session: Session,
    *,
    customer_code: str,
    customer_name_en: str,
    country_code: str,
    customer_name_local: str | None = None,
    contracting_entity_name: str | None = None,
    status: str = "ACTIVE",
    remark: str | None = None,
) -> Customer:
    """Validate, add, and flush one customer without committing.

    The caller owns the Session and transaction lifecycle. Flush may also
    write other pending objects in the Session. A returned object does not
    mean the transaction has committed successfully. After a flush failure,
    the caller must roll back the transaction or its SAVEPOINT before reusing
    the Session. No pre-insert duplicate lookup is performed.
    """
    code = _normalize_text(customer_code, "customer_code", required=True)
    code = code.translate(_ASCII_UPPER)
    if len(code) > 50:
        raise CustomerInputError("customer_code", "too_long") from None
    if re.fullmatch(r"[A-Z0-9_-]+", code) is None:
        raise CustomerInputError("customer_code", "invalid_format") from None

    name = _normalize_text(
        customer_name_en, "customer_name_en", required=True, max_length=200
    )
    country = _normalize_text(country_code, "country_code", required=True)
    country = country.translate(_ASCII_UPPER)
    if re.fullmatch(r"[A-Z]{2}", country) is None:
        raise CustomerInputError("country_code", "invalid_format") from None

    normalized_status = _normalize_text(status, "status", required=True)
    if normalized_status not in ("ACTIVE", "INACTIVE"):
        raise CustomerInputError("status", "invalid_choice") from None

    local_name = _normalize_text(
        customer_name_local, "customer_name_local", required=False, max_length=200
    )
    entity_name = _normalize_text(
        contracting_entity_name,
        "contracting_entity_name",
        required=False,
        max_length=200,
    )
    normalized_remark = _normalize_text(remark, "remark", required=False)

    customer = Customer(
        customer_code=code,
        customer_name_en=name,
        country_code=country,
        customer_name_local=local_name,
        contracting_entity_name=entity_name,
        status=normalized_status,
        remark=normalized_remark,
    )
    try:
        session.add(customer)
        session.flush()
    except IntegrityError as error:
        original = error.orig
        diagnostic = getattr(original, "diag", None)
        if (
            getattr(original, "sqlstate", None) == "23505"
            and getattr(diagnostic, "constraint_name", None)
            == "uq_customers_customer_code"
            and getattr(diagnostic, "table_name", None) == "customers"
            and getattr(diagnostic, "schema_name", None) == "public"
        ):
            raise DuplicateCustomerCodeError() from None
        raise CustomerPersistenceError() from None
    except SQLAlchemyError:
        raise CustomerPersistenceError() from None
    return customer
