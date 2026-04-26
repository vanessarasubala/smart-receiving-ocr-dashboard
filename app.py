import os
import re
import uuid
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import pytesseract
import streamlit as st
from PIL import Image


st.set_page_config(
    page_title="Smart Receiving OCR Dashboard",
    page_icon="📦",
    layout="wide"
)


EXPECTED_PO_PATH = "data/expected_po.csv"
RECEIVING_RECORDS_PATH = "data/receiving_records.csv"

RECEIVING_COLUMNS = [
    "record_id",
    "created_at",
    "received_date",
    "po_number",
    "supplier",
    "item_code",
    "expected_supplier",
    "expected_item_code",
    "expected_qty",
    "received_qty",
    "qty_difference",
    "status",
    "workflow_status",
    "validation_message",
    "source",
    "review_notes",
]


# -----------------------------
# Data loading functions
# -----------------------------
@st.cache_data
def load_expected_po():
    return pd.read_csv(EXPECTED_PO_PATH)


@st.cache_data
def load_receiving_records():
    if not os.path.exists(RECEIVING_RECORDS_PATH):
        return pd.DataFrame(columns=RECEIVING_COLUMNS)

    try:
        df = pd.read_csv(RECEIVING_RECORDS_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=RECEIVING_COLUMNS)

    for col in RECEIVING_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[RECEIVING_COLUMNS]


def save_all_records(df):
    df = df[RECEIVING_COLUMNS]
    df.to_csv(RECEIVING_RECORDS_PATH, index=False)
    st.cache_data.clear()


def save_receiving_record(record):
    existing_records = load_receiving_records()

    new_record = pd.DataFrame([record])

    for col in RECEIVING_COLUMNS:
        if col not in new_record.columns:
            new_record[col] = None

    new_record = new_record[RECEIVING_COLUMNS]

    updated_records = pd.concat(
        [existing_records, new_record],
        ignore_index=True
    )

    save_all_records(updated_records)


expected_po = load_expected_po()


# -----------------------------
# Helper functions
# -----------------------------
def extract_with_regex(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_receiving_fields(ocr_text):
    supplier = extract_with_regex(
        r"Supplier\s*[:\-]\s*(.+)",
        ocr_text
    )

    po_number = extract_with_regex(
        r"PO\s*(?:Number|No|#)?\s*[:\-]?\s*(PO[-\s]?\d+)",
        ocr_text
    )

    item_code = extract_with_regex(
        r"Item\s*Code\s*[:\-]\s*([A-Z0-9\-]+)",
        ocr_text
    )

    quantity = extract_with_regex(
        r"(?:Quantity|Qty)\s*[:\-]\s*(\d+)",
        ocr_text
    )

    received_date = extract_with_regex(
        r"(?:Received Date|Date)\s*[:\-]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        ocr_text
    )

    if po_number:
        po_number = po_number.replace(" ", "-").upper()

    if quantity:
        quantity = int(quantity)

    return {
        "supplier": supplier,
        "po_number": po_number,
        "item_code": item_code,
        "received_qty": quantity,
        "received_date": received_date,
    }


def assign_workflow_status(validation_status):
    """
    Initial workflow decision.
    Normal matched records are completed automatically.
    Exception records require manual review.
    """

    if validation_status == "Matched":
        return "Completed"

    return "Pending Review"


def validate_receiving(extracted_data, expected_po_df):
    po_number = extracted_data.get("po_number")

    if not po_number:
        status = "Missing PO Number"
        return {
            **extracted_data,
            "expected_supplier": None,
            "expected_item_code": None,
            "expected_qty": None,
            "qty_difference": None,
            "status": status,
            "workflow_status": assign_workflow_status(status),
            "validation_message": "PO number could not be extracted from the document."
        }

    matched_po = expected_po_df[expected_po_df["po_number"] == po_number]

    if matched_po.empty:
        status = "PO Not Found"
        return {
            **extracted_data,
            "expected_supplier": None,
            "expected_item_code": None,
            "expected_qty": None,
            "qty_difference": None,
            "status": status,
            "workflow_status": assign_workflow_status(status),
            "validation_message": "PO number was extracted, but it does not exist in expected PO data."
        }

    expected_record = matched_po.iloc[0]
    expected_qty = int(expected_record["expected_qty"])
    received_qty = extracted_data.get("received_qty")

    if received_qty is None:
        status = "Missing Quantity"
        return {
            **extracted_data,
            "expected_supplier": expected_record["supplier"],
            "expected_item_code": expected_record["item_code"],
            "expected_qty": expected_qty,
            "qty_difference": None,
            "status": status,
            "workflow_status": assign_workflow_status(status),
            "validation_message": "Quantity could not be extracted from the document."
        }

    qty_difference = received_qty - expected_qty

    if qty_difference == 0:
        status = "Matched"
        validation_message = "Received quantity matches expected PO quantity."
    else:
        status = "Mismatch"
        validation_message = "Received quantity does not match expected PO quantity."

    return {
        **extracted_data,
        "expected_supplier": expected_record["supplier"],
        "expected_item_code": expected_record["item_code"],
        "expected_qty": expected_qty,
        "qty_difference": qty_difference,
        "status": status,
        "workflow_status": assign_workflow_status(status),
        "validation_message": validation_message,
    }


def prepare_record_for_saving(validation_result, source):
    return {
        "record_id": str(uuid.uuid4())[:8],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "received_date": validation_result.get("received_date"),
        "po_number": validation_result.get("po_number"),
        "supplier": validation_result.get("supplier"),
        "item_code": validation_result.get("item_code"),
        "expected_supplier": validation_result.get("expected_supplier"),
        "expected_item_code": validation_result.get("expected_item_code"),
        "expected_qty": validation_result.get("expected_qty"),
        "received_qty": validation_result.get("received_qty"),
        "qty_difference": validation_result.get("qty_difference"),
        "status": validation_result.get("status"),
        "workflow_status": validation_result.get("workflow_status"),
        "validation_message": validation_result.get("validation_message"),
        "source": source,
        "review_notes": "",
    }


def update_record_workflow(record_id, new_workflow_status, review_notes):
    records = load_receiving_records()

    records.loc[
        records["record_id"] == record_id,
        "workflow_status"
    ] = new_workflow_status

    records.loc[
        records["record_id"] == record_id,
        "review_notes"
    ] = review_notes

    save_all_records(records)


# -----------------------------
# App title
# -----------------------------
st.title("📦 Smart Receiving OCR & Workflow Dashboard")
st.caption(
    "A prototype dashboard to automate receiving document processing, "
    "validate quantity mismatches, and monitor receiving workflow status."
)


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Go to",
    [
        "Dashboard",
        "Expected PO Data",
        "Manual Receiving Entry",
        "Upload Receiving Document",
        "Workflow Review"
    ]
)


# -----------------------------
# Dashboard page
# -----------------------------
if page == "Dashboard":
    st.subheader("Receiving Overview")

    if st.sidebar.button("Reset Receiving History"):
        empty_df = pd.DataFrame(columns=RECEIVING_COLUMNS)
        save_all_records(empty_df)
        st.success("Receiving history has been reset. Please refresh the page.")

    receiving_data = load_receiving_records()

    if receiving_data.empty:
        st.info(
            "No receiving records saved yet. Upload a receiving document or use manual entry first."
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records", 0)
        col2.metric("Pending Review", 0)
        col3.metric("Approved", 0)
        col4.metric("Completed", 0)

    else:
        receiving_data["received_qty"] = pd.to_numeric(
            receiving_data["received_qty"],
            errors="coerce"
        ).fillna(0)

        receiving_data["expected_qty"] = pd.to_numeric(
            receiving_data["expected_qty"],
            errors="coerce"
        )

        receiving_data["qty_difference"] = pd.to_numeric(
            receiving_data["qty_difference"],
            errors="coerce"
        )

        st.sidebar.subheader("Dashboard Filters")

        status_options = sorted(receiving_data["status"].dropna().unique().tolist())
        selected_status = st.sidebar.multiselect(
            "Filter by Validation Status",
            status_options,
            default=status_options
        )

        workflow_options = sorted(
            receiving_data["workflow_status"].dropna().unique().tolist()
        )
        selected_workflows = st.sidebar.multiselect(
            "Filter by Workflow Status",
            workflow_options,
            default=workflow_options
        )

        supplier_options = sorted(receiving_data["supplier"].dropna().unique().tolist())
        selected_suppliers = st.sidebar.multiselect(
            "Filter by Supplier",
            supplier_options,
            default=supplier_options
        )

        filtered_data = receiving_data[
            receiving_data["status"].isin(selected_status)
            & receiving_data["workflow_status"].isin(selected_workflows)
            & receiving_data["supplier"].isin(selected_suppliers)
        ]

        total_records = len(filtered_data)
        pending_count = (filtered_data["workflow_status"] == "Pending Review").sum()
        approved_count = (filtered_data["workflow_status"] == "Approved").sum()
        completed_count = (filtered_data["workflow_status"] == "Completed").sum()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Records", total_records)
        col2.metric("Pending Review", pending_count)
        col3.metric("Approved", approved_count)
        col4.metric("Completed", completed_count)

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Validation Status")

            status_count = (
                filtered_data["status"]
                .value_counts()
                .reset_index()
            )
            status_count.columns = ["status", "count"]

            if not status_count.empty:
                fig_status = px.pie(
                    status_count,
                    names="status",
                    values="count",
                    title="Validation Result Breakdown"
                )
                st.plotly_chart(fig_status, use_container_width=True)

        with col_right:
            st.subheader("Workflow Status")

            workflow_count = (
                filtered_data["workflow_status"]
                .value_counts()
                .reset_index()
            )
            workflow_count.columns = ["workflow_status", "count"]

            if not workflow_count.empty:
                fig_workflow = px.bar(
                    workflow_count,
                    x="workflow_status",
                    y="count",
                    title="Workflow Status Breakdown"
                )
                st.plotly_chart(fig_workflow, use_container_width=True)

        st.subheader("Receiving by Supplier")

        supplier_volume = (
            filtered_data.groupby("supplier")["received_qty"]
            .sum()
            .reset_index()
        )

        if not supplier_volume.empty:
            fig_supplier = px.bar(
                supplier_volume,
                x="supplier",
                y="received_qty",
                title="Total Received Quantity by Supplier"
            )
            st.plotly_chart(fig_supplier, use_container_width=True)

        st.subheader("Receiving Trend")

        trend_data = (
            filtered_data.groupby("received_date")["received_qty"]
            .sum()
            .reset_index()
        )

        if not trend_data.empty:
            fig_trend = px.line(
                trend_data,
                x="received_date",
                y="received_qty",
                markers=True,
                title="Received Quantity Over Time"
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        st.subheader("Receiving Records")
        st.dataframe(filtered_data, use_container_width=True)

        st.download_button(
            label="Download Receiving History as CSV",
            data=filtered_data.to_csv(index=False),
            file_name="receiving_history.csv",
            mime="text/csv"
        )


# -----------------------------
# Expected PO page
# -----------------------------
elif page == "Expected PO Data":
    st.subheader("Expected Purchase Order Data")
    st.write(
        "This table represents expected PO records from the system. "
        "OCR-extracted receiving data will be compared against this table."
    )
    st.dataframe(expected_po, use_container_width=True)


# -----------------------------
# Manual entry page
# -----------------------------
elif page == "Manual Receiving Entry":
    st.subheader("Manual Receiving Entry")

    st.write(
        "This page simulates manual receiving input. "
        "You can also save manual validation results to receiving history."
    )

    with st.form("receiving_form"):
        po_number = st.selectbox("PO Number", expected_po["po_number"].tolist())

        selected_po = expected_po[expected_po["po_number"] == po_number].iloc[0]

        supplier = st.text_input("Supplier", value=selected_po["supplier"])
        item_code = st.text_input("Item Code", value=selected_po["item_code"])
        received_qty = st.number_input("Received Quantity", min_value=0, step=1)
        received_date = st.date_input("Received Date", value=date.today())
        save_to_history = st.checkbox("Save this result to receiving history")

        submitted = st.form_submit_button("Validate Receiving")

    if submitted:
        extracted_data = {
            "supplier": supplier,
            "po_number": po_number,
            "item_code": item_code,
            "received_qty": received_qty,
            "received_date": str(received_date),
        }

        validation_result = validate_receiving(extracted_data, expected_po)

        if validation_result["status"] == "Matched":
            st.success(validation_result["validation_message"])
        elif validation_result["status"] == "Mismatch":
            st.error(validation_result["validation_message"])
        else:
            st.warning(validation_result["validation_message"])

        validation_df = pd.DataFrame([validation_result])

        st.subheader("Validation Result")
        st.dataframe(validation_df, use_container_width=True)

        if save_to_history:
            record = prepare_record_for_saving(
                validation_result,
                source="Manual Entry"
            )
            save_receiving_record(record)
            st.success("Manual receiving result saved to receiving history.")


# -----------------------------
# OCR upload page
# -----------------------------
elif page == "Upload Receiving Document":
    st.subheader("Upload Receiving Document")

    st.write(
        "Upload a receiving document image. The system will perform OCR, "
        "extract key receiving fields, validate it against expected PO data, "
        "and allow you to save the result to receiving history."
    )

    uploaded_file = st.file_uploader(
        "Upload PNG or JPG receiving document",
        type=["png", "jpg", "jpeg"]
    )

    if uploaded_file is not None:
        image = Image.open(uploaded_file)

        col_img, col_result = st.columns([1, 1])

        with col_img:
            st.subheader("Uploaded Document")
            st.image(image, use_container_width=True)

        with col_result:
            st.subheader("OCR Result")

            with st.spinner("Reading document with OCR..."):
                ocr_text = pytesseract.image_to_string(image)

            st.text_area("Raw OCR Text", value=ocr_text, height=250)

        st.divider()

        st.subheader("Extracted Receiving Fields")

        extracted_data = extract_receiving_fields(ocr_text)
        extracted_df = pd.DataFrame([extracted_data])
        st.dataframe(extracted_df, use_container_width=True)

        st.subheader("Validation Against Expected PO")

        validation_result = validate_receiving(extracted_data, expected_po)
        validation_df = pd.DataFrame([validation_result])

        status = validation_result["status"]

        if status == "Matched":
            st.success(validation_result["validation_message"])
        elif status == "Mismatch":
            st.error(validation_result["validation_message"])
        else:
            st.warning(validation_result["validation_message"])

        st.dataframe(validation_df, use_container_width=True)

        st.info(
            f"Initial workflow status: {validation_result['workflow_status']}"
        )

        col_save, col_download = st.columns(2)

        with col_save:
            if st.button("Save OCR Result to Receiving History"):
                record = prepare_record_for_saving(
                    validation_result,
                    source="OCR Upload"
                )
                save_receiving_record(record)
                st.success("OCR validation result saved to receiving history.")

        with col_download:
            st.download_button(
                label="Download Validation Result as CSV",
                data=validation_df.to_csv(index=False),
                file_name="receiving_validation_result.csv",
                mime="text/csv"
            )

    else:
        st.info("Upload a sample receiving document to start OCR extraction.")


# -----------------------------
# Workflow review page
# -----------------------------
elif page == "Workflow Review":
    st.subheader("Workflow Review")

    st.write(
        "Use this page to review exception records and update their workflow status."
    )

    records = load_receiving_records()

    if records.empty:
        st.info("No receiving records available for review.")

    else:
        review_filter = st.selectbox(
            "Show records with workflow status",
            ["All", "Pending Review", "Approved", "Completed"]
        )

        if review_filter != "All":
            review_records = records[records["workflow_status"] == review_filter]
        else:
            review_records = records

        if review_records.empty:
            st.warning("No records found for the selected workflow status.")

        else:
            display_records = review_records.copy()
            display_records["record_label"] = (
                display_records["record_id"].astype(str)
                + " | "
                + display_records["po_number"].astype(str)
                + " | "
                + display_records["status"].astype(str)
                + " | "
                + display_records["workflow_status"].astype(str)
            )

            selected_label = st.selectbox(
                "Select a record to review",
                display_records["record_label"].tolist()
            )

            selected_record_id = selected_label.split(" | ")[0]
            selected_record = records[
                records["record_id"] == selected_record_id
            ].iloc[0]

            st.subheader("Selected Record Details")

            detail_df = pd.DataFrame([selected_record])
            st.dataframe(detail_df, use_container_width=True)

            st.divider()

            st.subheader("Update Workflow Status")

            new_workflow_status = st.radio(
                "New Workflow Status",
                ["Pending Review", "Approved", "Completed"],
                index=["Pending Review", "Approved", "Completed"].index(
                    selected_record["workflow_status"]
                )
                if selected_record["workflow_status"] in ["Pending Review", "Approved", "Completed"]
                else 0
            )

            review_notes = st.text_area(
                "Review Notes",
                value=selected_record["review_notes"]
                if pd.notna(selected_record["review_notes"])
                else "",
                placeholder="Example: Partial delivery accepted after supervisor approval."
            )

            if st.button("Update Workflow Status"):
                update_record_workflow(
                    selected_record_id,
                    new_workflow_status,
                    review_notes
                )

                st.success(
                    f"Record {selected_record_id} updated to {new_workflow_status}."
                )
                st.info("Refresh the page to see the latest updated table.")

            st.subheader("Records for Review")
            st.dataframe(review_records, use_container_width=True)
            