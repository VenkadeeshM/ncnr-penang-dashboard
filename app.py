import datetime
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Page Configuration
st.set_page_config(page_title="NCNR Penang Cloud Dashboard", layout="wide")

st.title("⚡ NCNR Penang Cloud Operational Dashboard")
st.caption("🌐 Cloud Hosted | Live Multi-User Sync Enabled")

# Initialize GSheets connection using Streamlit Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def load_data():
    return conn.read(worksheet="Detail1")

try:
    df = load_data()
except Exception as e:
    st.error("❌ Failed to read Google Sheet. Please verify public access settings.")
    st.info(f"Error detail: {e}")
    st.stop()

# Ensure required tracking columns exist
if "Status (Final)" not in df.columns:
    df["Status (Final)"] = "Open"
df["Status (Final)"] = df["Status (Final)"].fillna("Open")

if "Last Updated Time" not in df.columns:
    df["Last Updated Time"] = None

# Initialize navigation state
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "selected_meter" not in st.session_state:
    st.session_state.selected_meter = None

# Top Metrics Row
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_count = len(df)
completed_count = len(df[df["Status (Final)"].isin(["Completed", "Resolved"])])
in_progress_count = len(df[df["Status (Final)"].isin(["In Progress", "Pending Site Visit"])])
open_count = total_count - completed_count - in_progress_count

col_m1.metric("Total Meters", f"{total_count:,}")
col_m2.metric("🔴 Open", f"{open_count:,}")
col_m3.metric("🟡 In Progress", f"{in_progress_count:,}")
col_m4.metric("🟢 Completed", f"{completed_count:,}")

st.divider()

# ---------------------------------------------------------
# STEP 1: SUMMARY OF ISSUES
# ---------------------------------------------------------
st.header("Step 1: Summary of Issues")
st.write("Click a category button to view its meter list:")

categories = df['Issue Category'].value_counts()
cols = st.columns(3)

for idx, (cat_name, count) in enumerate(categories.items()):
    col = cols[idx % 3]
    with col:
        if st.button(f"{cat_name}\n({count:,} meters)", key=cat_name, use_container_width=True):
            st.session_state.selected_category = cat_name
            st.session_state.selected_meter = None

st.divider()

# ---------------------------------------------------------
# STEP 2: LIST OF ACCOUNTS
# ---------------------------------------------------------
if st.session_state.selected_category:
    st.header(f"Step 2: Accounts for '{st.session_state.selected_category}'")
    
    sub_df = df[df['Issue Category'] == st.session_state.selected_category].copy()
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        stations = ["All Stations"] + list(sub_df['Station Description (Finalized)'].dropna().unique())
        selected_station = st.selectbox("Filter by Station:", stations)
    with col_f2:
        status_filter = st.selectbox("Filter by Status:", ["All Statuses", "Open", "In Progress", "Pending Site Visit", "Completed"])

    if selected_station != "All Stations":
        sub_df = sub_df[sub_df['Station Description (Finalized)'] == selected_station]
    if status_filter != "All Statuses":
        sub_df = sub_df[sub_df['Status (Final)'] == status_filter]

    st.write(f"Showing **{len(sub_df):,}** meters. Click a row below to select:")

    display_cols = ['Meter ID', 'Station Description (Finalized)', 'PIC (Final)', 'Status (Final)', 'Last Updated Time']
    event = st.dataframe(
        sub_df[display_cols],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(event.selection['rows']) > 0:
        selected_index = event.selection['rows'][0]
        st.session_state.selected_meter = sub_df.iloc[selected_index]['Meter ID']

    st.divider()

# ---------------------------------------------------------
# STEP 3: ACCOUNT DETAILS & UPDATE STATUS
# ---------------------------------------------------------
if st.session_state.selected_meter:
    st.header(f"Step 3: Update Account - {st.session_state.selected_meter}")

    meter_row = df[df['Meter ID'] == st.session_state.selected_meter].iloc[0]

    with st.form("update_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"**Station:** {meter_row.get('Station Description (Finalized)', 'N/A')}")
            st.write(f"**Issue Category:** {meter_row.get('Issue Category', 'N/A')}")
            st.write(f"**Current PIC:** {meter_row.get('PIC (Final)', 'N/A')}")
        
        with col_b:
            st.write(f"**Site Findings:** {meter_row.get('Site Findings (Categorised) - Final', 'N/A')}")
            st.write(f"**Mitigation Action:** {meter_row.get('Mitigation Action (Final)', 'N/A')}")
            st.write(f"**Last Saved Update:** {meter_row.get('Last Updated Time', 'Never')}")

        st.subheader("Update Work Progress")
        
        status_options = ["Open", "In Progress", "Pending Site Visit", "Completed"]
        current_status = str(meter_row.get('Status (Final)', 'Open'))
        status_index = status_options.index(current_status) if current_status in status_options else 0
        
        new_status = st.selectbox("New Status", status_options, index=status_index)
        updater_name = st.text_input("Updated By (PIC Name / ID):", value=str(meter_row.get('PIC (Final)', '')))
        new_remarks = st.text_area("Remarks / Notes", value=str(meter_row.get('remark deployment 1', '')))

        submitted = st.form_submit_button("✓ Save Update to Cloud")

        if submitted:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            df.loc[df['Meter ID'] == st.session_state.selected_meter, 'Status (Final)'] = new_status
            df.loc[df['Meter ID'] == st.session_state.selected_meter, 'PIC (Final)'] = updater_name
            df.loc[df['Meter ID'] == st.session_state.selected_meter, 'remark deployment 1'] = new_remarks
            df.loc[df['Meter ID'] == st.session_state.selected_meter, 'Last Updated Time'] = now_str

            # Save back to Google Sheets database live
            conn.update(worksheet="Detail1", data=df)

            st.success(f"Successfully updated {st.session_state.selected_meter} in the cloud!")
            st.cache_data.clear()
            st.rerun()
