# Smart Receiving OCR & Workflow Dashboard

A Streamlit-based prototype dashboard that automates receiving document processing using OCR, validates purchase order quantity mismatches, and tracks receiving workflow status.

## Project Overview

This project simulates a manufacturing receiving workflow where delivery documents are uploaded, processed with OCR, validated against expected purchase order data, and tracked through workflow statuses.

The goal is to improve receiving visibility, reduce manual checking, and flag exception cases such as quantity mismatches, missing quantities, or unknown PO numbers.

## Key Features

- Upload receiving document images
- Extract text using OCR
- Extract key receiving fields:
  - Supplier
  - PO Number
  - Item Code
  - Quantity
  - Received Date
- Validate received quantity against expected PO data
- Detect exceptions:
  - Quantity mismatch
  - PO not found
  - Missing quantity
- Save validation results into receiving history
- Track workflow status:
  - Pending Review
  - Approved
  - Completed
- Interactive dashboard with receiving analytics
- CSV export for receiving history

## Tech Stack

- Python
- Streamlit
- Pandas
- Plotly
- Tesseract OCR
- Pytesseract
- Pillow

## Project Workflow

```text
Upload Document → OCR Extraction → Field Extraction → PO Validation → Workflow Review → Dashboard