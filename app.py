import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="JKKP Inspection Tracker", layout="wide", page_icon="🛡️")
st.title("🛡️ JKKP Inspection & Defect Tracker")

# --- INSTRUCTIONS ---
with st.expander("ℹ️ Help / Instructions"):
    st.markdown("""
    * **Upload:** Supports **.xlsx** (Excel) and **.csv**.
    * **Fix for Errors:** If Excel upload fails, save your file as **CSV** and upload that.
    * **Filters:** The app automatically creates a "Yes/No" filter based on the Status column.
    """)

# --- 1. FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload Excel or CSV File", type=['xlsx', 'xls', 'csv'])

if uploaded_file:
    df = None
    try:
        # --- A. FILE READING (Robust Mode) ---
        # 1. Try Loading as CSV
        if uploaded_file.name.lower().endswith('.csv'):
            preview = pd.read_csv(uploaded_file, header=None, nrows=15)
            header_row = 0
            for i, row in preview.iterrows():
                row_str = row.astype(str).str.upper().tolist()
                if any("ANNUAL" in x for x in row_str) or any("TARIKH" in x for x in row_str):
                    header_row = i
                    break
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=header_row)

        # 2. Try Loading as Excel
        else:
            try:
                # Detect Header
                preview = pd.read_excel(uploaded_file, header=None, nrows=15)
                header_row = 4  # Default guess
                for i, row in preview.iterrows():
                    row_str = row.astype(str).str.upper().tolist()
                    if any("ANNUAL" in x for x in row_str) or any("TARIKH" in x for x in row_str):
                        header_row = i
                        break
                
                uploaded_file.seek(0)
                df = pd.read_excel(uploaded_file, header=header_row)
                
            except ImportError:
                st.error("❌ Missing 'openpyxl' library.")
                st.warning("👉 **Quick Fix:** Save your Excel file as a **CSV** and upload it again.")
                st.stop()
            except Exception as e:
                st.error(f"Error reading Excel: {e}")
                st.warning("👉 **Quick Fix:** Save your file as **CSV** and retry.")
                st.stop()

    except Exception as e:
        st.error(f"Critical Error: {e}")
        st.stop()

    # --- B. APP LOGIC ---
    if df is not None:
        st.sidebar.success("File Loaded!")

        # 1. MAP COLUMNS
        st.sidebar.header("1. Map Columns")
        cols = list(df.columns)
        
        def find_col(terms):
            for i, c in enumerate(cols):
                if any(t in str(c).upper() for t in terms): return i
            return 0

        # Selectors
        c_date = st.sidebar.selectbox("Inspection Date", cols, index=find_col(['ANNUAL', 'TARIKH', 'INSPECTION']))
        c_status = st.sidebar.selectbox("Inspection Status", cols, index=find_col(['DEFECTS STATUS', 'STATUS', 'KEADAAN']))
        c_reply = st.sidebar.selectbox("Reply Date", cols, index=find_col(['REPLY', 'BALAS']))
        c_insp = st.sidebar.selectbox("Inspector / CP", cols, index=find_col(['INSPECTOR', 'PEMERIKSA']))

        # 2. DATA PROCESSING
        # Clean Dates
        for c in [c_date, c_reply]:
            df[c] = pd.to_datetime(df[c], errors='coerce').dt.date

        # --- NEW: GENERATE 'YES/NO' COLUMN ---
        def categorize_defect(val):
            s = str(val).upper()
            if pd.isna(val) or val == "" or s == 'NAN': return "Blank"
            if any(x in s for x in ['NO DEFECT', 'TIADA', '/', 'SAFE', 'OK', 'GOOD']): return "No"
            if any(x in s for x in ['MAJOR', 'MINOR', 'NOTICE', 'X', 'YES', 'ADA', 'FAIL']): return "Yes"
            return "Other" # For unclear text

        df['Defect Found?'] = df[c_status].apply(categorize_defect)

        # Logic: Calculate Due Date
        def get_due_date(row):
            start = row[c_date]
            stat = str(row[c_status]).upper()
            if pd.isnull(start): return None
            
            if "MAJOR" in stat: return start + relativedelta(months=1)
            if "MINOR" in stat: return start + relativedelta(months=3)
            if "NOTICE" in stat: return start + relativedelta(weeks=2)
            # Default to 1 year if No Defect or Unknown
            return start + relativedelta(years=1)

        df['Due Date'] = df.apply(get_due_date, axis=1)
        df['Days Left'] = (pd.to_datetime(df['Due Date']) - pd.to_datetime(date.today())).dt.days

        # 3. FILTERS
        st.sidebar.markdown("---")
        st.sidebar.header("2. Filters")

        # A. Filter: Defect Yes/No (The one you asked for!)
        f_yn = st.sidebar.multiselect("Defect Found? (Yes/No)", options=["Yes", "No", "Blank", "Other"])
        if f_yn:
            df = df[df['Defect Found?'].isin(f_yn)]

        # B. Filter: Specific Category (Major/Minor)
        # We perform a robust check for these keywords
        status_types = ["Major", "Minor",
