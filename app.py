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
    * **Target Column:** This app looks for **"ANNUAL INSPECTION"** and ignores "1st Schedule".
    * **Fix for Errors:** If Excel upload fails, save your file as **CSV** and upload that.
    * **Styling:** If the colored rows disappear, it means there was a conflict in your column selection, but the data will still be visible.
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
                # Prioritize "ANNUAL" and "INSPECTION", exclude "1ST SCHEDULE" in row detection if possible
                if any("ANNUAL" in x for x in row_str) and any("INSPECTION" in x for x in row_str):
                    header_row = i
                    break
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=header_row)

        # 2. Try Loading as Excel
        else:
            try:
                preview = pd.read_excel(uploaded_file, header=None, nrows=15)
                header_row = 4  # Default guess
                for i, row in preview.iterrows():
                    row_str = row.astype(str).str.upper().tolist()
                    if any("ANNUAL" in x for x in row_str) and any("INSPECTION" in x for x in row_str):
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
        
        # Helper: Find column excluding specific terms
        def find_col(terms, exclude_terms=None):
            if exclude_terms is None: exclude_terms = []
            for i, c in enumerate(cols):
                c_upper = str(c).upper()
                if any(ex in c_upper for ex in exclude_terms): continue
                if any(t in c_upper for t in terms): return i
            return 0

        # Selectors
        c_date = st.sidebar.selectbox(
            "Annual Inspection Date", 
            cols, 
            index=find_col(['ANNUAL', 'TARIKH PEMERIKSAAN'], exclude_terms=['1ST SCHEDULE', 'JADUAL PERTAMA'])
        )
        
        c_status = st.sidebar.selectbox("Inspection Status", cols, index=find_col(['DEFECTS STATUS', 'STATUS', 'KEADAAN']))
        c_reply = st.sidebar.selectbox("Reply Date", cols, index=find_col(['REPLY', 'BALAS']))
        c_insp = st.sidebar.selectbox("Inspector / CP", cols, index=find_col(['INSPECTOR', 'PEMERIKSA']))

        # 2. DATA PROCESSING
        # Clean Dates
        for c in [c_date, c_reply]:
            df[c] = pd.to_datetime(df[c], errors='coerce').dt.date

        # Yes/No Logic
        def categorize_defect(val):
            s = str(val).upper()
            if pd.isna(val) or val == "" or s == 'NAN': return "Blank"
            if any(x in s for x in ['NO DEFECT', 'TIADA', '/', 'SAFE', 'OK', 'GOOD']): return "No"
            if any(x in s for x in ['MAJOR', 'MINOR', 'NOTICE', 'X', 'YES', 'ADA', 'FAIL']): return "Yes"
            return "Other" 

        df['Defect Found?'] = df[c_status].apply(categorize_defect)

        # Due Date Logic
        def get_due_date(row):
            start = row[c_date]
            stat = str(row[c_status]).upper()
            if pd.isnull(start): return None
            
            if "MAJOR" in stat: return start + relativedelta(months=1)
            if "MINOR" in stat: return start + relativedelta(months=3)
            if "NOTICE" in stat: return start + relativedelta(weeks=2)
            return start + relativedelta(years=1)

        df['Due Date'] = df.apply(get_due_date, axis=1)
        df['Days Left'] = (pd.to_datetime(df['Due Date']) - pd.to_datetime(date.today())).dt.days

        # 3. FILTERS
        st.sidebar.markdown("---")
        st.sidebar.header("2. Filters")

        # Filters
        f_yn = st.sidebar.multiselect("Defect Found? (Yes/No)", options=["Yes", "No", "Blank", "Other"])
        if f_yn: df = df[df['Defect Found?'].isin(f_yn)]

        status_types = ["Major", "Minor", "Notice", "No Defect"]
        f_cat = st.sidebar.multiselect("Inspection Category", options=status_types)
        if f_cat:
            mask = pd.Series([False] * len(df))
            for cat in f_cat:
                mask = mask | df[c_status].astype(str).str.contains(cat, case=False, na=False)
            df = df[mask]

        f_insp = st.sidebar.multiselect("Inspector Name", options=df[c_insp].astype(str).unique())
        if f_insp: df = df[df[c_insp].astype(str).isin(f_insp)]
            
        f_reply = st.sidebar.radio("Reply Status:", ["All", "Replied", "Not Replied"])
        if f_reply == "Replied": df = df[df[c_reply].notna()]
        elif f_reply == "Not Replied": df = df[df[c_reply].isna()]

        f_buffer = st.sidebar.select_slider("Deadline Buffer:", options=["All", "Overdue", "1 Month", "3 Months"])
        if f_buffer == "Overdue": df = df[df['Days Left'] < 0]
        elif f_buffer == "1 Month": df = df[(df['Days Left'] >= 0) & (df['Days Left'] <= 30)]
        elif f_buffer == "3 Months": df = df[(df['Days Left'] >= 0) & (df['Days Left'] <= 90)]

        # 4. MAIN DISPLAY
        m1, m2, m3 = st.columns(3)
        m1.metric("Filtered Rows", len(df))
        m2.metric("Defects (Yes)", len(df[df['Defect Found?'] == "Yes"]))
        m3.metric("Urgent (Overdue)", len(df[df['Days Left'] < 0]), delta_color="inverse")

        # --- CRASH FIX: SAFE COLUMN SELECTION ---
        # 1. Define columns to show
        desired_cols = [c_date, c_status, 'Defect Found?', 'Due Date', 'Days Left', c_reply, c_insp]
        
        # 2. REMOVE DUPLICATES (This prevents the KeyError)
        # We use dict.fromkeys to remove duplicates while keeping order
        show_cols = list(dict.fromkeys(desired_cols))
        
        # 3. Style function
        def style_rows(row):
            d = row['Days Left']
            if pd.notnull(d) and d < 0: return ['background-color: #ffcccc'] * len(row) # Red
            if pd.notnull(d) and d < 30: return ['background-color: #ffffcc'] * len(row) # Yellow
            return [''] * len(row)

        st.subheader("📋 Inspection Data")
        
        # 4. SAFE DISPLAY BLOCK
        try:
            st.dataframe(
                df[show_cols].style.apply(style_rows, axis=1), 
                use_container_width=True
            )
        except Exception as e:
            # If styling fails (rare edge case), show plain data instead of crashing
            st.warning("⚠️ Highlighting disabled due to column conflict, but here is your data:")
            st.dataframe(df[show_cols], use_container_width=True)

        st.download_button("📥 Download Filtered Data", df.to_csv(index=False), "filtered_jkkp_data.csv", "text/csv")
