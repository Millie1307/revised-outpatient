
import pandas as pd


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def is_missing(value):
    """Return True when a value is blank or missing."""
    return pd.isna(value) or str(value).strip() == ""


# ---------------------------------------------------------
# Age validation
# ---------------------------------------------------------

def validate_age(value):
    if pd.isna(value):
        return "Missing"

    try:
        age = float(value)
    except (ValueError, TypeError):
        return "Invalid"

    if age < 0:
        return "Invalid"

    if age == 0:
        return "Review"

    if age > 100:
        return "Invalid"

    return "Pass"


# ---------------------------------------------------------
# Date validation
# ---------------------------------------------------------

def validate_date(value):
    if pd.isna(value):
        return "Invalid"

    return "Pass"


# ---------------------------------------------------------
# Gender validation
# ---------------------------------------------------------

def validate_gender(value):
    if pd.isna(value):
        return "Missing"

    value = str(value).strip()

    if value in ["F", "M"]:
        return "Pass"

    if value == "m":
        return "Standardize"

    return "Review"


# ---------------------------------------------------------
# Status validation
# ---------------------------------------------------------

VALID_STATUSES = [
    "Pharmacy",
    "Triage",
    "Lab",
    "Lab Results",
    "Imaging"
]


def validate_status(value):
    if pd.isna(value):
        return "Missing"

    value = str(value).strip()

    if value in VALID_STATUSES:
        return "Pass"

    return "Review"


# ---------------------------------------------------------
# Registration number validation
# ---------------------------------------------------------

def validate_registration(row):
    category = str(row["CATEGORY"]).strip()
    value = row["REGISTRATION NO."]

    if category == "Student":
        if is_missing(value):
            return "Missing"

        return "Pass"

    if not is_missing(value):
        return "Review"

    return "Informational"


# ---------------------------------------------------------
# PF number validation
# ---------------------------------------------------------

PF_REQUIRED_CATEGORIES = [
    "Employee",
    "Dependant",
    "Private Citizen"
]


def validate_pf(row):
    category = str(row["CATEGORY"]).strip()
    value = row["PF NO."]

    if category in PF_REQUIRED_CATEGORIES:
        if is_missing(value):
            return "Missing"

        return "Pass"

    if not is_missing(value):
        return "Review"

    return "Informational"


# ---------------------------------------------------------
# OPD number
# ---------------------------------------------------------

def validate_opd(value):
    # OPD number is optional according to the agreed
    # facility interpretation.
    return "Informational"


# ---------------------------------------------------------
# Diagnosis validation
# ---------------------------------------------------------

CONTEXT_DEPENDENT_STATUSES = [
    "Triage",
    "Lab",
    "Lab Results",
    "Imaging"
]


def validate_diagnosis(row):
    diagnosis = row["DIAGNOSIS"]
    status = str(row["STATUS"]).strip()

    if not is_missing(diagnosis):
        return "Pass"

    if status == "Pharmacy":
        return "Review"

    if status in CONTEXT_DEPENDENT_STATUSES:
        return "Context-dependent"

    return "Review"


# ---------------------------------------------------------
# RE-VISIT validation
# ---------------------------------------------------------

def validate_revisit(value):
    if pd.isna(value) or str(value).strip() == "":
        return "Informational"

    value = str(value).strip().upper()

    if value == "RE-VISIT":
        return "Pass"

    if value == "RE-VISIST":
        return "Standardize"

    return "Review"


# ---------------------------------------------------------
# Overall result priority
# ---------------------------------------------------------

RESULT_PRIORITY = {
    "Invalid": 6,
    "Review": 5,
    "Missing": 4,
    "Standardize": 3,
    "Context-dependent": 2,
    "Informational": 1,
    "Pass": 0
}


ACTIONABLE_RESULTS = {
    "Invalid",
    "Review",
    "Missing",
    "Standardize"
}


def calculate_overall_result(row, result_columns):
    results = [row[col] for col in result_columns]

    highest_priority = max(
        RESULT_PRIORITY.get(result, 0)
        for result in results
    )

    for result, priority in RESULT_PRIORITY.items():
        if priority == highest_priority:
            return result


# ---------------------------------------------------------
# Main validation function
# ---------------------------------------------------------

def validate_outpatient_data(df):

    validation = df.copy()

    # Parse date
    if "DATE" in validation.columns:
        validation["DATE_PARSED"] = pd.to_datetime(
            validation["DATE"],
            errors="coerce",
            format="mixed"
        )

    # Preserve original values
    if "GENDER" in validation.columns:
        validation["GENDER_ORIGINAL"] = validation["GENDER"]

    if "RE-VISIT" in validation.columns:
        validation["REVISIT_ORIGINAL"] = validation["RE-VISIT"]

    # Field checks
    validation["AGE_RESULT"] = validation["AGE"].apply(
        validate_age
    )

    validation["DATE_RESULT"] = validation["DATE_PARSED"].apply(
        lambda x: "Pass" if pd.notna(x) else "Invalid"
    )

    validation["GENDER_RESULT"] = validation["GENDER"].apply(
        validate_gender
    )

    validation["STATUS_RESULT"] = validation["STATUS"].apply(
        validate_status
    )

    validation["REGISTRATION_RESULT"] = validation.apply(
        validate_registration,
        axis=1
    )

    validation["PF_RESULT"] = validation.apply(
        validate_pf,
        axis=1
    )

    validation["OPD_RESULT"] = validation["OPD NO."].apply(
        validate_opd
    )

    validation["DIAGNOSIS_RESULT"] = validation.apply(
        validate_diagnosis,
        axis=1
    )

    validation["REVISIT_RESULT"] = validation["RE-VISIT"].apply(
        validate_revisit
    )

    # Exact duplicates
    duplicate_columns = [
        col for col in df.columns
        if col != "DATE_PARSED"
    ]

    exact_duplicate_mask = validation.duplicated(
        subset=duplicate_columns,
        keep=False
    )

    validation["EXACT_DUPLICATE_RESULT"] = (
        exact_duplicate_mask.map({
            True: "Review",
            False: "Pass"
        })
    )

    # Observation number validation
    obs = validation["OBSERVATION NO."].astype("string").str.strip()

    obs_missing = (
        validation["OBSERVATION NO."].isna()
        | obs.eq("")
    )

    obs_counts = obs[~obs_missing].value_counts()

    repeated_observation_numbers = set(
        obs_counts[obs_counts > 1].index
    )

    validation["OBSERVATION_RESULT"] = "Pass"

    validation.loc[
        obs_missing,
        "OBSERVATION_RESULT"
    ] = "Informational"

    validation.loc[
        obs.isin(repeated_observation_numbers),
        "OBSERVATION_RESULT"
    ] = "Review"

    # Overall result
    result_columns = [
        "AGE_RESULT",
        "DATE_RESULT",
        "GENDER_RESULT",
        "STATUS_RESULT",
        "REGISTRATION_RESULT",
        "PF_RESULT",
        "OPD_RESULT",
        "DIAGNOSIS_RESULT",
        "REVISIT_RESULT",
        "EXACT_DUPLICATE_RESULT",
        "OBSERVATION_RESULT"
    ]

    validation["OVERALL_RESULT"] = validation.apply(
        lambda row: calculate_overall_result(
            row,
            result_columns
        ),
        axis=1
    )

    # Actionable findings
    validation["ACTIONABLE_FLAG_COUNT"] = validation[
        result_columns
    ].apply(
        lambda row: sum(
            value in ACTIONABLE_RESULTS
            for value in row
        ),
        axis=1
    )

    validation["CONTEXTUAL_COUNT"] = validation[
        result_columns
    ].apply(
        lambda row: sum(
            value in {
                "Context-dependent",
                "Informational"
            }
            for value in row
        ),
        axis=1
    )

    validation["NEEDS_ACTION"] = (
        validation["ACTIONABLE_FLAG_COUNT"] > 0
    )

    return validation
