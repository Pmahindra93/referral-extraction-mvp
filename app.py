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
from pipeline.process import extract, extract_bytes, upload_path
from pipeline.registry import DEFAULT_SCHEMA, get_schema
from pipeline.validate import cross_model_flags, validate

st.set_page_config(page_title="Referral Extraction", layout="wide")

st.markdown("""<style>
/* slim clinical rule at the very top; hide app-builder chrome */
[data-testid="stHeader"] { background: transparent; height: 0; }
[data-testid="stToolbar"], footer { display: none; }

/* page title in Streamlit's native serif — the "form header" voice */
h1 { font-family: "Source Serif Pro", "Source Serif 4", Georgia, serif;
     font-weight: 600; letter-spacing: -0.01em; }
h3 { font-weight: 600; font-size: 1.05rem; }

/* eyebrow label above the title */
.eyebrow { font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
           color: #5A6B72; font-weight: 600; margin-bottom: -0.6rem; }

/* signature: extracted values read like typed record entries —
   monospace makes character-level checking against the scan easier */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
  font-family: "Source Code Pro", ui-monospace, Menlo, monospace;
  font-size: 0.85rem; background: #FFFFFF; }

/* field labels: quiet, uppercase, like a printed proforma */
[data-testid="stWidgetLabel"] p { font-size: 0.72rem; letter-spacing: 0.06em;
  text-transform: uppercase; color: #5A6B72; }

/* expanders as clean record sections */
[data-testid="stExpander"] { border: 1px solid #E2E6E5; border-radius: 6px;
  background: #FFFFFF; }
[data-testid="stExpander"] summary { font-weight: 600; }
</style>""", unsafe_allow_html=True)

header_left, header_right = st.columns([3, 1], vertical_alignment="bottom")
with header_left:
    st.markdown('<p class="eyebrow">Clinic ops · Referral intake</p>', unsafe_allow_html=True)
    st.title("Referral letter extraction")
    st.caption("Upload referral letters. Flagged fields need a human check before the record is trusted.")
with header_right:
    cross_check = st.toggle(
        "Cross-check with a second model",
        value=bool(config.OPENAI_API_KEY),
        disabled=not config.OPENAI_API_KEY,
        help="An independent model re-reads each letter; disagreements are flagged. "
             "Note: letter content is sent to OpenAI as well as Anthropic while this "
             "is on. Needs OPENAI_API_KEY in env.local.",
    )


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


@st.cache_data(show_spinner="Cross-checking with a second model...")
def get_cross_flags(file_name: str, schema_name: str) -> dict[str, str]:
    """Cached so widget interactions don't re-pay a GPT call per rerun."""
    schema = get_schema(schema_name)
    path = upload_path(file_name)
    record = extract(path, schema=schema)  # disk-cached by this point
    return cross_model_flags(path, record, schema)


def edit_field(field: str, value, flags: dict, key_prefix: str,
               cross_fields: frozenset = frozenset()):
    label = field.replace("_", " ")
    if field in cross_fields:
        label = f"⚑ {label}"
        st.info(f"**{field}** — second model found a different value: "
                f"{flags[field].removeprefix('second model read ')}")
    elif field in flags:
        label = f"⚑ {label}"
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
                flags = validate(upload_path(upload.name), record, schema)
            disagreements = (
                get_cross_flags(upload.name, schema.name) if cross_check else {}
            )
            cross_fields = frozenset(
                f for f in disagreements if f not in flags
            )
            for field, reason in disagreements.items():
                flags.setdefault(field, reason)
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            continue

        if schema.name != DEFAULT_SCHEMA:
            st.info(
                f"Not a haematology 2WW letter — extracted with the "
                f"**{schema.display_name}** schema instead."
            )
        if "document_type" in flags:
            st.error(f"{flags['document_type']}. Fields below are best-effort only.")
        if record.additional_findings.strip():
            st.warning(f"**Additional findings:** {record.additional_findings}")
        if cross_check:
            if disagreements:
                st.warning(
                    f"**Cross-model check: {len(disagreements)} disagreement(s)** — "
                    + "; ".join(
                        f"`{f}` ({reason})" for f, reason in disagreements.items()
                    )
                )
            else:
                st.success("Cross-model check: the second model agrees on every field")
        if flags:
            with st.expander(f"Review needed — {len(flags)} flagged field(s)"):
                for field, reason in flags.items():
                    source = "second model" if field in cross_fields else "checks"
                    st.markdown(f"- **{field}** ({source}) — {reason}")
        else:
            st.success("Clean extraction — no fields flagged")
        download_slot = st.container()

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
                                                upload.name, cross_fields)
                                for sub, sub_value in value.items()
                            }
                        else:
                            edited[field] = edit_field(field, value, flags,
                                                       upload.name, cross_fields)

        final = build_output(
            upload.name,
            schema.model.model_validate(edited),
            flags,
            schema,
        )
        # Rendered into the container up top; edits still land because any
        # edit triggers a rerun before the download can be clicked.
        with download_slot:
            st.download_button(
                "Download reviewed JSON",
                json.dumps(final, indent=2),
                file_name=f"{Path(upload.name).stem}.json",
                mime="application/json",
                key=f"dl:{upload.name}",
            )
