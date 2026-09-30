import streamlit as st
import pandas as pd
import sys
import os
import io
import re

# ---------------------------------------------------------
# Optional image/OCR imports
# ---------------------------------------------------------

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Outpatient Data Quality Improvement System",
    page_icon="📊",
    layout="wide"
)


# ---------------------------------------------------------
# Load validation engine
# ---------------------------------------------------------

sys.path.append(os.path.dirname(__file__))

from validation_engine import validate_outpatient_data


# ---------------------------------------------------------
# File paths
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(__file__)

DATA_PATH = os.path.join(
    BASE_DIR,
    "outpatient_merged.csv"
)

NEW_RECORDS_PATH = os.path.join(
    BASE_DIR,
    "new_outpatient_records.csv"
)


# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------

SOURCE_COLUMNS = [
    "S/NO.",
    "OBSERVATION NO.",
    "CATEGORY",
    "PT NO.",
    "PATIENT NAME",
    "REGISTRATION NO.",
    "PF NO.",
    "DATE",
    "DIAGNOSIS",
    "STATUS",
    "AGE",
    "GENDER",
    "OPD NO.",
    "RE-VISIT",
    "NO.",
    ">60",
    "SOURCE_FILE",
    "SOURCE_SHEET"
]


DISPLAY_COLUMNS = [
    "CATEGORY",
    "PT NO.",
    "PATIENT NAME",
    "REGISTRATION NO.",
    "PF NO.",
    "DATE",
    "DIAGNOSIS",
    "STATUS",
    "AGE",
    "GENDER",
    "OPD NO.",
    "RE-VISIT"
]


# ---------------------------------------------------------
# Session state
# ---------------------------------------------------------

DEFAULT_STATE = {
    "new_records": [],
    "last_entry_validation": None,
    "uploaded_data": None,
    "uploaded_validation": None,
    "ocr_text": "",
    "ocr_record": None,
    "last_saved_count": 0
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------
# Load original data
# ---------------------------------------------------------

@st.cache_data
def load_data():
    return pd.read_csv(DATA_PATH)


# ---------------------------------------------------------
# Load saved new records
# ---------------------------------------------------------

def load_saved_records():
    if os.path.exists(NEW_RECORDS_PATH):
        try:
            return pd.read_csv(NEW_RECORDS_PATH)
        except Exception:
            return pd.DataFrame()

    return pd.DataFrame()


# ---------------------------------------------------------
# Save records permanently
# ---------------------------------------------------------

def save_records_to_disk(df):
    """
    Append validated records to the persistent
    new_outpatient_records.csv file.
    """

    if df is None or df.empty:
        return False, 0

    save_df = df.copy()

    # Remove validation-only columns where appropriate
    validation_columns = [
        "AGE_RESULT",
        "DATE_RESULT",
        "GENDER_RESULT",
        "STATUS_RESULT",
        "DIAGNOSIS_RESULT",
        "REVISIT_RESULT",
        "REGISTRATION_RESULT",
        "PF_RESULT",
        "OPD_RESULT",
        "EXACT_DUPLICATE_RESULT",
        "OBSERVATION_RESULT",
        "OVERALL_RESULT",
        "NEEDS_ACTION",
        "ACTIONABLE_FLAG_COUNT"
    ]

    # Keep source fields and useful metadata
    save_df = save_df[
        [
            c for c in save_df.columns
            if c not in validation_columns
        ]
    ].copy()

    # Make sure the standard columns exist
    for column in SOURCE_COLUMNS:
        if column not in save_df.columns:
            save_df[column] = pd.NA

    save_df = save_df[SOURCE_COLUMNS]

    # Append to existing file
    if os.path.exists(NEW_RECORDS_PATH):

        try:
            existing = pd.read_csv(NEW_RECORDS_PATH)
        except Exception:
            existing = pd.DataFrame()

        if not existing.empty:

            for column in SOURCE_COLUMNS:
                if column not in existing.columns:
                    existing[column] = pd.NA

            existing = existing[SOURCE_COLUMNS]

            combined = pd.concat(
                [existing, save_df],
                ignore_index=True
            )

        else:
            combined = save_df

    else:
        combined = save_df

    combined.to_csv(
        NEW_RECORDS_PATH,
        index=False
    )

    return True, len(save_df)


# ---------------------------------------------------------
# Patient record definition
# ---------------------------------------------------------

def get_patient_records(df):

    structural_pt_values = [
        "Patient No",
        "PATIENT NO",
        "PATIENT NUMBER"
    ]

    if "PT NO." not in df.columns:
        return df.copy()

    is_patient = (
        df["PT NO."].notna()
        & ~df["PT NO."].astype("string").str.strip().isin(
            structural_pt_values
        )
    )

    return df[is_patient].copy()


# ---------------------------------------------------------
# Validation helper
# ---------------------------------------------------------

def validate_records(df):

    working = df.copy()

    for column in SOURCE_COLUMNS:

        if column not in working.columns:
            working[column] = pd.NA

    working = working[SOURCE_COLUMNS]

    return validate_outpatient_data(working.copy())


# ---------------------------------------------------------
# Create standardized record
# ---------------------------------------------------------

def create_record(
    pt_no="",
    category="Student",
    patient_name="",
    registration_no="",
    pf_no="",
    date=None,
    age="",
    gender="",
    opd_no="",
    revisit="",
    status="",
    diagnosis="",
    source_file="Direct Entry",
    source_sheet="New Record"
):

    if date is None:
        date_value = pd.Timestamp.today().strftime("%Y-%m-%d")

    elif hasattr(date, "strftime"):
        date_value = date.strftime("%Y-%m-%d")

    else:
        date_value = str(date)

    record = {
        "S/NO.": "",
        "OBSERVATION NO.": "",
        "CATEGORY": category,
        "PT NO.": str(pt_no).strip(),
        "PATIENT NAME": str(patient_name).strip(),
        "REGISTRATION NO.": (
            str(registration_no).strip()
            if str(registration_no).strip()
            else pd.NA
        ),
        "PF NO.": (
            str(pf_no).strip()
            if str(pf_no).strip()
            else pd.NA
        ),
        "DATE": date_value,
        "DIAGNOSIS": (
            str(diagnosis).strip()
            if str(diagnosis).strip()
            else pd.NA
        ),
        "STATUS": (
            str(status).strip()
            if str(status).strip()
            else pd.NA
        ),
        "AGE": (
            str(age).strip()
            if str(age).strip()
            else pd.NA
        ),
        "GENDER": (
            str(gender).strip()
            if str(gender).strip()
            else pd.NA
        ),
        "OPD NO.": (
            str(opd_no).strip()
            if str(opd_no).strip()
            else pd.NA
        ),
        "RE-VISIT": (
            str(revisit).strip()
            if str(revisit).strip()
            else pd.NA
        ),
        "NO.": "",
        ">60": "",
        "SOURCE_FILE": source_file,
        "SOURCE_SHEET": source_sheet
    }

    return record


# ---------------------------------------------------------
# Normalize uploaded data
# ---------------------------------------------------------

def normalize_uploaded_columns(df):

    df = df.copy()

    # Remove completely empty columns
    df = df.dropna(
        axis=1,
        how="all"
    )

    # Strip column names
    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    # Column aliases
    aliases = {
        "PT NO": "PT NO.",
        "PT NO": "PT NO.",
        "PATIENT NO": "PT NO.",
        "PATIENT NUMBER": "PT NO.",
        "PATIENT NAME": "PATIENT NAME",
        "NAME": "PATIENT NAME",
        "REG NO": "REGISTRATION NO.",
        "REGISTRATION": "REGISTRATION NO.",
        "REGISTRATION NUMBER": "REGISTRATION NO.",
        "PF": "PF NO.",
        "PF NUMBER": "PF NO.",
        "OPD": "OPD NO.",
        "OPD NUMBER": "OPD NO.",
        "REVISIT": "RE-VISIT",
        "RE VISIT": "RE-VISIT",
        "RE-VISIT": "RE-VISIT",
        "SEX": "GENDER",
        "DIAGNOSES": "DIAGNOSIS"
    }

    renamed = {}

    for column in df.columns:

        upper = str(column).strip().upper()

        if upper in aliases:
            renamed[column] = aliases[upper]

    if renamed:
        df = df.rename(columns=renamed)

    # Ensure all required columns exist
    for column in SOURCE_COLUMNS:

        if column not in df.columns:

            if column == "DATE":
                df[column] = pd.NaT

            else:
                df[column] = pd.NA

    # Keep standard columns first
    standard = [
        c for c in SOURCE_COLUMNS
        if c in df.columns
    ]

    extras = [
        c for c in df.columns
        if c not in standard
    ]

    return df[standard + extras]


# ---------------------------------------------------------
# Read uploaded file
# ---------------------------------------------------------

def read_uploaded_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".csv"):

        return pd.read_csv(
            uploaded_file
        )

    if filename.endswith(".xlsx") or filename.endswith(".xls"):

        excel_file = pd.ExcelFile(
            uploaded_file
        )

        sheets = {}

        for sheet in excel_file.sheet_names:

            sheets[sheet] = pd.read_excel(
                excel_file,
                sheet_name=sheet
            )

        # Combine sheets
        frames = []

        for sheet_name, frame in sheets.items():

            if frame.empty:
                continue

            frame = frame.copy()

            frame["SOURCE_FILE"] = uploaded_file.name
            frame["SOURCE_SHEET"] = sheet_name

            frames.append(frame)

        if not frames:
            return pd.DataFrame()

        return pd.concat(
            frames,
            ignore_index=True
        )

    raise ValueError(
        "Unsupported file type. Please upload CSV, XLS or XLSX."
    )


# ---------------------------------------------------------
# OCR preprocessing
# ---------------------------------------------------------

def preprocess_image(image):

    if not PIL_AVAILABLE:
        return image

    image = image.convert("L")

    # Increase contrast
    image = ImageEnhance.Contrast(
        image
    ).enhance(2.0)

    # Sharpen
    image = image.filter(
        ImageFilter.SHARPEN
    )

    # Resize for OCR
    width, height = image.size

    if width < 1800:

        scale = 1800 / width

        image = image.resize(
            (
                int(width * scale),
                int(height * scale)
            )
        )

    # Auto contrast
    image = ImageOps.autocontrast(
        image
    )

    return image


# ---------------------------------------------------------
# OCR
# ---------------------------------------------------------

def perform_ocr(uploaded_image):

    if not PIL_AVAILABLE:
        raise RuntimeError(
            "Pillow is not installed."
        )

    if not TESSERACT_AVAILABLE:
        raise RuntimeError(
            "pytesseract is not installed."
        )

    image = Image.open(
        uploaded_image
    )

    processed = preprocess_image(
        image
    )

    text = pytesseract.image_to_string(
        processed
    )

    return text


# ---------------------------------------------------------
# Extract likely fields from OCR text
# ---------------------------------------------------------

def extract_ocr_fields(text):

    result = {
        "PT NO.": "",
        "PATIENT NAME": "",
        "CATEGORY": "Student",
        "REGISTRATION NO.": "",
        "PF NO.": "",
        "DATE": "",
        "AGE": "",
        "GENDER": "",
        "OPD NO.": "",
        "RE-VISIT": "",
        "STATUS": "",
        "DIAGNOSIS": ""
    }

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    def find_value(labels):

        for line in lines:

            upper = line.upper()

            for label in labels:

                if label in upper:

                    parts = re.split(
                        r"[:\-]",
                        line,
                        maxsplit=1
                    )

                    if len(parts) == 2:
                        return parts[1].strip()

        return ""

    result["PT NO."] = find_value(
        ["PT NO", "PATIENT NO", "PATIENT NUMBER"]
    )

    result["PATIENT NAME"] = find_value(
        ["PATIENT NAME", "NAME"]
    )

    result["REGISTRATION NO."] = find_value(
        ["REGISTRATION NO", "REG NO", "REGISTRATION NUMBER"]
    )

    result["PF NO."] = find_value(
        ["PF NO", "PF NUMBER", "PF"]
    )

    result["DATE"] = find_value(
        ["DATE"]
    )

    result["AGE"] = find_value(
        ["AGE"]
    )

    result["GENDER"] = find_value(
        ["GENDER", "SEX"]
    )

    result["OPD NO."] = find_value(
        ["OPD NO", "OPD NUMBER"]
    )

    result["RE-VISIT"] = find_value(
        ["RE-VISIT", "REVISIT", "RE VISIT"]
    )

    result["STATUS"] = find_value(
        ["STATUS"]
    )

    result["DIAGNOSIS"] = find_value(
        ["DIAGNOSIS", "DIAGNOSES"]
    )

    result["CATEGORY"] = find_value(
        ["CATEGORY"]
    ) or "Student"

    return result


# ---------------------------------------------------------
# Validation result display
# ---------------------------------------------------------

def display_validation_result(
    checked,
    allow_save=True,
    save_button_label="💾 Save Validated Record"
):

    if checked is None or checked.empty:
        return False

    result = checked.iloc[0]

    overall = result.get(
        "OVERALL_RESULT",
        "Unknown"
    )

    needs_action = bool(
        result.get(
            "NEEDS_ACTION",
            False
        )
    )

    st.subheader(
        "Validation Result"
    )

    if not needs_action:

        st.success(
            f"Overall result: {overall}. "
            "No actionable validation finding was detected."
        )

    else:

        st.warning(
            f"Overall result: {overall}. "
            "This record needs review before being treated as clean."
        )

    result_columns = [
        ("AGE_RESULT", "Age"),
        ("DATE_RESULT", "Date"),
        ("GENDER_RESULT", "Gender"),
        ("STATUS_RESULT", "Status"),
        ("DIAGNOSIS_RESULT", "Diagnosis"),
        ("REVISIT_RESULT", "RE-VISIT"),
        ("REGISTRATION_RESULT", "Registration No."),
        ("PF_RESULT", "PF No."),
        ("OPD_RESULT", "OPD No."),
        ("EXACT_DUPLICATE_RESULT", "Exact duplicate"),
        ("OBSERVATION_RESULT", "Observation No.")
    ]

    result_rows = []

    for column, label in result_columns:

        if column in checked.columns:

            result_rows.append({
                "Field": label,
                "Validation result": result[column]
            })

    if result_rows:

        st.dataframe(
            pd.DataFrame(result_rows),
            use_container_width=True,
            hide_index=True
        )

    if allow_save and not needs_action:

        return st.button(
            save_button_label,
            type="primary",
            use_container_width=True
        )

    if needs_action:

        st.info(
            "Review and correct the flagged values, then "
            "validate the record again before saving."
        )

    return False


# ---------------------------------------------------------
# MAIN DATA LOAD
# ---------------------------------------------------------

try:

    raw_df = load_data()

    patient_df = get_patient_records(
        raw_df
    )

    validation_df = validate_records(
        patient_df
    )

except Exception as e:

    st.error(
        f"Unable to load or validate the outpatient data: {e}"
    )

    st.stop()


# ---------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------

st.sidebar.title(
    "📊 Data Quality System"
)

page = st.sidebar.radio(
    "Navigate to",
    [
        "Overview",
        "Data Quality Summary",
        "Completeness",
        "Validity & Consistency",
        "Identifier Validation",
        "Duplicates & Structural Records",
        "Review Queue",
        "👤 Patient Data Entry",
        "How to Use"
    ]
)


# =========================================================
# OVERVIEW
# =========================================================

if page == "Overview":

    st.title(
        "Outpatient Data Quality Improvement System"
    )

    st.markdown(
        """
        This system assesses the quality of outpatient
        medical records by checking completeness, validity,
        consistency, identifiers, and possible duplicates.

        It identifies records that may require review,
        correction, or standardization before the data
        is used for analysis or reporting.
        """
    )

    st.info(
        "The system validates patient records using predefined "
        "data-quality rules. It does not automatically alter "
        "the original records."
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total records",
            f"{len(raw_df):,}"
        )

    with col2:
        st.metric(
            "Patient records",
            f"{len(patient_df):,}"
        )

    with col3:
        st.metric(
            "Structural / non-patient",
            f"{len(raw_df) - len(patient_df):,}"
        )

    saved_df = load_saved_records()

    with col4:
        st.metric(
            "New records saved",
            f"{len(saved_df):,}"
        )

    st.divider()

    st.subheader(
        "What does the system check?"
    )

    checks = pd.DataFrame({
        "Area": [
            "Completeness",
            "Validity",
            "Consistency",
            "Identifiers",
            "Duplicates"
        ],
        "Purpose": [
            "Checks whether expected information has been recorded.",
            "Checks whether values follow expected formats or ranges.",
            "Checks whether values follow agreed categories and conventions.",
            "Checks category-specific registration and PF requirements.",
            "Identifies exact duplicates and repeated observation numbers."
        ]
    })

    st.dataframe(
        checks,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# DATA QUALITY SUMMARY
# =========================================================

elif page == "Data Quality Summary":

    st.title(
        "📊 Data Quality Summary"
    )

    actionable = validation_df[
        "NEEDS_ACTION"
    ].sum()

    no_action = (
        len(validation_df)
        - actionable
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Patient records",
            f"{len(validation_df):,}"
        )

    with col2:
        st.metric(
            "Require action / review",
            f"{actionable:,}"
        )

    with col3:
        st.metric(
            "No actionable finding",
            f"{no_action:,}"
        )

    st.divider()

    st.subheader(
        "Overall validation results"
    )

    summary = (
        validation_df[
            "OVERALL_RESULT"
        ]
        .value_counts()
        .rename_axis("Result")
        .reset_index(
            name="Records"
        )
    )

    summary["Percentage"] = (
        summary["Records"]
        / len(validation_df)
        * 100
    ).round(2)

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# COMPLETENESS
# =========================================================

elif page == "Completeness":

    st.title(
        "📝 Completeness"
    )

    st.markdown(
        """
        Completeness describes whether expected information
        has been recorded.

        A missing value is only treated as an actionable
        issue where the field is considered required or
        expected under the validation rules.
        """
    )

    fields = [
        "DATE",
        "DIAGNOSIS",
        "AGE",
        "GENDER",
        "STATUS",
        "CATEGORY",
        "PATIENT NAME"
    ]

    completeness = []

    for field in fields:

        if field not in validation_df.columns:
            continue

        missing = (
            validation_df[field].isna()
            |
            validation_df[field]
            .astype("string")
            .str.strip()
            .eq("")
        ).sum()

        complete = (
            len(validation_df)
            - missing
        )

        completeness.append({
            "Field": field,
            "Complete": complete,
            "Missing": missing,
            "Completeness (%)": round(
                complete
                / len(validation_df)
                * 100,
                2
            )
        })

    completeness_df = pd.DataFrame(
        completeness
    )

    st.dataframe(
        completeness_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# VALIDITY & CONSISTENCY
# =========================================================

elif page == "Validity & Consistency":

    st.title(
        "🔍 Validity & Consistency"
    )

    st.markdown(
        """
        These checks determine whether values follow the
        agreed validation rules.

        The system does not automatically correct ambiguous
        values. Records requiring human verification are
        sent to the review queue.
        """
    )

    result_columns = {
        "AGE_RESULT": "Age",
        "DATE_RESULT": "Date",
        "GENDER_RESULT": "Gender",
        "STATUS_RESULT": "Status",
        "DIAGNOSIS_RESULT": "Diagnosis",
        "REVISIT_RESULT": "RE-VISIT"
    }

    rows = []

    for column, field in result_columns.items():

        if column not in validation_df.columns:
            continue

        counts = (
            validation_df[column]
            .value_counts()
            .to_dict()
        )

        for result, count in counts.items():

            rows.append({
                "Field": field,
                "Result": result,
                "Records": count
            })

    validity_df = pd.DataFrame(
        rows
    )

    st.dataframe(
        validity_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# IDENTIFIER VALIDATION
# =========================================================

elif page == "Identifier Validation":

    st.title(
        "🪪 Identifier & Cross-field Validation"
    )

    st.markdown(
        """
        Identifier rules depend on patient category.

        **Student:** Registration No. expected.

        **Employee, Dependant and Private Citizen:**
        PF No. expected.

        **OPD No.:** treated as optional because it may be
        issued during a patient's first outpatient visit and
        not necessarily repeated on subsequent visits.
        """
    )

    identifier_columns = [
        "REGISTRATION_RESULT",
        "PF_RESULT",
        "OPD_RESULT"
    ]

    rows = []

    for column in identifier_columns:

        if column not in validation_df.columns:
            continue

        counts = (
            validation_df[column]
            .value_counts()
            .to_dict()
        )

        for result, count in counts.items():

            rows.append({
                "Identifier": column.replace(
                    "_RESULT",
                    ""
                ),
                "Result": result,
                "Records": count
            })

    identifier_df = pd.DataFrame(
        rows
    )

    st.dataframe(
        identifier_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# DUPLICATES
# =========================================================

elif page == "Duplicates & Structural Records":

    st.title(
        "♻️ Duplicates & Structural Records"
    )

    raw_structural = (
        len(raw_df)
        - len(patient_df)
    )

    exact_duplicates = (
        validation_df[
            "EXACT_DUPLICATE_RESULT"
        ]
        .eq("Review")
        .sum()
    )

    repeated_observations = (
        validation_df[
            "OBSERVATION_RESULT"
        ]
        .eq("Review")
        .sum()
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Structural / non-patient records",
            f"{raw_structural:,}"
        )

    with col2:

        st.metric(
            "Exact duplicate records",
            f"{exact_duplicates:,}"
        )

    with col3:

        st.metric(
            "Repeated observation records",
            f"{repeated_observations:,}"
        )

    st.info(
        "Repeated observation numbers are not automatically "
        "treated as duplicate patients. They require review "
        "because they may represent multiple service transactions."
    )


# =========================================================
# REVIEW QUEUE
# =========================================================

elif page == "Review Queue":

    st.title(
        "⚠️ Review Queue"
    )

    st.markdown(
        """
        These records contain at least one actionable
        validation finding.

        **Review does not mean the record is definitely wrong.**
        The original source record should be checked before
        making a correction.
        """
    )

    review_df = validation_df[
        validation_df["NEEDS_ACTION"]
    ].copy()

    st.metric(
        "Records requiring action",
        f"{len(review_df):,}"
    )

    display_columns = [
        "CATEGORY",
        "PT NO.",
        "PATIENT NAME",
        "DATE",
        "AGE",
        "GENDER",
        "STATUS",
        "DIAGNOSIS",
        "RE-VISIT",
        "AGE_RESULT",
        "GENDER_RESULT",
        "STATUS_RESULT",
        "DIAGNOSIS_RESULT",
        "REVISIT_RESULT",
        "OVERALL_RESULT",
        "ACTIONABLE_FLAG_COUNT"
    ]

    available_columns = [
        column
        for column in display_columns
        if column in review_df.columns
    ]

    st.dataframe(
        review_df[
            available_columns
        ],
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# PATIENT DATA ENTRY
# =========================================================

elif page == "👤 Patient Data Entry":

    st.title(
        "👤 Patient Data Entry"
    )

    st.markdown(
        """
        Add outpatient records directly into the system,
        upload existing Excel/CSV records, or upload a
        photograph of a medical record for OCR extraction.

        **Every record goes through validation before it is saved.**
        """

    )

    tab_manual, tab_file, tab_photo, tab_saved = st.tabs(
        [
            "📝 Manual Entry",
            "📄 Upload Excel / CSV",
            "📷 Upload Photo",
            "💾 Saved Records"
        ]
    )


    # =====================================================
    # MANUAL ENTRY
    # =====================================================

    with tab_manual:

        st.subheader(
            "Enter a new patient"
        )

        st.info(
            "Fill in the available information. Missing values can "
            "be reviewed and corrected before saving."
        )

        with st.form(
            "manual_patient_form",
            clear_on_submit=False
        ):

            col1, col2, col3 = st.columns(3)

            with col1:

                pt_no = st.text_input(
                    "PT No. *"
                )

                category = st.selectbox(
                    "Category *",
                    [
                        "Student",
                        "Employee",
                        "Dependant",
                        "Private Citizen"
                    ]
                )

                patient_name = st.text_input(
                    "Patient Name *"
                )

                registration_no = st.text_input(
                    "Registration No.",
                    help="Expected for Students."
                )

            with col2:

                pf_no = st.text_input(
                    "PF No.",
                    help=(
                        "Expected for Employees, Dependants "
                        "and Private Citizens."
                    )
                )

                date = st.date_input(
                    "Date *"
                )

                age = st.text_input(
                    "Age",
                    help="Enter a numeric age."
                )

                gender = st.selectbox(
                    "Gender",
                    [
                        "",
                        "F",
                        "M",
                        "m"
                    ]
                )

            with col3:

                opd_no = st.text_input(
                    "OPD No.",
                    help="Optional."
                )

                revisit = st.selectbox(
                    "RE-VISIT",
                    [
                        "",
                        "RE-VISIT",
                        "RE-VISIST"
                    ]
                )

                status = st.selectbox(
                    "Status",
                    [
                        "",
                        "Pharmacy",
                        "Triage",
                        "Lab",
                        "Lab Results",
                        "Imaging"
                    ]
                )

                diagnosis = st.text_input(
                    "Diagnosis"
                )

            validate_button = st.form_submit_button(
                "🔍 Validate Patient",
                type="primary",
                use_container_width=True
            )

        if validate_button:

            if not pt_no.strip():

                st.error(
                    "PT No. is required."
                )

            elif not patient_name.strip():

                st.error(
                    "Patient Name is required."
                )

            else:

                record = create_record(
                    pt_no=pt_no,
                    category=category,
                    patient_name=patient_name,
                    registration_no=registration_no,
                    pf_no=pf_no,
                    date=date,
                    age=age,
                    gender=gender,
                    opd_no=opd_no,
                    revisit=revisit,
                    status=status,
                    diagnosis=diagnosis
                )

                entry_df = pd.DataFrame(
                    [record]
                )

                try:

                    checked = validate_records(
                        entry_df
                    )

                    st.session_state.last_entry_validation = checked

                except Exception as e:

                    st.session_state.last_entry_validation = None

                    st.error(
                        f"Validation failed: {e}"
                    )

        checked = st.session_state.last_entry_validation

        if checked is not None:

            st.divider()

            save_clicked = display_validation_result(
                checked,
                allow_save=True,
                save_button_label="💾 Save Patient Record"
            )

            st.subheader(
                "Review entered values"
            )

            entered_columns = [
                "CATEGORY",
                "PT NO.",
                "PATIENT NAME",
                "REGISTRATION NO.",
                "PF NO.",
                "DATE",
                "DIAGNOSIS",
                "STATUS",
                "AGE",
                "GENDER",
                "OPD NO.",
                "RE-VISIT"
            ]

            available = [
                c
                for c in entered_columns
                if c in checked.columns
            ]

            entered_view = checked[
                available
            ].T.reset_index()

            entered_view.columns = [
                "Field",
                "Value"
            ]

            st.dataframe(
                entered_view,
                use_container_width=True,
                hide_index=True
            )

            if save_clicked:

                success, count = save_records_to_disk(
                    checked
                )

                if success:

                    st.session_state.last_saved_count = count

                    st.success(
                        "✅ Patient record saved successfully."
                    )

                    st.info(
                        f"Saved permanently to: "
                        f"{os.path.basename(NEW_RECORDS_PATH)}"
                    )

                    st.session_state.last_entry_validation = None

            elif (
                checked is not None
                and bool(
                    checked.iloc[0].get(
                        "NEEDS_ACTION",
                        False
                    )
                )
            ):

                st.warning(
                    "Correct the flagged information in the "
                    "form above and click Validate Patient again."
                )


    # =====================================================
    # EXCEL / CSV UPLOAD
    # =====================================================

    with tab_file:

        st.subheader(
            "📄 Upload Existing Records"
        )

        st.markdown(
            """
            Upload an Excel or CSV file containing outpatient
            records. The system will display the records before
            validation so that missing information can be filled
            in or corrected.
            """
        )

        uploaded_file = st.file_uploader(
            "Choose an Excel or CSV file",
            type=[
                "csv",
                "xlsx",
                "xls"
            ],
            key="patient_file_upload"
        )

        if uploaded_file is not None:

            try:

                uploaded_df = read_uploaded_file(
                    uploaded_file
                )

                uploaded_df = normalize_uploaded_columns(
                    uploaded_df
                )

                # Remove completely empty rows
                uploaded_df = uploaded_df.dropna(
                    how="all"
                ).reset_index(
                    drop=True
                )

                st.session_state.uploaded_data = uploaded_df

                st.success(
                    f"Loaded {len(uploaded_df):,} records."
                )

            except Exception as e:

                st.error(
                    f"Could not read the uploaded file: {e}"
                )

        uploaded_df = st.session_state.uploaded_data

        if uploaded_df is not None and not uploaded_df.empty:

            st.divider()

            st.subheader(
                "1. Review and edit the uploaded records"
            )

            st.caption(
                "You can click cells below and fill missing values "
                "before validation."
            )

            editable_columns = [
                c
                for c in SOURCE_COLUMNS
                if c in uploaded_df.columns
            ]

            edited_df = st.data_editor(
                uploaded_df[
                    editable_columns
                ],
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                key="uploaded_editor"
            )

            st.session_state.uploaded_data = edited_df

            st.divider()

            col1, col2 = st.columns(2)

            with col1:

                validate_upload = st.button(
                    "🔍 Validate Uploaded Records",
                    type="primary",
                    use_container_width=True
                )

            with col2:

                if st.button(
                    "🗑️ Clear Upload",
                    use_container_width=True
                ):

                    st.session_state.uploaded_data = None
                    st.session_state.uploaded_validation = None

                    st.rerun()

            if validate_upload:

                try:

                    checked_upload = validate_records(
                        edited_df
                    )

                    st.session_state.uploaded_validation = (
                        checked_upload
                    )

                except Exception as e:

                    st.error(
                        f"Validation failed: {e}"
                    )

            checked_upload = (
                st.session_state.uploaded_validation
            )

            if checked_upload is not None:

                st.divider()

                st.subheader(
                    "2. Validation results"
                )

                actionable_upload = (
                    checked_upload[
                        "NEEDS_ACTION"
                    ].sum()
                )

                clean_upload = (
                    len(checked_upload)
                    - actionable_upload
                )

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "Uploaded records",
                        f"{len(checked_upload):,}"
                    )

                with c2:

                    st.metric(
                        "No actionable finding",
                        f"{clean_upload:,}"
                    )

                with c3:

                    st.metric(
                        "Require review",
                        f"{actionable_upload:,}"
                    )

                st.dataframe(
                    checked_upload[
                        [
                            c for c in [
                                "PT NO.",
                                "PATIENT NAME",
                                "DATE",
                                "AGE",
                                "GENDER",
                                "DIAGNOSIS",
                                "OVERALL_RESULT",
                                "ACTIONABLE_FLAG_COUNT"
                            ]
                            if c in checked_upload.columns
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True
                )

                if actionable_upload == 0:

                    st.success(
                        "All uploaded records passed the "
                        "current actionable validation checks."
                    )

                    if st.button(
                        "💾 Save All Validated Records",
                        type="primary",
                        use_container_width=True
                    ):

                        success, count = save_records_to_disk(
                            checked_upload
                        )

                        if success:

                            st.success(
                                f"✅ {count:,} records were "
                                "saved successfully."
                            )

                            st.session_state.uploaded_data = None
                            st.session_state.uploaded_validation = None

                else:

                    st.warning(
                        f"{actionable_upload:,} record(s) require "
                        "review before they can be saved."
                    )

                    st.info(
                        "Return to the editable table above, "
                        "correct the missing or invalid values, "
                        "then validate the upload again."
                    )


    # =====================================================
    # PHOTO / OCR
    # =====================================================

    with tab_photo:

        st.subheader(
            "📷 Upload a Medical Record Photo"
        )

        st.markdown(
            """
            Upload a clear photograph or scanned image of a
            patient record.

            The system will attempt to read the text using OCR.
            Because handwritten medical records can be difficult
            for OCR systems to interpret, the extracted information
            must be reviewed and corrected before saving.
            """
        )

        if not TESSERACT_AVAILABLE:

            st.warning(
                "OCR is currently unavailable because "
                "`pytesseract` is not installed. You can still "
                "use Manual Entry and Excel/CSV Upload."
            )

        photo = st.file_uploader(
            "Upload patient record photo",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp"
            ],
            key="patient_photo_upload"
        )

        if photo is not None:

            if PIL_AVAILABLE:

                image = Image.open(
                    photo
                )

                st.image(
                    image,
                    caption="Uploaded medical record",
                    use_container_width=True
                )

            if st.button(
                "🔎 Extract Text from Photo",
                type="primary",
                use_container_width=True
            ):

                try:

                    ocr_text = perform_ocr(
                        photo
                    )

                    st.session_state.ocr_text = (
                        ocr_text
                    )

                    st.session_state.ocr_record = (
                        extract_ocr_fields(
                            ocr_text
                        )
                    )

                    st.success(
                        "OCR extraction completed. "
                        "Please review the extracted information."
                    )

                except Exception as e:

                    st.error(
                        f"OCR could not process the image: {e}"
                    )

        if st.session_state.ocr_text:

            st.divider()

            st.subheader(
                "1. OCR text"
            )

            st.text_area(
                "Text detected in the image",
                value=st.session_state.ocr_text,
                height=250,
                disabled=True
            )

        if st.session_state.ocr_record:

            st.divider()

            st.subheader(
                "2. Review and correct extracted information"
            )

            ocr = st.session_state.ocr_record

            with st.form(
                "ocr_review_form"
            ):

                c1, c2, c3 = st.columns(3)

                with c1:

                    ocr_pt_no = st.text_input(
                        "PT No.",
                        value=ocr.get(
                            "PT NO.",
                            ""
                        )
                    )

                    ocr_name = st.text_input(
                        "Patient Name",
                        value=ocr.get(
                            "PATIENT NAME",
                            ""
                        )
                    )

                    ocr_category = st.selectbox(
                        "Category",
                        [
                            "Student",
                            "Employee",
                            "Dependant",
                            "Private Citizen"
                        ],
                        index=(
                            [
                                "Student",
                                "Employee",
                                "Dependant",
                                "Private Citizen"
                            ].index(
                                ocr.get(
                                    "CATEGORY",
                                    "Student"
                                )
                            )
                            if ocr.get(
                                "CATEGORY",
                                "Student"
                            ) in [
                                "Student",
                                "Employee",
                                "Dependant",
                                "Private Citizen"
                            ]
                            else 0
                        )
                    )

                    ocr_registration = st.text_input(
                        "Registration No.",
                        value=ocr.get(
                            "REGISTRATION NO.",
                            ""
                        )
                    )

                with c2:

                    ocr_pf = st.text_input(
                        "PF No.",
                        value=ocr.get(
                            "PF NO.",
                            ""
                        )
                    )

                    ocr_date = st.text_input(
                        "Date",
                        value=ocr.get(
                            "DATE",
                            ""
                        )
                    )

                    ocr_age = st.text_input(
                        "Age",
                        value=ocr.get(
                            "AGE",
                            ""
                        )
                    )

                    ocr_gender = st.selectbox(
                        "Gender",
                        [
                            "",
                            "F",
                            "M",
                            "m"
                        ],
                        index=(
                            [
                                "",
                                "F",
                                "M",
                                "m"
                            ].index(
                                ocr.get(
                                    "GENDER",
                                    ""
                                )
                            )
                            if ocr.get(
                                "GENDER",
                                ""
                            ) in [
                                "",
                                "F",
                                "M",
                                "m"
                            ]
                            else 0
                        )
                    )

                with c3:

                    ocr_opd = st.text_input(
                        "OPD No.",
                        value=ocr.get(
                            "OPD NO.",
                            ""
                        )
                    )

                    ocr_revisit = st.selectbox(
                        "RE-VISIT",
                        [
                            "",
                            "RE-VISIT",
                            "RE-VISIST"
                        ],
                        index=(
                            [
                                "",
                                "RE-VISIT",
                                "RE-VISIST"
                            ].index(
                                ocr.get(
                                    "RE-VISIT",
                                    ""
                                )
                            )
                            if ocr.get(
                                "RE-VISIT",
                                ""
                            ) in [
                                "",
                                "RE-VISIT",
                                "RE-VISIST"
                            ]
                            else 0
                        )
                    )

                    ocr_status = st.text_input(
                        "Status",
                        value=ocr.get(
                            "STATUS",
                            ""
                        )
                    )

                    ocr_diagnosis = st.text_input(
                        "Diagnosis",
                        value=ocr.get(
                            "DIAGNOSIS",
                            ""
                        )
                    )

                review_ocr = st.form_submit_button(
                    "🔍 Validate Extracted Record",
                    type="primary",
                    use_container_width=True
                )

            if review_ocr:

                if not ocr_pt_no.strip():

                    st.error(
                        "PT No. is missing. "
                        "Please enter it before validation."
                    )

                elif not ocr_name.strip():

                    st.error(
                        "Patient Name is missing. "
                        "Please enter it before validation."
                    )

                else:

                    try:

                        ocr_record = create_record(
                            pt_no=ocr_pt_no,
                            category=ocr_category,
                            patient_name=ocr_name,
                            registration_no=ocr_registration,
                            pf_no=ocr_pf,
                            date=ocr_date,
                            age=ocr_age,
                            gender=ocr_gender,
                            opd_no=ocr_opd,
                            revisit=ocr_revisit,
                            status=ocr_status,
                            diagnosis=ocr_diagnosis,
                            source_file=photo.name,
                            source_sheet="Photo OCR"
                        )

                        ocr_df = pd.DataFrame(
                            [ocr_record]
                        )

                        checked_ocr = validate_records(
                            ocr_df
                        )

                        st.session_state.ocr_record = (
                            checked_ocr.iloc[0].to_dict()
                        )

                        st.success(
                            "Record validated. Review the results below."
                        )

                    except Exception as e:

                        st.error(
                            f"Validation failed: {e}"
                        )

            # -------------------------------------------------
            # OCR validation result
            # -------------------------------------------------

            current_ocr = st.session_state.ocr_record

            if current_ocr:

                # Check whether this is already validation output
                if "OVERALL_RESULT" in current_ocr:

                    st.divider()

                    ocr_checked_df = pd.DataFrame(
                        [current_ocr]
                    )

                    save_ocr = display_validation_result(
                        ocr_checked_df,
                        allow_save=True,
                        save_button_label="💾 Save OCR Record"
                    )

                    if save_ocr:

                        success, count = save_records_to_disk(
                            ocr_checked_df
                        )

                        if success:

                            st.success(
                                "✅ OCR-extracted patient record "
                                "saved successfully."
                            )

                            st.session_state.ocr_text = ""
                            st.session_state.ocr_record = None


    # =====================================================
    # SAVED RECORDS
    # =====================================================

    with tab_saved:

        st.subheader(
            "💾 Permanently Saved Records"
        )

        saved_df = load_saved_records()

        if saved_df.empty:

            st.info(
                "No records have been permanently saved yet."
            )

        else:

            st.metric(
                "Saved records",
                f"{len(saved_df):,}"
            )

            st.dataframe(
                saved_df,
                use_container_width=True,
                hide_index=True
            )

            csv_data = saved_df.to_csv(
                index=False
            ).encode(
                "utf-8"
            )

            st.download_button(
                "⬇️ Download Saved Records",
                data=csv_data,
                file_name="new_outpatient_records.csv",
                mime="text/csv",
                use_container_width=True
            )

            st.caption(
                f"Storage file: {NEW_RECORDS_PATH}"
            )


# =========================================================
# HOW TO USE
# =========================================================

elif page == "How to Use":

    st.title(
        "📖 How to Use the Validation System"
    )

    st.subheader(
        "Validation key"
    )

    key = pd.DataFrame({
        "Result": [
            "Pass",
            "Review",
            "Invalid",
            "Standardize",
            "Context-dependent",
            "Informational",
            "Missing"
        ],
        "Meaning": [
            "The record meets the validation rule.",
            "The value is unusual or potentially problematic and should be checked.",
            "The value clearly violates the expected format or range.",
            "The value is conceptually usable but should be converted to the standard format.",
            "Interpretation depends on the service context and is not automatically an error.",
            "No correction is required under the current rule.",
            "Expected information was not recorded."
        ],
        "Action": [
            "No immediate action.",
            "Check the original record.",
            "Verify and correct after checking the source.",
            "Standardize while preserving the original value.",
            "Interpret using the relevant service context.",
            "No correction required.",
            "Check whether the information can be recovered."
        ]
    })

    st.dataframe(
        key,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader(
        "New Patient workflow"
    )

    st.markdown(
        """
        ### Manual entry

        **Enter patient → Validate → Review → Save**

        ### Excel / CSV

        **Upload → Edit missing/incorrect values → Validate → Save**

        ### Photo

        **Upload photo → OCR → Review extracted information →
        Correct if necessary → Validate → Save**

        ### Saved records

        Records saved through the Patient Data Entry page are
        stored separately in `new_outpatient_records.csv`.

        The original `outpatient_merged.csv` is not overwritten.
        """
    )

    st.divider()

    st.subheader(
        "Important principle"
    )

    st.warning(
        "The validation system supports data-quality review. "
        "It does not replace verification against the original "
        "medical record and does not automatically overwrite "
        "source data."
    )
