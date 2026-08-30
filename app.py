"""Referral extraction review app.

Upload referral letters -> pipeline classifies and extracts (haematology 2WW
letters get the full specialty schema; other referrals fall back to the generic
schema) -> review side-by-side (letter left, editable fields right, flagged
fields highlighted) -> export the reviewed JSON.

Run: streamlit run app.py
"""

import base64
import json
from pathlib import Path

import streamlit as st

from pipeline import config
from pipeline.ingest import ingest
from pipeline.output import build_output
from pipeline.process import extract_bytes, upload_path
from pipeline.registry import DEFAULT_SCHEMA
from pipeline.validate import validate

st.set_page_config(page_title="Referral Extraction", layout="wide")
st.title("Referral letter extraction")
st.caption("Upload referral letters. Fields flagged 🚩 need a human check.")


def show_letter(name: str, data: bytes) -> None:
    ext = Path(name).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg"):
        st.image(data)
    elif ext == ".pdf":
        b64 = base64.b64encode(data).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" '
            'width="100%" height="700"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        # txt/docx/heic: show what the pipeline actually feeds the model
        tmp = upload_path(name)
        block = ingest(tmp)[0]
        if block["type"] == "text":
            st.text(block["text"])
        else:  # heic converted to jpeg
            st.image(base64.b64decode(block["source"]["data"]))


def edit_field(field: str, value, flags: dict, key_prefix: str):
    label = field.replace("_", " ")
    if field in flags:
        label = f"🚩 {label}"
        st.warning(f"**{field}**: {flags[field]}")
    key = f"{key_prefix}:{field}"
    if isinstance(value, bool):
        return st.checkbox(label, value=value, key=key)
    if isinstance(value, list):
        edited = st.text_area(label, "\n".join(value), key=key, height=68)
        return [line.strip() for line in edited.splitlines() if line.strip()]
    return st.text_input(label, value, key=key)


uploads = st.file_uploader(
    "Referral letters",
    type=["txt", "docx", "pdf", "png", "jpg", "jpeg", "heic"],
    accept_multiple_files=True,
)

cross_check = st.toggle(
    "Cross-check with a second model (flags disagreements)",
    value=False,
    disabled=not config.OPENAI_API_KEY,
    help="Needs OPENAI_API_KEY in env.local",
)

if not uploads:
    st.info("Upload one or more referral letters to begin.")
    st.stop()

tabs = st.tabs([u.name for u in uploads])
for tab, upload in zip(tabs, uploads):
    with tab:
        data = upload.getvalue()
        try:
            with st.spinner(f"Extracting {upload.name}..."):
                record, schema = extract_bytes(data, upload.name)
                flags = validate(upload_path(upload.name),
                                 record, schema, cross_check=cross_check)
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            continue

        if schema.name != DEFAULT_SCHEMA:
            st.info(
                f"ℹ️ Not a haematology 2WW letter — extracted with the "
                f"**{schema.display_name}** schema instead."
            )
        if "document_type" in flags:
            st.error(f"⛔ {flags['document_type']}. Fields below are best-effort only.")
        if record.additional_findings.strip():
            st.warning(f"**Additional findings:** {record.additional_findings}")
        if flags:
            st.warning(f"{len(flags)} field(s) flagged for review")
        else:
            st.success("No fields flagged")

        left, right = st.columns([1, 1])
        with left:
            st.subheader("Letter")
            show_letter(upload.name, data)
        with right:
            st.subheader(f"Extracted fields — {schema.display_name}")
            edited = {}
            record_data = record.model_dump()
            for group, fields in schema.groups.items():
                with st.expander(group, expanded=True):
                    for field in fields:
                        value = record_data[field]
                        if isinstance(value, dict):  # nested object, e.g. fbc
                            edited[field] = {
                                sub: edit_field(f"{field}.{sub}", sub_value, flags,
                                                upload.name)
                                for sub, sub_value in value.items()
                            }
                        else:
                            edited[field] = edit_field(field, value, flags, upload.name)

            final = build_output(
                upload.name,
                schema.model.model_validate(edited),
                flags,
                schema,
            )
            st.download_button(
                "Download reviewed JSON",
                json.dumps(final, indent=2),
                file_name=f"{Path(upload.name).stem}.json",
                mime="application/json",
                key=f"dl:{upload.name}",
            )
