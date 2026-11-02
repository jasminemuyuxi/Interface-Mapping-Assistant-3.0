"""Display Registry planning and a minimal customer creation form."""

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from services.customer_service import (
    CustomerInputError,
    CustomerPersistenceError,
    DuplicateCustomerCodeError,
    create_customer,
)


_RESULT_KEY = "registry_customer_created"
_CLEANUP_KEY = "registry_customer_cleanup_warning"
_UNCERTAIN_SAVE = (
    "The save result could not be confirmed. Check whether the "
    "customer was created before trying again."
)
_FIELD_LABELS = {
    "customer_code": "Customer code",
    "customer_name_en": "Customer name (English)",
    "country_code": "Country / region code",
    "customer_name_local": "Customer name (local)",
    "contracting_entity_name": "Contracting entity name",
    "status": "Status",
    "remark": "Remark",
}
_INPUT_MESSAGES = {
    "required": "is required.",
    "invalid_type": "must be text.",
    "null_character": "must not contain null characters.",
    "too_long": "exceeds the permitted length.",
    "invalid_format": "has an invalid format. Check the field guidance.",
    "invalid_choice": "must be ACTIVE or INACTIVE.",
}


def _input_message(error: CustomerInputError) -> str:
    """Map known validation identifiers to fixed display text."""
    field = _FIELD_LABELS.get(error.field)
    message = _INPUT_MESSAGES.get(error.code)
    if field is None or message is None:
        return "Check the customer details and try again."
    return f"{field} {message}"


def _save_customer(values: dict) -> tuple[dict | None, str | None, bool]:
    """Own one short-lived Session and preserve the known commit outcome."""
    try:
        from db.database import SessionLocal
    except ValueError:
        return None, "Database configuration is unavailable.", False
    except SQLAlchemyError:
        return None, "Customer could not be saved.", False

    session = None
    result = None
    failure = None
    commit_started = False
    committed = False
    cleanup_failed = False
    try:
        session = SessionLocal()
        customer = create_customer(session, **values)
        # Copy loaded scalar values before commit; do not retain ORM objects.
        result = {
            "customer_id": customer.customer_id,
            "customer_code": customer.customer_code,
            "customer_name_en": customer.customer_name_en,
            "status": customer.status,
        }
        commit_started = True
        session.commit()
        committed = True
    except CustomerInputError as error:
        failure = _input_message(error)
    except DuplicateCustomerCodeError:
        failure = "Customer code already exists."
    except CustomerPersistenceError:
        failure = "Customer could not be saved."
    except SQLAlchemyError:
        failure = _UNCERTAIN_SAVE if commit_started else "Customer could not be saved."
    finally:
        if session is not None:
            if not committed:
                try:
                    session.rollback()
                except SQLAlchemyError:
                    cleanup_failed = True
            try:
                session.close()
            except SQLAlchemyError:
                cleanup_failed = True
    return result if committed else None, failure, cleanup_failed


st.title("Mapping Registry")
st.caption("Interface Mapping Assistant 3.0")

st.subheader("Create customer")
st.caption(
    "* Required. Inputs are retained after saving or an error. "
    "Unsubmitted input is not guaranteed to survive page navigation."
)
code_help = (
    "Leading and trailing whitespace is removed. Only ASCII lowercase "
    "letters are converted to uppercase when saved. "
)
with st.form(
    "registry_customer_create", clear_on_submit=False, enter_to_submit=False
):
    customer_code = st.text_input(
        "Customer code *", key="registry_customer_code",
        help=code_help + "1-50 characters: A-Z, 0-9, underscore or hyphen.",
    )
    customer_name_en = st.text_input(
        "Customer name (English) *", key="registry_customer_name_en",
        help="Required; up to 200 characters after trimming. Unicode is supported.",
    )
    country_code = st.text_input(
        "Country / region code *", key="registry_customer_country_code",
        help=code_help + "Exactly two letters A-Z. Format validation only.",
    )
    customer_name_local = st.text_input(
        "Customer name (local)", key="registry_customer_name_local",
        help="Optional; up to 200 characters after trimming. Blank becomes NULL.",
    )
    contracting_entity_name = st.text_input(
        "Contracting entity name", key="registry_customer_contracting_entity",
        help="Optional; up to 200 characters after trimming. Blank becomes NULL.",
    )
    status = st.selectbox(
        "Status *", ("ACTIVE", "INACTIVE"), index=0, key="registry_customer_status"
    )
    remark = st.text_area(
        "Remark", key="registry_customer_remark",
        help="Optional; surrounding whitespace is removed. Blank becomes NULL.",
    )
    submitted = st.form_submit_button("Create customer", type="primary")

if submitted:
    st.session_state.pop(_RESULT_KEY, None)
    st.session_state.pop(_CLEANUP_KEY, None)
    saved, failure, cleanup_failed = _save_customer({
        "customer_code": customer_code,
        "customer_name_en": customer_name_en,
        "country_code": country_code,
        "customer_name_local": customer_name_local,
        "contracting_entity_name": contracting_entity_name,
        "status": status,
        "remark": remark,
    })
    if saved is not None:
        st.session_state[_RESULT_KEY] = saved
    if failure is not None:
        st.error(failure)
    if cleanup_failed:
        st.session_state[_CLEANUP_KEY] = True

saved_result = st.session_state.get(_RESULT_KEY)
if saved_result is not None:
    st.success("Customer created successfully.")
    st.write("Customer ID:", saved_result["customer_id"])
    st.write("Customer code:", saved_result["customer_code"])
    st.write("Customer name:", saved_result["customer_name_en"])
    st.write("Status:", saved_result["status"])
if st.session_state.get(_CLEANUP_KEY):
    st.warning(
        "The customer was created, but database session cleanup did not complete."
        if saved_result is not None
        else "Database session cleanup did not complete. No automatic retry was made."
    )

st.info("This PoC currently supports creating individual customers. Other Registry features are planned.")

st.subheader("Planned Registry capabilities")
st.markdown(
    "- Customer and interface registration\n"
    "- Customer → CJ EDI → OMS → WMS mapping management\n"
    "- Mapping creation, editing, deletion, and search\n"
    "- Excel import and export\n"
    "- Revision history, approval, and audit"
)

st.subheader("AI Workspace")
st.write(
    "Use AI Workspace in the sidebar to open the existing AI Mapping workflow."
)
st.write(
    "A future integration will import AI Mapping results as Registry Drafts "
    "for human review before publication. This integration is not implemented yet."
)
