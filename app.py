"""Referral extraction review app.

Upload referral letters -> pipeline extracts -> review side-by-side
(letter on the left, editable fields on the right, flagged fields highlighted)
-> export the corrected JSON.

Run: streamlit run app.py
"""

import base64
import json
from pathlib import Path

import streamlit as st

from pipeline import config
from pipeline.ingest import ingest
from pipeline.output import build_output
from pipeline.process import extract_bytes
from pipeline.schema import FullBloodCount, ReferralRecord
from pipeline.validate import validate

st.set_page_config(page_title="Referral Extraction", layout="wide")
st.title("Referral letter extraction")
st.caption("Upload GP referral letters. Fields flagged 🚩 need a human check.")

FIELD_GROUPS = {
    "Patient": ["title", "first_name", "surname", "sex", "date_of_birth", "nhs_number",
                "address", "postcode", "home_telephone", "mobile", "language", "ethnicity"],
    "Referral": ["referral_date", "ubrn", "referring_gp", "practice", "practice_address",
                 "practice_postcode", "practice_telephone", "hospital", "trust"],
    "Clinical": ["suspected_pathway", "leukaemia", "lymphadenopathy", "myeloma",
                 "splenomegaly", "lymph_node_size_cm", "lymph_node_site", "symptoms",
                 "myeloma_features", "investigations", "medical_history", "comments",
                 "discussed_with_patient"],
    "Triage": ["document_type", "additional_findings"],
}


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
        tmp = config.CACHE_DIR / "uploads" / name
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
                record = extract_bytes(data, upload.name)
                flags = validate(config.CACHE_DIR / "uploads" / upload.name,
                                 record, cross_check=cross_check)
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            continue

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
            st.subheader("Extracted fields")
            edited = {}
            record_data = record.model_dump()
            for group, fields in FIELD_GROUPS.items():
                with st.expander(group, expanded=True):
                    for field in fields:
                        edited[field] = edit_field(
                            field, record_data[field], flags, upload.name
                        )
            with st.expander("FBC", expanded=True):
                fbc = {}
                for sub, sub_value in record_data["fbc"].items():
                    fbc[sub] = edit_field(f"fbc.{sub}", sub_value, flags, upload.name)
                edited["fbc"] = {k.split(".")[-1]: v for k, v in fbc.items()}

            final = build_output(
                upload.name,
                ReferralRecord.model_validate(edited),
                flags,
            )
            st.download_button(
                "Download reviewed JSON",
                json.dumps(final, indent=2),
                file_name=f"{Path(upload.name).stem}.json",
                mime="application/json",
                key=f"dl:{upload.name}",
            )
