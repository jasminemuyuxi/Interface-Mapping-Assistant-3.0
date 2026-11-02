"""Provide native navigation for the Registry and existing AI Workspace."""

import streamlit as st


st.set_page_config(
    page_title="Interface Mapping Assistant 3.0",
    page_icon=":material/account_tree:",
    layout="wide",
)

pages = [
    st.Page(
        "app_pages/mapping_registry.py",
        title="Mapping Registry",
        icon=":material/table_view:",
        default=True,
    ),
    st.Page(
        "app.py",
        title="AI Workspace",
        icon=":material/science:",
        url_path="ai_workspace",
    ),
]

selected_page = st.navigation(pages, position="hidden")
is_ai_workspace = selected_page.url_path == "ai_workspace"

# Approval must only be consumed after the current AI page completes.
if (
    not is_ai_workspace
    or st.session_state.get("app_nav_registry_request") == "approved"
):
    st.session_state.pop("app_nav_registry_request", None)

with st.sidebar:
    st.subheader("Navigation")

    if st.button(
        "Mapping Registry",
        key="app_nav_registry",
        disabled=not is_ai_workspace,
        width="stretch",
    ):
        st.session_state["app_nav_registry_request"] = "requested"

    if st.button(
        "AI Workspace",
        key="app_nav_ai_workspace",
        disabled=is_ai_workspace,
        width="stretch",
    ):
        st.switch_page(pages[1])

st.session_state["app_nav_managed"] = is_ai_workspace
page_completed = False
try:
    selected_page.run()
    page_completed = True
finally:
    st.session_state.pop("app_nav_managed", None)
    if not page_completed:
        # Reruns, stops, and errors must not leave a pending navigation behind.
        st.session_state.pop("app_nav_registry_request", None)

if (
    is_ai_workspace
    and st.session_state.get("app_nav_registry_request") == "approved"
):
    st.session_state.pop("app_nav_registry_request", None)
    st.switch_page(pages[0])
