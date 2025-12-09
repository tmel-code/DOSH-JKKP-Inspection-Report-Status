import streamlit as st
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="JKKP Inspection Tracker", layout="wide", page_icon="🛡️")

# --- CUSTOM CSS FOR STATUS HIGHLIGHTING ---
st.markdown("""
<style>
    .status-major { background-color: #ffcccb; color: #8b0000; padding: 4px; border-radius: 4px; font-weight: bold; }
    .status-minor { background-color: #fffacd; color: #bdb76b; padding: 4px; border-radius: 4px; font-weight: bold; }
    .status-safe { background-color: #c1ffc1; color: #006400; padding: 4px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ JKKP Inspection & Defect Tracker")
st.markdown("Upload your **Master File** (Old or New format) to calculate due dates and filter defects.")

# --- 1. FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # Load Data - Skip first few rows if header is not in row 1 (Common in JKKP reports)
        # We try to auto-find the header row looking for "MAINTENANCE CODE" or "JKKP"
        df = pd.read_excel(uploaded_file, header=None)
        
        # Find the header row index
        header_row_idx = 0
        for i, row in df.head(10).iterrows():
            row_str = row.astype(str).str.upper().tolist()
            if "INSPECTOR" in str(row_str) or "DATE" in str(row_str):
                header_row_idx = i
                break
        
        # Reload with correct header
        df = pd.read_excel(uploaded_file, header=header_row_idx)

        # --- 2. COLUMN MAPPING (CRITICAL FOR OLD VS NEW VERSIONS) ---
        st.sidebar.header("🔧 Column Configuration")
        st.sidebar.info("Map your Excel columns below. This allows both Old & New versions to work.")
        
        all_columns = df.columns.tolist()
        
        # Helper to find default index
        def get_idx(options, search_terms):
            for i, opt in enumerate(options):
                if any(term in str(opt).upper() for term in search_terms):
                    return i
            return 0

        # Select Columns
        col_insp_date = st.sidebar.selectbox("Inspection Date Column", all_columns, index=get_idx(all_columns, ['ANNUAL', 'TARIKH', 'INSPECTION']))
        col_status = st.sidebar.selectbox("Inspection Status Column (Major/Minor)", all_columns, index=get_idx(all_columns, ['STATUS', 'DEFECT', 'KEADAAN']))
        col_reply = st.sidebar.selectbox("Reply Date Column", all_columns, index=get_idx(all_columns, ['REPLY', 'BALAS']))
        col_inspector = st.sidebar.selectbox("Inspector / CP Name", all_columns, index=get_idx(all_columns, ['INSPECTOR', 'PEMERIKSA', 'CP']))
        col_defect_yn = st.sidebar.selectbox("Defect (Yes/No) Column", all_columns, index=get_idx(all_columns, ['DEFECT', 'ADA', 'YES']))

        # --- 3. DATA CLEANING & LOGIC ---
        # Standardize Date Columns
        for col in [col_insp_date, col_reply]:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

        # Function to Calculate Due Date
        def calculate_deadline(row):
            insp_date = row[col_insp_date]
            status = str(row[col_status]).upper()
            
            if pd.isnull(insp_date):
                return None
            
            # JKKP / COMPLIANCE LOGIC
            if 'MAJOR' in status:
                return insp_date + relativedelta(months=1) # 1 Month Buffer
            elif 'MINOR' in status:
                return insp_date + relativedelta(months=3) # 3 Month Buffer
            elif 'NOTICE' in status:
                return insp_date + relativedelta(weeks=2)  # 2 Weeks Buffer
            else:
                return insp_date + relativedelta(years=1)  # Next Annual

        df['Calculated Due Date'] = df.apply(calculate_deadline, axis=1)
        
        # Calculate Days Remaining
        today = date.today()
        df['Days Remaining'] = (pd.to_datetime(df['Calculated Due Date']) - pd.to_datetime(today)).dt.days

        # --- 4. FILTERS ---
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filters")
        
        # Filter: Inspector
        selected_inspector = st.sidebar.multiselect("Filter by Inspector", options=df[col_inspector].unique())
        if selected_inspector:
            df = df[df[col_inspector].isin(selected_inspector)]

        # Filter: Status Category
        status_options = df[col_status].unique()
        selected_status = st.sidebar.multiselect("Filter by Status (Major/Minor)", options=status_options)
        if selected_status:
            df = df[df[col_status].isin(selected_status)]

        # Filter: Buffer Time / Urgency
        buffer_choice = st.sidebar.radio("Show Due Within:", ["All", "1 Month", "3 Months", "Overdue ⚠️"])
        
        if buffer_choice == "1 Month":
            df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 30)]
        elif buffer_choice == "3 Months":
            df = df[(df['Days Remaining'] >= 0) & (df['Days Remaining'] <= 90)]
        elif buffer_choice == "Overdue ⚠️":
            df = df[df['Days Remaining'] < 0]

        # --- 5. MAIN DASHBOARD ---
        
        # KPI Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Inspections", len(df))
        
        # Count Majors (Case insensitive search)
        major_count = df[df[col_status].astype(str).str.contains("MAJOR", case=False, na=False)].shape[0]
        m2.metric("Major Defects", major_count)
        
        # Count Overdue
        overdue_count = df[df['Days Remaining'] < 0].shape[0]
        m3.metric("Overdue Items", overdue_count, delta_color="inverse")

        # Display Data Table
        st.subheader("📋 Inspection Data")
        
        # Formatting for display
        display_cols = [col_insp_date, col_status, 'Calculated Due Date', 'Days Remaining', col_reply, col_inspector, col_defect_yn]
        
        # Style the dataframe
        def highlight_rows(val):
            if val < 0: return 'background-color: #ffcccc' # Red for overdue
            if val < 30: return 'background-color: #ffffcc' # Yellow for urgent
            return ''

        st.dataframe(
            df[display_cols].style.applymap(highlight_rows, subset=['Days Remaining']),
            use_container_width=True
        )

        # Download Button
        st.download_button(
            label="📥 Download Filtered Report",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name='jkkp_filtered_report.csv',
            mime='text/csv'
        )

    except Exception as e:
        st.error(f"Error reading file: {e}")
        st.warning("Ensure your Excel file is not password protected and has headers.")

else:
    st.info("👆 Please upload your JKKP Master Excel file to begin.")
