import streamlit as st
import pandas as pd
import sys
import os

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

DATA_PATH = os.path.join(
    os.path.dirname(__file__),
    "outpatient_merged.csv"
)

# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

@st.cache_data
def load_data():
    return pd.read_csv(DATA_PATH)

# ---------------------------------------------------------
# Patient record definition
# ---------------------------------------------------------

def get_patient_records(df):
    structural_pt_values = [
        "Patient No",
        "PATIENT NO",
        "PATIENT NUMBER"
    ]

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
    return validate_outpatient_data(df.copy())

# ---------------------------------------------------------
# Session state for newly entered records
# ---------------------------------------------------------

if "new_records" not in st.session_state:
    st.session_state.new_records = []

if "last_entry_validation" not in st.session_state:
    st.session_state.last_entry_validation = None

# ---------------------------------------------------------
# Load and validate existing data
# ---------------------------------------------------------

try:
    raw_df = load_data()
    patient_df = get_patient_records(raw_df)
    validation_df = validate_records(patient_df)

except Exception as e:
    st.error(
        f"Unable to load or validate the outpatient data: {e}"
    )
    st.stop()

# ---------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------

st.sidebar.title("📊 Data Quality System")

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
        "➕ New Record",
        "How to Use"
    ]
)

# ---------------------------------------------------------
# Overview
# ---------------------------------------------------------

if page == "Overview":

    st.title("Outpatient Data Quality Improvement System")

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

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total records", f"{len(raw_df):,}")

    with col2:
        st.metric("Patient records", f"{len(patient_df):,}")

    with col3:
        st.metric(
            "Structural / non-patient",
            f"{len(raw_df) - len(patient_df):,}"
        )

    st.divider()

    st.subheader("What does the system check?")

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

# ---------------------------------------------------------
# Data Quality Summary
# ---------------------------------------------------------

elif page == "Data Quality Summary":

    st.title("📊 Data Quality Summary")

    actionable = validation_df["NEEDS_ACTION"].sum()
    no_action = len(validation_df) - actionable

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Patient records", f"{len(validation_df):,}")

    with col2:
        st.metric("Require action / review", f"{actionable:,}")

    with col3:
        st.metric("No actionable finding", f"{no_action:,}")

    st.divider()

    st.subheader("Overall validation results")

    summary = (
        validation_df["OVERALL_RESULT"]
        .value_counts()
        .rename_axis("Result")
        .reset_index(name="Records")
    )

    summary["Percentage"] = (
        summary["Records"] / len(validation_df) * 100
    ).round(2)

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )

# ---------------------------------------------------------
# Completeness
# ---------------------------------------------------------

elif page == "Completeness":

    st.title("📝 Completeness")

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
        missing = (
            validation_df[field].isna()
            | validation_df[field].astype("string").str.strip().eq("")
        ).sum()

        complete = len(validation_df) - missing

        completeness.append({
            "Field": field,
            "Complete": complete,
            "Missing": missing,
            "Completeness (%)": round(
                complete / len(validation_df) * 100,
                2
            )
        })

    completeness_df = pd.DataFrame(completeness)

    st.dataframe(
        completeness_df,
        use_container_width=True,
        hide_index=True
    )

# ---------------------------------------------------------
# Validity & Consistency
# ---------------------------------------------------------

elif page == "Validity & Consistency":

    st.title("🔍 Validity & Consistency")

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
        counts = validation_df[column].value_counts().to_dict()

        for result, count in counts.items():
            rows.append({
                "Field": field,
                "Result": result,
                "Records": count
            })

    validity_df = pd.DataFrame(rows)

    st.dataframe(
        validity_df,
        use_container_width=True,
        hide_index=True
    )

# ---------------------------------------------------------
# Identifier Validation
# ---------------------------------------------------------

elif page == "Identifier Validation":

    st.title("🪪 Identifier & Cross-field Validation")

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
        counts = validation_df[column].value_counts().to_dict()

        for result, count in counts.items():
            rows.append({
                "Identifier": column.replace("_RESULT", ""),
                "Result": result,
                "Records": count
            })

    identifier_df = pd.DataFrame(rows)

    st.dataframe(
        identifier_df,
        use_container_width=True,
        hide_index=True
    )

# ---------------------------------------------------------
# Duplicates & Structural Records
# ---------------------------------------------------------

elif page == "Duplicates & Structural Records":

    st.title("♻️ Duplicates & Structural Records")

    raw_structural = len(raw_df) - len(patient_df)

    exact_duplicates = (
        validation_df["EXACT_DUPLICATE_RESULT"]
        .eq("Review")
        .sum()
    )

    repeated_observations = (
        validation_df["OBSERVATION_RESULT"]
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

# ---------------------------------------------------------
# Review Queue
# ---------------------------------------------------------

elif page == "Review Queue":

    st.title("⚠️ Review Queue")

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
        review_df[available_columns],
        use_container_width=True,
        hide_index=True
    )

# ---------------------------------------------------------
# New Record
# ---------------------------------------------------------

elif page == "➕ New Record":

    st.title("➕ Add and Validate a New Outpatient Record")

    st.markdown(
        """
        Enter a new outpatient record below. The same validation
        rules used for the existing dataset will be applied.

        **Important:** validation does not automatically guess or
        overwrite medical information. If a value is flagged,
        verify it against the original record before saving it.
        """
    )

    st.info(
        "This first version stores newly entered records only in "
        "the current session. It does not modify outpatient_merged.csv."
    )

    with st.form("new_record_form", clear_on_submit=False):

        st.subheader("Patient information")

        col1, col2, col3 = st.columns(3)

        with col1:
            pt_no = st.text_input("PT No. *")
            category = st.selectbox(
                "Category *",
                [
                    "Student",
                    "Employee",
                    "Dependant",
                    "Private Citizen"
                ]
            )
            patient_name = st.text_input("Patient Name *")
            registration_no = st.text_input(
                "Registration No.",
                help="Expected for Students."
            )

        with col2:
            pf_no = st.text_input(
                "PF No.",
                help="Expected for Employees, Dependants and Private Citizens."
            )
            date = st.date_input("Date *")
            age = st.text_input(
                "Age",
                help="Enter a numeric age. Use 0 only when it genuinely represents an infant."
            )
            gender = st.selectbox(
                "Gender",
                ["", "F", "M", "m"]
            )

        with col3:
            opd_no = st.text_input(
                "OPD No.",
                help="Optional."
            )
            revisit = st.selectbox(
                "RE-VISIT",
                ["", "RE-VISIT", "RE-VISIST"]
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
            diagnosis = st.text_input("Diagnosis")

        submitted = st.form_submit_button(
            "🔍 Validate Record",
            type="primary",
            use_container_width=True
        )

    if submitted:

        if not pt_no.strip():
            st.error("PT No. is required for a patient record.")
        elif not patient_name.strip():
            st.error("Patient Name is required.")
        else:

            # Build a record using the same source-column names
            # expected by the validation engine.
            record = {
                "S/NO.": "",
                "OBSERVATION NO.": "",
                "CATEGORY": category,
                "PT NO.": pt_no.strip(),
                "PATIENT NAME": patient_name.strip(),
                "REGISTRATION NO.": registration_no.strip() or pd.NA,
                "PF NO.": pf_no.strip() or pd.NA,
                "DATE": date.strftime("%Y-%m-%d"),
                "DIAGNOSIS": diagnosis.strip() or pd.NA,
                "STATUS": status.strip() or pd.NA,
                "AGE": age.strip() or pd.NA,
                "GENDER": gender.strip() or pd.NA,
                "OPD NO.": opd_no.strip() or pd.NA,
                "RE-VISIT": revisit.strip() or pd.NA,
                "NO.": "",
                ">60": "",
                "SOURCE_FILE": "Direct Entry",
                "SOURCE_SHEET": "New Record"
            }

            entry_df = pd.DataFrame([record])

            try:
                checked = validate_records(entry_df)
                st.session_state.last_entry_validation = checked
            except Exception as e:
                st.session_state.last_entry_validation = None
                st.error(f"Validation failed: {e}")

    # -----------------------------------------------------
    # Show validation result
    # -----------------------------------------------------

    checked = st.session_state.last_entry_validation

    if checked is not None and not checked.empty:

        st.divider()
        st.subheader("Validation result")

        result = checked.iloc[0]

        overall = result.get("OVERALL_RESULT", "Unknown")
        needs_action = bool(result.get("NEEDS_ACTION", False))

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

        st.dataframe(
            pd.DataFrame(result_rows),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Review the entered values")

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

        entered_view = checked[
            [c for c in entered_columns if c in checked.columns]
        ].T.reset_index()

        entered_view.columns = ["Field", "Value"]

        st.dataframe(
            entered_view,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "If a field is flagged, verify it against the original "
            "medical record. This system intentionally does not "
            "silently correct ambiguous values."
        )

        if not needs_action:

            if st.button(
                "💾 Save this validated record to session",
                type="primary"
            ):
                st.session_state.new_records.append(
                    checked.iloc[0].to_dict()
                )
                st.success(
                    "Record added to the current session. "
                    "It has not modified the original dataset."
                )

        else:
            st.info(
                "Correct the flagged value above and validate the "
                "record again before saving it."
            )

    # -----------------------------------------------------
    # Session records
    # -----------------------------------------------------

    st.divider()
    st.subheader("Records added during this session")

    if st.session_state.new_records:

        session_df = pd.DataFrame(
            st.session_state.new_records
        )

        session_display_columns = [
            "CATEGORY",
            "DATE",
            "AGE",
            "GENDER",
            "STATUS",
            "DIAGNOSIS",
            "RE-VISIT",
            "OVERALL_RESULT"
        ]

        session_display_columns = [
            c for c in session_display_columns
            if c in session_df.columns
        ]

        st.dataframe(
            session_df[session_display_columns],
            use_container_width=True,
            hide_index=True
        )

        csv = session_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Download validated new records",
            data=csv,
            file_name="validated_new_outpatient_records.csv",
            mime="text/csv",
            use_container_width=True
        )

        if st.button("Clear session records"):
            st.session_state.new_records = []
            st.session_state.last_entry_validation = None
            st.rerun()

    else:
        st.info("No new records have been saved in this session yet.")

# ---------------------------------------------------------
# How to Use
# ---------------------------------------------------------

elif page == "How to Use":

    st.title("📖 How to Use the Validation System")

    st.subheader("Validation key")

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

    st.subheader("New Record workflow")

    st.markdown(
        """
        **1. Enter the record → 2. Validate → 3. Review flagged
        fields → 4. Correct using the original source → 5. Validate
        again → 6. Save only after verification.**

        Records saved through the New Record page are kept in the
        current session and can be downloaded as a CSV. The original
        outpatient dataset is not overwritten.
        """
    )

    st.subheader("Important principle")

    st.warning(
        "The validation system supports data-quality review. "
        "It does not replace verification against the original "
        "medical record and does not automatically overwrite "
        "source data."
    )
