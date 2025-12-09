import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import sys

# --- CONFIGURATION ---
st.set_page_config(page_title="JKKP Inspection Tracker", layout="wide")
st.title("🛡️ JKKP Inspection & Defect Tracker")

# --- SAFETY CHECK FOR OPENPYXL ---
try:
    import openpyxl
except ImportError:
    st.error("🔴 CRITICAL ERROR: 'openpyxl' is missing.")
    st.code("pip install openpyxl", language="bash")
    st.stop()

# --- 1. FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # --- SMART HEADER DETECTION ---
        # Read first 10 rows to find the header row containing "ANNUAL INSPECTION" or "TARIKH"
        # We use engine='openpyxl' explicitly.
        df_preview = pd.read_excel(uploaded_file, header=None, nrows=10, engine='openpyxl')
        
        header_row = 4 # Default to Row 5 (Index 4) based on your Master File
        
        for i, row in df_preview.iterrows():
            row_text = row.astype(str).str.upper().tolist()
            if any("ANNUAL INSPECTION" in x for x in row_text) or any("TARIKH" in x for x in row_text):
                header_row = i
                break
        
        # Reload Data with correct header
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, header=header_row, engine='openpyxl')

        # --- 2. COLUMN MAPPING ---
        st.sidebar.header("🔧 Column Settings")
        all_cols = list(df.columns)

        # Helper to auto-find columns
        def get_col(options, keywords):
            for i, col in enumerate(options):
                if any(k in str(col).upper() for k in keywords):
                    return i
            return 0

        c_date = st.sidebar.selectbox("Inspection Date", all_cols, index=get_col(all_cols, ['ANNUAL', 'TARIKH', 'INSPECTION']))
        c_status = st.sidebar.selectbox("Defect Status (Major/Minor)", all_cols, index=get_col(all_cols, ['DEFECTS STATUS', 'STATUS', 'KEADAAN']))
        c_reply = st.sidebar.selectbox("Reply Date", all_cols, index=get_col(all_cols, ['REPLY', 'BALAS']))
        c_inspector = st.sidebar.selectbox("Inspector / CP Name", all_cols, index=get_col(all_cols, ['INSPECTOR', 'PEMERIKSA']))

        # --- 3. LOGIC & CALCULATIONS ---
        # 1. Clean Dates
        for col in [c_date, c_reply]:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

        # 2. Calculate Due Date (The Logic)
        def calculate_deadline(row):
            start = row[c_date]
            status = str(row[c_status]).upper()
            
            if pd.isnull(start): return None
            
            if "MAJOR" in status: return start + relativedelta(months=1)
            if "MINOR" in status: return start + relativedelta(months=3)
            if "NOTICE" in status: return start + relativedelta(weeks=2)
            if "NO DEFECT" in status: return start + relativedelta(years=1)
            return start + relativedelta(years=1) # Default

        df['Due Date'] = df.apply(calculate_deadline, axis=1)
        
        # 3. Calculate Buffer
        today = date.today()
        df['Days Remaining'] = (pd.to_datetime(df['Due Date']) - pd.to_datetime(today)).dt.days

        # --- 4. FILTERS ---
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filters")
        
        # Inspector Filter
        sel_insp = st.sidebar.multiselect("Inspector", options=df[c_inspector].dropna().unique())
        if sel_insp:
            df = df[df[c_inspector].isin(sel_insp)]

        # Status Filter
        sel_stat = st.sidebar.multiselect("Status Category", options=df[c_status].dropna().unique())
        if sel_stat:
            df = df[df[c_status].isin(sel_stat)]

        # Buffer Time Filter
        buffer_mode = st.sidebar.radio("Deadline Buffer:", ["All", "Overdue (Urgent)", "Due in 1 Month", "Due in 3 Months"])
        
        if buffer_mode == "Overdue (Urgent)":
            df = df[df['Days Remaining'] < 0]
        elif buffer_mode == "Due in 1 Month":
            df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 30)]
        elif buffer_mode == "Due in 3 Months":
            df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 90)]

        # --- 5. DISPLAY ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Rows", len(df))
        col2.metric("Major Defects", len(df[df[c_status].astype(str).str.contains("MAJOR", case=False, na=False)]))
        col3.metric("Action Required", len(df[df['Days Remaining'] < 0]), delta_color="inverse")

        # Table Styling
        def highlight(row):
            days = row['Days Remaining']
            if pd.notnull(days):
                if days < 0: return ['background-color: #ffcccc'] * len(row) # Red
                if days < 30: return ['background-color: #ffffcc'] * len(row) # Yellow
            return [''] * len(row)

        st.dataframe(
            df[[c_date, c_status, 'Due Date', 'Days Remaining', c_reply, c_inspector]].style.apply(highlight, axis=1),
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error Processing File: {e}")
        st.warning("Please ensure the file is not password protected and is a valid .xlsx file.")

else:
    st.info("Waiting for Excel file upload...")
