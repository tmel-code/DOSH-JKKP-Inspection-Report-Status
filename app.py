import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="JKKP Inspection Tracker", layout="wide", page_icon="🛡️")

# --- CUSTOM STYLING ---
st.markdown("""
    <style>
        .stDataFrame { border: 1px solid #ccc; border-radius: 5px; }
        .urgent { color: #d9534f; font-weight: bold; }
        .safe { color: #5cb85c; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ JKKP Inspection & Defect Tracker")
st.markdown("Upload your **Master File**. The app acts as a dashboard to track deadlines.")

# --- 1. FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload Excel File", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # --- SMART HEADER DETECTION ---
        # We read the first 10 rows to find the row containing "ANNUAL INSPECTION DATE"
        # engine='openpyxl' is crucial here to fix your error
        df_preview = pd.read_excel(uploaded_file, header=None, nrows=10, engine='openpyxl')
        
        header_row_index = 0
        found_header = False
        
        # Scan rows to find the real header
        for i, row in df_preview.iterrows():
            row_text = row.astype(str).str.upper().tolist()
            # We look for keywords specific to your JKKP report
            if any("ANNUAL INSPECTION DATE" in x for x in row_text) or any("TARIKH" in x for x in row_text):
                header_row_index = i
                found_header = True
                break
        
        if not found_header:
            st.warning("⚠️ Could not auto-detect header row. Defaulting to Row 5.")
            header_row_index = 4 # Default based on your uploaded file

        # Reload data with the correct header row
        df = pd.read_excel(uploaded_file, header=header_row_index, engine='openpyxl')

        # --- 2. COLUMN MAPPING (Flexible for Old/New Versions) ---
        st.sidebar.header("🔧 Column Settings")
        st.sidebar.caption("Map the columns below if they don't match automatically.")
        
        all_cols = list(df.columns)
        
        # Function to find best matching column name
        def find_col(keywords):
            for i, col in enumerate(all_cols):
                c_str = str(col).upper()
                if any(k in c_str for k in keywords):
                    return i
            return 0

        # Create dropdowns for mapping
        c_date = st.sidebar.selectbox("Inspection Date", all_cols, index=find_col(['ANNUAL INSPECTION', 'TARIKH PEMERIKSAAN']))
        c_status = st.sidebar.selectbox("Defect Status (Major/Minor)", all_cols, index=find_col(['DEFECTS STATUS', 'KEADAAN', 'STATUS']))
        c_reply = st.sidebar.selectbox("Reply Date", all_cols, index=find_col(['REPLY DATE', 'TARIKH BALAS']))
        c_inspector = st.sidebar.selectbox("Inspector Name", all_cols, index=find_col(['INSPECTOR', 'NAMA PEMERIKSA', 'CP']))
        c_defect_yn = st.sidebar.selectbox("Defect (Yes/No)", all_cols, index=find_col(['DEFECT', 'ADA', 'YES']))

        # --- 3. DATA PROCESSING ---
        # Convert dates
        for col in [c_date, c_reply]:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

        # Logic: Calculate Due Date based on Status
        def calculate_due_date(row):
            start_date = row[c_date]
            status = str(row[c_status]).upper()
            
            if pd.isnull(start_date): return None
            
            if "MAJOR" in status:
                return start_date + relativedelta(months=1) # 1 Month
            elif "MINOR" in status:
                return start_date + relativedelta(months=3) # 3 Months
            elif "NOTICE" in status:
                return start_date + relativedelta(weeks=2)  # 2 Weeks
            elif "NO DEFECT" in status:
                return start_date + relativedelta(years=1)  # Next Cycle
            return None

        df['Due Date'] = df.apply(calculate_due_date, axis=1)
        
        # Calculate Buffer / Days Remaining
        today = date.today()
        df['Days Remaining'] = (pd.to_datetime(df['Due Date']) - pd.to_datetime(today)).dt.days

        # --- 4. FILTERS ---
        st.sidebar.markdown("---")
        st.sidebar.header("📊 Dashboard Filters")

        # Filter by Inspector
        unique_inspectors = df[c_inspector].dropna().unique()
        selected_inspector = st.sidebar.multiselect("Filter Inspector", options=unique_inspectors)
        if selected_inspector:
            df = df[df[c_inspector].isin(selected_inspector)]

        # Filter by Urgency (Buffer Time)
        buffer_mode = st.sidebar.radio("Show Deadlines:", ["All Data", "Due in 1 Month", "Due in 3 Months", "Overdue"])
        
        if buffer_mode == "Due in 1 Month":
            df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 30)]
        elif buffer_mode == "Due in 3 Months":
            df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 90)]
        elif buffer_mode == "Overdue":
            df = df[df['Days Remaining'] < 0]

        # --- 5. MAIN DISPLAY ---
        
        # KPI Row
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total Items", len(df))
        
        overdue_count = len(df[df['Days Remaining'] < 0])
        kpi2.metric("Overdue Items", overdue_count, delta_color="inverse")
        
        major_defects = len(df[df[c_status].astype(str).str.contains("MAJOR", case=False, na=False)])
        kpi3.metric("Major Defects", major_defects)

        # Highlight Function for DataFrame
        def highlight_rows(row):
            days = row['Days Remaining']
            if pd.isna(days): return [''] * len(row)
            if days < 0: return ['background-color: #ffcccc'] * len(row) # Red
            if days <= 30: return ['background-color: #fff3cd'] * len(row) # Yellow
            return [''] * len(row)

        st.subheader("📋 Inspection Details")
        
        # Select columns to display
        display_cols = [c_date, c_status, 'Due Date', 'Days Remaining', c_reply, c_inspector, c_defect_yn]
        # Filter out columns that might not exist or were not mapped
        display_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(
            df[display_cols].style.apply(highlight_rows, axis=1),
            use_container_width=True,
            column_config={
                c_date: st.column_config.DateColumn("Inspection Date"),
                "Due Date": st.column_config.DateColumn("Due Date", format="DD/MM/YYYY"),
            }
        )

    except Exception as e:
        st.error(f"Error: {e}")
        st.info("Ensure you have 'openpyxl' installed and the file is a standard Excel format.")

else:
    st.info("Waiting for file upload...")
