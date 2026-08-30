"""The extraction schema — mirrors the ground-truth JSON exactly.

Every field the clinic ops team currently types in manually, as captured on an
NHS 2WW (urgent suspected cancer) haematology referral proforma.
"""

from pydantic import BaseModel, Field


class FullBloodCount(BaseModel):
    wbc: str = Field("", description="White blood cell count, e.g. '3.4'")
    hb: str = Field("", description="Haemoglobin in g/L, number only, e.g. '102'")
    platelets: str = Field("", description="Platelet count, e.g. '88'")
    neutrophils: str = Field("", description="Neutrophil count, e.g. '0.9'")
    lymphocytes: str = Field("", description="Lymphocyte count, e.g. '0.6'")


class ReferralRecord(BaseModel):
    # Triage guards (not part of the eval dataset)
    document_type: str = Field(
        "",
        description=(
            "'referral' if this document is a GP referral letter for the urgent "
            "suspected-cancer haematology pathway. Otherwise a short description of "
            "what the document actually is, e.g. 'discharge summary', "
            "'clinic appointment letter', 'not a medical document'."
        ),
    )
    additional_findings: str = Field(
        "",
        description=(
            "Anything clinically or administratively significant in the letter that "
            "does not fit any other field — e.g. safeguarding concerns, allergy "
            "warnings, DNR status, a second patient mentioned. Empty string if none."
        ),
    )
    # Patient demographics
    title: str = Field("", description="Patient title: Mr/Mrs/Ms/Miss/Dr etc.")
    first_name: str = ""
    surname: str = ""
    sex: str = Field("", description="'M' or 'F'")
    date_of_birth: str = Field("", description="DD/MM/YYYY")
    nhs_number: str = Field("", description="Format 'XXX XXX XXXX' with spaces")
    address: str = Field("", description="Street address WITHOUT postcode")
    postcode: str = ""
    home_telephone: str = ""
    mobile: str = ""
    language: str = Field("", description="Patient's main spoken language")
    ethnicity: str = ""
    # Referral admin
    referral_date: str = Field("", description="DD/MM/YYYY")
    ubrn: str = Field("", description="e-Referral booking reference, 'XXXX-XXXX-XXXX'")
    # Referrer
    referring_gp: str = Field("", description="Including title, e.g. 'Dr Naveen Malik'")
    practice: str = ""
    practice_address: str = Field("", description="Street address WITHOUT postcode")
    practice_postcode: str = ""
    practice_telephone: str = ""
    # Destination
    hospital: str = ""
    trust: str = ""
    # Clinical
    suspected_pathway: str = Field(
        "", description="e.g. 'myeloma', 'acute leukaemia', 'lymphoma'"
    )
    leukaemia: bool = False
    lymphadenopathy: bool = False
    myeloma: bool = False
    splenomegaly: bool = False
    lymph_node_size_cm: str = ""
    lymph_node_site: str = ""
    fbc: FullBloodCount = Field(default_factory=FullBloodCount)
    symptoms: list[str] = Field(default_factory=list)
    myeloma_features: list[str] = Field(default_factory=list)
    investigations: str = ""
    medical_history: str = ""
    comments: str = ""
    discussed_with_patient: str = Field("", description="'Y' or 'N'")


# JSON Schema handed to the LLM for structured output.
EXTRACTION_JSON_SCHEMA = ReferralRecord.model_json_schema()
