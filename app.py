import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="JKKP Inspection Tracker", layout="wide")

st.title("🛡️ JKKP Inspection & Defect Tracker")
st.markdown("""
**Instructions:**
1. Upload your **Excel (.xlsx)** or **CSV (.csv)** file.
2. If the Excel upload fails, **Save your file as CSV** in Excel and try again.
""")

# --- 1. ROBUST FILE UPLOADER ---
# We now allow CSV files as a backup if Excel libraries are missing
uploaded_file = st.file_uploader("Upload File", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    df = None
    try:
        # --- A. FILE LOADING LOGIC ---
        if uploaded_file.name.endswith('.csv'):
            # Load CSV (No special libraries needed!)
            # We read the first 15 rows to find the header
            df_preview = pd.read_csv(uploaded_file, header=None, nrows=15)
            
            header_row = 0
            for i, row in df_preview.iterrows():
                row_text = row.astype(str).str.upper().tolist()
                if any("ANNUAL INSPECTION" in x for x in row_text) or any("TARIKH" in x for x in row_text):
                    header_row = i
                    break
            
            # Load full CSV
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=header_row)
            
        else:
            # Load Excel (Requires openpyxl)
            try:
                import openpyxl
                engine_name = 'openpyxl'
            except ImportError:
                st.error("❌ strict dependency 'openpyxl' is missing for .xlsx files.")
                st.info("💡 WORKAROUND: Open your Excel file, click 'Save As', select 'CSV (Comma delimited)', and upload that instead.")
                st.stop()

            # Detect Header in Excel
            df_preview = pd.read_excel(uploaded_file, header=None, nrows=15, engine=engine_name)
            header_row = 0
            for i, row in df_preview.iterrows():
                row_text = row.astype(str).str.upper().tolist()
                if any("ANNUAL INSPECTION" in x for x in row_text) or any("TARIKH" in x for x in row_text):
                    header_row = i
                    break
            
            # Load full Excel
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, header=header_row, engine=engine_name)

        # --- B. COLUMN MAPPING ---
        if df is not None:
            st.write("✅ File loaded successfully!")
            
            st.sidebar.header("🔧 Column Setup")
            all_cols = list(df.columns)
            
            # Helper to find columns
            def get_col(options, keywords):
                for i, col in enumerate(options):
                    if any(k in str(col).upper() for k in keywords):
                        return i
                return 0

            # Allow user to pick columns
            c_date = st.sidebar.selectbox("Inspection Date", all_cols, index=get_col(all_cols, ['ANNUAL', 'TARIKH', 'INSPECTION']))
            c_status = st.sidebar.selectbox("Status (Major/Minor)", all_cols, index=get_col(all_cols, ['DEFECTS STATUS', 'STATUS', 'KEADAAN']))
            c_reply = st.sidebar.selectbox("Reply Date", all_cols, index=get_col(all_cols, ['REPLY', 'BALAS']))
            c_inspector = st.sidebar.selectbox("Inspector / CP", all_cols, index=get_col(all_cols, ['INSPECTOR', 'PEMERIKSA']))

            # --- C. CALCULATIONS ---
            # Date conversion
            for col in [c_date, c_reply]:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

            # Deadline Logic
            def calculate_due(row):
                start = row[c_date]
                status = str(row[c_status]).upper()
                
                if pd.isnull(start): return None
                
                if "MAJOR" in status: return start + relativedelta(months=1)
                if "MINOR" in status: return start + relativedelta(months=3)
                if "NOTICE" in status: return start + relativedelta(weeks=2)
                if "NO DEFECT" in status: return start + relativedelta(years=1)
                return start + relativedelta(years=1)

            df['Due Date'] = df.apply(calculate_due, axis=1)
            df['Days Remaining'] = (pd.to_datetime(df['Due Date']) - pd.to_datetime(date.today())).dt.days

            # --- D. FILTERS ---
            st.sidebar.markdown("---")
            st.sidebar.header("🔍 Filter Options")
            
            # Filter Inspector
            insp_filter = st.sidebar.multiselect("Filter Inspector", options=df[c_inspector].dropna().unique())
            if insp_filter:
                df = df[df[c_inspector].isin(insp_filter)]

            # Filter Urgency
            urgency = st.sidebar.radio("Show Deadlines:", ["All", "Overdue (Urgent)", "Due in 1 Month", "Due in 3 Months"])
            
            if urgency == "Overdue (Urgent)":
                df = df[df['Days Remaining'] < 0]
            elif urgency == "Due in 1 Month":
                df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 30)]
            elif urgency == "Due in 3 Months":
                df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 90)]

            # --- E. DISPLAY ---
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
        st.error(f"An error occurred: {e}")
        st.warning("Tip: Try saving your Excel file as a CSV file and upload that instead.")
