import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime, date
import plotly.express as px
import os
from PIL import Image

# --- Smart Path Configuration (Handles file paths reliably) ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # This will run in environments where __file__ is not defined (like some notebooks)
    script_dir = os.getcwd()
LOGO_PATH = os.path.join(script_dir, "logo.png")


# --- Configuration & Constants ---
DB_FILE = "persistent_system.db"
RFI_TABLE_NAME = "rfi_data"
COMPANY_NAME = "Mcdermott"

# --- Column Names (Update these if your Excel columns are different) ---
COL_STATUS = 'HELP CELL ="REJECTED"'
COL_REASON = 'MCD INSPECTION REASON SURVEILLANCE INSPECTION RESOLUTION'
COL_SUBCONTRACTOR = 'SUBCONTRACTOR name'
COL_NCR = 'QOC NCR number'
COL_WEEK = 'WEEK number'
COL_INSP_DATE = 'DATE of INSPECTION'
COL_RFI_NUMBER = "RFI number" 
COL_DISCIPLINE = "DISCIPLINE"

# --- List of columns required for the dashboard to function (for performance optimization) ---
REQUIRED_COLUMNS = list(set([
    COL_STATUS, COL_REASON, COL_SUBCONTRACTOR, 
    COL_NCR, COL_WEEK, COL_INSP_DATE, 
    COL_RFI_NUMBER, COL_DISCIPLINE
]))

# --- Page Configuration ---
try:
    logo_image = Image.open(LOGO_PATH)
    st.set_page_config(page_title=f"{COMPANY_NAME} Inspection Dashboard", page_icon=logo_image, layout="wide")
except FileNotFoundError:
    st.set_page_config(page_title=f"{COMPANY_NAME} Inspection Dashboard", layout="wide")

# --- Helper Functions ---

def init_db():
    """Initializes the database and tables if they don't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
        c.execute(f'''CREATE TABLE IF NOT EXISTS {RFI_TABLE_NAME} (placeholder_column TEXT)''')
        if c.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
            admin_pw = hashlib.sha256("admin123".encode()).hexdigest()
            c.execute("INSERT INTO users VALUES (?, ?, ?)", ("admin", admin_pw, "Admin"))

@st.cache_data(ttl=300)
def load_data_from_db(full_data=False) -> pd.DataFrame:
    """
    Loads data from the database.
    - If full_data is False (default), loads only a subset of required columns for performance.
    - If full_data is True, loads all columns.
    """
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    
    with sqlite3.connect(DB_FILE) as conn:
        try:
            db_columns = pd.read_sql_query(f"PRAGMA table_info({RFI_TABLE_NAME})", conn)['name'].tolist()
            
            if full_data:
                cols_to_load = db_columns
            else:
                cols_to_load = [col for col in REQUIRED_COLUMNS if col in db_columns]

            if not cols_to_load: return pd.DataFrame()

            query = f"SELECT {', '.join(f'`{col}`' for col in cols_to_load)} FROM {RFI_TABLE_NAME}"
            df = pd.read_sql_query(query, conn)

            if COL_STATUS in df.columns:
                df['cleaned_status'] = df[COL_STATUS].astype(str).str.strip().str.upper()
                df['cleaned_status'] = df['cleaned_status'].astype('category')
            
            if not full_data: # Only optimize these if not loading full data
                if COL_SUBCONTRACTOR in df.columns: df[COL_SUBCONTRACTOR] = df[COL_SUBCONTRACTOR].astype('category')
                if COL_DISCIPLINE in df.columns: df[COL_DISCIPLINE] = df[COL_DISCIPLINE].astype('category')

            return df
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return pd.DataFrame()

def import_df_to_db(df: pd.DataFrame, mode='replace'):
    """Imports a DataFrame into the database."""
    with sqlite3.connect(DB_FILE) as conn:
        df.to_sql(RFI_TABLE_NAME, conn, if_exists=mode, index=False)
    st.cache_data.clear()

def add_new_rfi(new_data: dict):
    """Appends a single new RFI record to the database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # To append a new row, we need to make sure all columns match the existing table.
            # It's safer to load the full table, append, and save back.
            full_df = pd.read_sql_query(f"SELECT * FROM {RFI_TABLE_NAME}", conn)
            new_df = pd.DataFrame([new_data])
            updated_df = pd.concat([full_df, new_df], ignore_index=True)
            updated_df.to_sql(RFI_TABLE_NAME, conn, if_exists='replace', index=False)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Database error while adding new record: {e}")
        return False

def clear_rfi_data():
    """Deletes all RFI data from the database."""
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(f"DROP TABLE IF EXISTS {RFI_TABLE_NAME}")
        c.execute(f'''CREATE TABLE IF NOT EXISTS {RFI_TABLE_NAME} (placeholder_column TEXT)''')
    st.cache_data.clear()

# --- Authentication ---
def login():
    try:
        st.image(LOGO_PATH, width=150)
    except Exception:
        st.warning(f"Could not find logo at '{LOGO_PATH}'. Please ensure it's in the same directory as the app.")
    st.title(f"Welcome to {COMPANY_NAME}")
    st.header("Inspection Dashboard Login")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login", type="primary"):
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, hashed_pw))
            result = c.fetchone()
        if result:
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.session_state['role'] = result[0]
            st.session_state['page'] = "Dashboard"
            st.rerun()
        else:
            st.error("Invalid credentials")

# --- Main Application ---
def main():
    init_db()
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    if not st.session_state['logged_in']:
        login()
        return

    with st.sidebar:
        try:
            st.image(LOGO_PATH, width=100)
        except Exception:
            pass # Don't show error in sidebar if logo is missing
        st.title(COMPANY_NAME)
        st.divider()
        st.header(f"Welcome, {st.session_state['username']}")
        st.write(f"Role: **{st.session_state['role']}**")
        page_options = ["Dashboard", "Data Explorer", "Add New RFI", "Import & Manage Data"]
        page = st.radio("Menu", page_options, key="page_selector", 
                        index=page_options.index(st.session_state.get('page', 'Dashboard')))
        
        if st.button("Logout"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

    # --- Page Routing ---
    if page == "Dashboard":
        render_dashboard()
    elif page == "Data Explorer":
        render_data_explorer()
    elif page == "Add New RFI":
        render_add_new_rfi()
    elif page == "Import & Manage Data":
        render_import_manage_data()

def render_dashboard():
    st.title("📊 Main Dashboard")
    df = load_data_from_db(full_data=False) # Load optimized data
    if df.empty:
        st.warning("⚠️ No data found. Go to 'Import & Manage Data' to import an Excel file.")
        return
    if 'cleaned_status' not in df.columns:
        st.error(f"Critical Error: The status column '{COL_STATUS}' was not found or could not be processed.")
        return

    st.success(f"Displaying analysis for {len(df)} records.")
    
    total_rfis = len(df)
    rejected_count = df[df['cleaned_status'] == 'REJECTED'].shape[0]
    accepted_count = df[(df['cleaned_status'] != 'REJECTED') & (df['cleaned_status'].notna()) & (df['cleaned_status'] != 'NAN') & (df['cleaned_status'] != '')].shape[0]
    accepted_perc = (accepted_count / total_rfis * 100) if total_rfis > 0 else 0
    open_ncr_count = df[df[COL_NCR].notna()].shape[0] if COL_NCR in df.columns else 0

    st.subheader("Key Performance Indicators")
    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Total RFIs", total_rfis)
    kpi_cols[1].metric("Accepted %", f"{accepted_perc:.1f}%")
    kpi_cols[2].metric("Rejected RFIs", rejected_count, delta_color="inverse")
    kpi_cols[3].metric("Open NCRs", open_ncr_count, delta_color="inverse")

    st.divider()
    st.subheader("🔔 Interactive Notifications & Actions")
    st.info("Click a button to instantly filter and view the relevant data in the 'Data Explorer' page.")
    overdue_count = 0
    if COL_INSP_DATE in df.columns:
        df[COL_INSP_DATE] = pd.to_datetime(df[COL_INSP_DATE], errors='coerce')
        overdue_df = df[(df[COL_INSP_DATE] < datetime.now()) & (~df['cleaned_status'].isin(['ACCEPTED', 'REJECTED']))]
        overdue_count = len(overdue_df)
    
    action_cols = st.columns(3)
    if action_cols[0].button(f"View {rejected_count} Rejected RFIs"):
        st.session_state['filter_type'] = 'rejected'
        st.session_state['page'] = "Data Explorer"
        st.rerun()
    if action_cols[1].button(f"View {open_ncr_count} Open NCRs"):
        st.session_state['filter_type'] = 'ncr'
        st.session_state['page'] = "Data Explorer"
        st.rerun()
    if action_cols[2].button(f"View {overdue_count} Overdue RFIs"):
        st.session_state['filter_type'] = 'overdue'
        st.session_state['page'] = "Data Explorer"
        st.rerun()
    
    st.divider()
    st.subheader("Performance Charts")
    chart_cols = st.columns(2)
    
    def simplify_status(status):
        if status == 'REJECTED': return 'Rejected'
        elif status in ['NAN', '', 'NONE', 'PENDING']: return 'Pending'
        else: return 'Accepted'
    
    df['pie_status'] = df['cleaned_status'].apply(simplify_status)
    status_counts = df['pie_status'].value_counts()
    
    if not status_counts.empty:
        fig_status = px.pie(values=status_counts.values, names=status_counts.index, title="RFI Status Distribution",
                            color=status_counts.index, color_discrete_map={'Accepted': '#2E8B57', 'Rejected': '#DC143C', 'Pending': '#FF8C00'})
        chart_cols[0].plotly_chart(fig_status, use_container_width=True)

    if COL_WEEK in df.columns:
        df[COL_WEEK] = pd.to_numeric(df[COL_WEEK], errors='coerce')
        weekly_counts = df.dropna(subset=[COL_WEEK])[COL_WEEK].astype(int).value_counts().sort_index()
        if not weekly_counts.empty:
            fig_weekly = px.bar(x=weekly_counts.index, y=weekly_counts.values, title="RFIs Submitted per Week", labels={'x': 'Week Number', 'y': 'Number of RFIs'})
            chart_cols[1].plotly_chart(fig_weekly, use_container_width=True)
    
    st.subheader("Drill-Down Analysis")
    analysis_cols = st.columns(2)

    if rejected_count > 0 and COL_REASON in df.columns:
        rejection_reasons = df[df['cleaned_status'] == 'REJECTED'][COL_REASON].dropna().value_counts().head(5)
        if not rejection_reasons.empty:
            analysis_cols[0].write("Top 5 Rejection Reasons")
            analysis_cols[0].table(rejection_reasons)
    
    if rejected_count > 0 and COL_SUBCONTRACTOR in df.columns:
        sub_performance = df[df['cleaned_status'] == 'REJECTED'].groupby(COL_SUBCONTRACTOR).size().sort_values(ascending=False)
        if not sub_performance.empty:
            analysis_cols[1].write("Subcontractor Rejection Counts (Worst First)")
            analysis_cols[1].table(sub_performance)

def render_data_explorer():
    st.title("🔍 Data Explorer")
    df = load_data_from_db(full_data=True) # Load full data for exploration
    
    if 'cleaned_status' not in df.columns and COL_STATUS in df.columns:
        df['cleaned_status'] = df[COL_STATUS].astype(str).str.strip().str.upper()

    filter_type = st.session_state.get('filter_type')

    if filter_type:
        if st.button("Back to Dashboard / Clear Filter"):
            st.session_state['filter_type'] = None
            st.session_state['page'] = "Dashboard"
            st.rerun()

        st.info(f"Applying filter for: **{filter_type.upper()}**")
        
        df_to_display = df
        if filter_type == 'rejected':
            df_to_display = df[df['cleaned_status'] == 'REJECTED']
        elif filter_type == 'ncr' and COL_NCR in df.columns:
            df_to_display = df[df[COL_NCR].notna()]
        elif filter_type == 'overdue' and COL_INSP_DATE in df.columns:
            df[COL_INSP_DATE] = pd.to_datetime(df[COL_INSP_DATE], errors='coerce')
            df_to_display = df[(df[COL_INSP_DATE] < datetime.now()) & (~df['cleaned_status'].isin(['ACCEPTED', 'REJECTED']))]
        
        st.success(f"Filtered to {len(df_to_display)} records.")
        
        def highlight_status(s):
            val = str(s).strip().upper()
            if 'REJECTED' in val: return 'background-color: #FF4B4B; color: white'
            elif val not in ['NAN', '', 'NONE', 'PENDING']: return 'background-color: #2E8B57; color: white'
            return ''
        st.dataframe(df_to_display.style.applymap(highlight_status, subset=[COL_STATUS]))

    else:
        st.info(f"Displaying all {len(df)} records. Styling is disabled for performance. Use Dashboard buttons to filter and enable styling.")
        st.dataframe(df)

def render_add_new_rfi():
    st.title("✍️ Add a New RFI Record")
    st.info("Fill out the form below and click 'Save Record' to add a new entry to the database.")

    with st.form(key="new_rfi_form", clear_on_submit=True):
        st.subheader("RFI Details")
        col1, col2 = st.columns(2)
        rfi_number = col1.text_input(f"**{COL_RFI_NUMBER}** (Required)")
        discipline = col2.text_input(f"**{COL_DISCIPLINE}**")
        subcontractor = col1.text_input(f"**{COL_SUBCONTRACTOR}**")
        inspection_date = col2.date_input(f"**{COL_INSP_DATE}**", value=None)
        
        submitted = st.form_submit_button("💾 Save Record")
        if submitted:
            if not rfi_number:
                st.error("RFI Number is a required field.")
            else:
                new_record = {
                    COL_RFI_NUMBER: rfi_number,
                    COL_DISCIPLINE: discipline,
                    COL_SUBCONTRACTOR: subcontractor,
                    COL_INSP_DATE: inspection_date.strftime("%Y-%m-%d") if inspection_date else None,
                    COL_STATUS: "PENDING",
                    COL_WEEK: datetime.now().isocalendar()[1]
                }
                if add_new_rfi(new_record):
                    st.success(f"✅ Successfully added RFI: {rfi_number}")

def render_import_manage_data():
    st.title("📦 Import & Manage Data")
    st.subheader("1. Import New Data")
    st.info("This will **replace** all existing data in the database with the content of the new file.")
    header_row = st.number_input("Enter the Excel row number that contains the column headers", min_value=1, value=1)
    uploaded_file = st.file_uploader("Upload Excel File", type=['xlsx'])
    if uploaded_file:
        try:
            new_df = pd.read_excel(uploaded_file, header=header_row - 1)
            st.write("File Preview:")
            st.dataframe(new_df.head())
            if st.button("✅ Confirm and Import to Database"):
                import_df_to_db(new_df, mode='replace')
                st.success(f"Successfully imported {len(new_df)} records into the database!")
                st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {e}")
    st.divider()
    st.subheader("2. Current Data in Database")
    df = load_data_from_db(full_data=True)
    if df.empty:
        st.warning("The database is currently empty.")
    else:
        st.info(f"Displaying a preview of the {len(df)} records currently in the database.")
        st.dataframe(df.head(100))
    st.divider()
    st.subheader("3. Danger Zone")
    if st.button("🗑️ Delete All Data from Database"):
        clear_rfi_data()
        st.success("All data has been cleared.")
        st.rerun()

if __name__ == "__main__":
    main()







