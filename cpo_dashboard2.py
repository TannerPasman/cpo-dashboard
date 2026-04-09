import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="CPO Surveillance Dashboard",
    page_icon="🦠",
    layout="wide"
)

# ── Helper ──────────────────────────────────────────────────────────────────
def clean(val):
    if val is None:
        return "—"
    if isinstance(val, float) and pd.isna(val):
        return "—"
    s = str(val).strip()
    if s.lower() in ["nan", "none", "na", "n/a", ""]:
        return "—"
    return s

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        border: 1px solid #e9ecef;
    }
    .detail-label { color: #6c757d; font-size: 0.78rem; margin-bottom: 2px; }
    .detail-value { font-size: 0.95rem; font-weight: 500; }
    div[data-testid="stExpander"] { border: 1px solid #e9ecef; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    if hasattr(path, "name") and path.name.endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    date_cols = ["event_date"] + [f"facility{i}_{x}" for i in [1,2,3] for x in ["admission_date","discharge_date"]]
    for dc in date_cols:
        if dc in df.columns:
            parsed = pd.to_datetime(df[dc], format="%Y-%m-%d", errors="coerce")
            if parsed.isna().all():
                parsed = pd.to_datetime(df[dc], format="%m/%d/%Y", errors="coerce")
            if parsed.isna().all():
                parsed = pd.to_datetime(df[dc], errors="coerce")
            df[dc] = parsed
    return df

# ── File loader in sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    uploaded = st.file_uploader("Upload your data file (.xlsx or .csv)", type=["xlsx", "csv"])
    st.markdown("---")

if uploaded is None:
    st.title("🦠 CPO Surveillance Dashboard")
    st.info("Upload your Excel file using the sidebar to get started.")
    st.stop()

df = load_data(uploaded)

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Filters")
    if st.button("🔄 Reset all filters"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # Date range
    if "event_date" in df.columns and df["event_date"].notna().any():
        min_date = df["event_date"].min().date()
        max_date = df["event_date"].max().date()
        date_range = st.date_input("Event date range", value=(min_date, max_date), key="date_range")
        if len(date_range) == 2:
            df = df[
                (df["event_date"].dt.date >= date_range[0]) &
                (df["event_date"].dt.date <= date_range[1])
            ]

    # Organism
    if "organism" in df.columns:
        orgs = ["All"] + sorted(df["organism"].dropna().unique().tolist())
        sel_org = st.selectbox("Organism", orgs)
        if sel_org != "All":
            df = df[df["organism"] == sel_org]

    # Mechanism
    if "mechanism" in df.columns:
        mechs = ["All"] + sorted(df["mechanism"].dropna().unique().tolist())
        sel_mech = st.selectbox("Mechanism", mechs)
        if sel_mech != "All":
            df = df[df["mechanism"] == sel_mech]

    # County
    if "county_assigned" in df.columns:
        counties = ["All"] + sorted(df["county_assigned"].dropna().unique().tolist())
        sel_county = st.selectbox("County assigned", counties)
        if sel_county != "All":
            df = df[df["county_assigned"] == sel_county]

    # Confirmed CPO only
    if "confirmed_cpo" in df.columns:
        confirmed_only = st.checkbox("Confirmed CPO only")
        if confirmed_only:
            df = df[df["confirmed_cpo"].astype(str).str.lower().isin(["yes", "true", "1", "y"])]

# ── Tabs ──────────────────────────────────────────────────────────────────────
st.title("🦠 CPO Surveillance Dashboard")
tab1, tab2, tab3 = st.tabs(["📋 Patient Records", "🏥 Facility View", "📈 Outbreak Trends"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Patient Records
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total patients", len(df))
    if "organism" in df.columns:
        col2.metric("Unique organisms", df["organism"].nunique())
    if "county_assigned" in df.columns:
        col3.metric("Counties affected", df["county_assigned"].nunique())
    if "confirmed_cpo" in df.columns:
        confirmed_count = df["confirmed_cpo"].astype(str).str.lower().isin(["yes","true","1","y"]).sum()
        col4.metric("Confirmed CPO", confirmed_count)

    st.markdown("---")

    # Search
    search = st.text_input("🔍 Search by patient ID, organism, county, or mechanism", "")
    display_df = df.copy()
    if search:
        mask = display_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        display_df = display_df[mask]

    # Clickable table — show key columns
    key_cols = [c for c in ["clean_id","event_date","gender","age","race","ethnicity",
                             "county_assigned","organism","mechanism","confirmed_cpo",
                             "specimen_source"] if c in display_df.columns]
    table_df = display_df[key_cols].copy()
    if "event_date" in table_df.columns:
        table_df["event_date"] = table_df["event_date"].dt.strftime("%Y-%m-%d")

    st.dataframe(table_df.reset_index(drop=True), use_container_width=True, height=320)
    st.caption(f"Showing {len(display_df)} of {len(df)} patients")

    # Patient drill-down
    st.markdown("### Patient detail")
    if "clean_id" in df.columns:
        patient_ids = ["— select —"] + sorted(display_df["clean_id"].dropna().astype(str).tolist())
        sel_id = st.selectbox("Select a patient ID to view full record", patient_ids)

        if sel_id != "— select —":
            row = df[df["clean_id"].astype(str) == sel_id].iloc[0]

            # Demographics
            with st.expander("👤 Demographics & event info", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='detail-label'>Patient ID</div><div class='detail-value'>{clean(row.get('clean_id'))}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='detail-label'>Age</div><div class='detail-value'>{clean(row.get('age'))}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='detail-label'>Gender</div><div class='detail-value'>{clean(row.get('gender'))}</div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='detail-label'>Race</div><div class='detail-value'>{clean(row.get('race'))}</div>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='detail-label'>Ethnicity</div><div class='detail-value'>{clean(row.get('ethnicity'))}</div>", unsafe_allow_html=True)
                ev = row.get('event_date')
                ev_str = ev.strftime('%Y-%m-%d') if pd.notna(ev) else '—'
                c2.markdown(f"<div class='detail-label'>Event date</div><div class='detail-value'>{ev_str}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='detail-label'>County assigned</div><div class='detail-value'>{clean(row.get('county_assigned'))}</div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='detail-label'>Other counties</div><div class='detail-value'>{clean(row.get('other_counties'))}</div>", unsafe_allow_html=True)

            # Lab / organism
            with st.expander("🔬 Lab & organism", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='detail-label'>Organism</div><div class='detail-value'>{clean(row.get('organism'))}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='detail-label'>Mechanism</div><div class='detail-value'>{clean(row.get('mechanism'))}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='detail-label'>Specimen source</div><div class='detail-value'>{clean(row.get('specimen_source'))}</div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='detail-label'>Confirmed CPO</div><div class='detail-value'>{clean(row.get('confirmed_cpo'))}</div>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='detail-label'>Performing lab</div><div class='detail-value'>{clean(row.get('performing_lab'))}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='detail-label'>Carbapenem resistant</div><div class='detail-value'>{clean(row.get('carbapenem_resistant'))}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='detail-label'>BPHL resistant</div><div class='detail-value'>{clean(row.get('bphl_result_resistent_to_carbapenem'))}</div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='detail-label'>BPHL mechanism</div><div class='detail-value'>{clean(row.get('bphl_result_mechanism'))}</div>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='detail-label'>Isolate → BPHL JAX</div><div class='detail-value'>{clean(row.get('isolate_forwarded_to_bphl_jax'))}</div>", unsafe_allow_html=True)

            # Risk factors
            with st.expander("⚠️ Risk factors", expanded=True):
                risk_cols = ["wounds","tracheostomy","ventilator_dependent","indwelling_device",
                             "indwelling_device_specified","dialysis","surgery_past_12_months","other_risk_factors"]
                risk_cols = [c for c in risk_cols if c in row.index]
                cols = st.columns(4)
                for i, rc in enumerate(risk_cols):
                    cols[i % 4].markdown(f"<div class='detail-label'>{rc.replace('_',' ').title()}</div><div class='detail-value'>{row.get(rc,'—')}</div>", unsafe_allow_html=True)

            # Investigation
            with st.expander("📁 Investigation"):
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='detail-label'>Investigated</div><div class='detail-value'>{clean(row.get('investigated'))}</div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='detail-label'>Investigator</div><div class='detail-value'>{clean(row.get('investigator'))}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='detail-label'>Med records attached</div><div class='detail-value'>{clean(row.get('medical_records_attached'))}</div>", unsafe_allow_html=True)

            # Facilities
            for i in [1, 2, 3]:
                fac_name_col = f"facility{i}"
                fac_cols = [c for c in df.columns if c.startswith(f"facility{i}") or c.startswith(f"facilty{i}")]
                if fac_cols and pd.notna(row.get(fac_name_col, None)):
                    with st.expander(f"🏥 Facility {i} — {row.get(fac_name_col, '')}"):
                        cols = st.columns(4)
                        for j, fc in enumerate(fac_cols):
                            val = row.get(fc)
                            if pd.notna(val):
                                label = fc.replace(f"facility{i}_","").replace(f"facilty{i}_","").replace("_"," ").title()
                                if hasattr(val, 'strftime'):
                                    val = val.strftime('%Y-%m-%d')
                                cols[j % 4].markdown(f"<div class='detail-label'>{label}</div><div class='detail-value'>{val}</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Facility View
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Facility patient tracker")

    # Build a long-form facility table
    fac_rows = []
    for _, row in df.iterrows():
        for i in [1, 2, 3]:
            fac_col = f"facility{i}"
            adm_col = f"facility{i}_admission_date"
            dis_col = f"facility{i}_discharge_date"
            unit_col = f"facility{i}_unit"
            county_col = f"facility{i}_county"
            iso_col = f"facility{i}_isolation_precautions"
            fac_name = row.get(fac_col)
            if pd.notna(fac_name) and str(fac_name).strip() not in ["", "nan"]:
                adm = row.get(adm_col)
                dis = row.get(dis_col)
                fac_rows.append({
                    "Patient ID": clean(row.get("clean_id")),
                    "Facility": fac_name,
                    "Facility #": f"Facility {i}",
                    "County": row.get(county_col,"—"),
                    "Unit": row.get(unit_col,"—"),
                    "Admission": adm.strftime('%Y-%m-%d') if pd.notna(adm) else "—",
                    "Discharge": dis.strftime('%Y-%m-%d') if pd.notna(dis) else "—",
                    "Isolation precautions": row.get(iso_col,"—"),
                    "Organism": clean(row.get("organism")),
                    "Mechanism": clean(row.get("mechanism")),
                })

    if fac_rows:
        fac_df = pd.DataFrame(fac_rows)

        # Facility selector
        fac_options = ["All facilities"] + sorted(fac_df["Facility"].dropna().unique().tolist())
        sel_fac = st.selectbox("Select a facility", fac_options)
        if sel_fac != "All facilities":
            view_df = fac_df[fac_df["Facility"] == sel_fac]
        else:
            view_df = fac_df.copy()

        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Patient visits", len(view_df))
        c2.metric("Unique patients", view_df["Patient ID"].nunique())
        c3.metric("Organisms detected", view_df["Organism"].nunique())

        st.markdown("---")
        st.dataframe(view_df.reset_index(drop=True), use_container_width=True, height=380)

        # Co-exposure: patients who share a facility
        if sel_fac != "All facilities":
            st.markdown("#### Patients at this facility — organism breakdown")
            org_counts = view_df["Organism"].value_counts().reset_index()
            org_counts.columns = ["Organism","Count"]
            fig = px.bar(org_counts, x="Organism", y="Count", color="Organism",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(showlegend=False, height=280, margin=dict(t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)

        # Timeline for selected facility
        st.markdown("#### Admission timeline")
        timeline_df = fac_df.copy()
        if sel_fac != "All facilities":
            timeline_df = timeline_df[timeline_df["Facility"] == sel_fac]
        timeline_df = timeline_df[timeline_df["Admission"] != "—"].copy()
        if not timeline_df.empty:
            timeline_df["Admission_dt"] = pd.to_datetime(timeline_df["Admission"], errors="coerce")
            timeline_df["Month"] = timeline_df["Admission_dt"].dt.to_period("M").astype(str)
            monthly = timeline_df.groupby(["Month","Organism"]).size().reset_index(name="Cases")
            fig2 = px.bar(monthly, x="Month", y="Cases", color="Organism",
                          color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_layout(height=300, margin=dict(t=10,b=10))
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No facility data found — make sure columns like `facility1`, `facility1_admission_date` etc. are populated.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Outbreak Trends
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Outbreak trends")

    if "event_date" not in df.columns or df["event_date"].isna().all():
        st.warning("No valid event_date column found.")
    else:
        trend_df = df.dropna(subset=["event_date"]).copy()
        trend_df["Month"] = trend_df["event_date"].dt.to_period("M").astype(str)
        trend_df["Week"] = trend_df["event_date"].dt.to_period("W").astype(str)

        granularity = st.radio("Group by", ["Month", "Week"], horizontal=True)
        group_col = granularity

        c1, c2 = st.columns(2)

        # Cases over time by organism
        with c1:
            st.markdown("##### Cases over time by organism")
            if "organism" in trend_df.columns:
                monthly_org = trend_df.groupby([group_col,"organism"]).size().reset_index(name="Cases")
                fig = px.line(monthly_org, x=group_col, y="Cases", color="organism",
                              markers=True, color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(height=320, margin=dict(t=10,b=10), xaxis_title="", legend_title="Organism")
                st.plotly_chart(fig, use_container_width=True)

        # Cases by mechanism
        with c2:
            st.markdown("##### Cases over time by mechanism")
            if "mechanism" in trend_df.columns:
                monthly_mech = trend_df.groupby([group_col,"mechanism"]).size().reset_index(name="Cases")
                fig = px.bar(monthly_mech, x=group_col, y="Cases", color="mechanism",
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(height=320, margin=dict(t=10,b=10), xaxis_title="", legend_title="Mechanism")
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns(2)

        # Cases by county
        with c1:
            st.markdown("##### Cases by county")
            if "county_assigned" in trend_df.columns:
                county_counts = trend_df["county_assigned"].value_counts().reset_index()
                county_counts.columns = ["County","Cases"]
                fig = px.bar(county_counts, x="Cases", y="County", orientation="h",
                             color="Cases", color_continuous_scale="Blues")
                fig.update_layout(height=350, margin=dict(t=10,b=10), yaxis_title="", coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True)

        # Risk factor breakdown
        with c2:
            st.markdown("##### Risk factor prevalence")
            risk_fields = ["wounds","tracheostomy","ventilator_dependent","indwelling_device",
                           "dialysis","surgery_past_12_months"]
            risk_fields = [r for r in risk_fields if r in trend_df.columns]
            risk_summary = {}
            for r in risk_fields:
                yes_count = trend_df[r].astype(str).str.lower().isin(["yes","true","1","y"]).sum()
                risk_summary[r.replace("_"," ").title()] = yes_count
            risk_plot = pd.DataFrame(list(risk_summary.items()), columns=["Risk factor","Count"])
            risk_plot = risk_plot.sort_values("Count", ascending=True)
            fig = px.bar(risk_plot, x="Count", y="Risk factor", orientation="h",
                         color="Count", color_continuous_scale="Oranges")
            fig.update_layout(height=350, margin=dict(t=10,b=10), yaxis_title="", coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        # Epi curve
        st.markdown("##### Epi curve — all cases")
        epi = trend_df.groupby(group_col).size().reset_index(name="Cases")
        fig = px.bar(epi, x=group_col, y="Cases", color_discrete_sequence=["#378ADD"])
        fig.update_layout(height=280, margin=dict(t=10,b=10), xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

        # Demographics breakdown
        st.markdown("---")
        st.markdown("##### Demographics breakdown")
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            if "gender" in trend_df.columns:
                g = trend_df["gender"].value_counts().reset_index()
                g.columns = ["Gender","Count"]
                fig = px.pie(g, values="Count", names="Gender", hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(height=250, margin=dict(t=10,b=10), showlegend=True)
                st.markdown("Gender")
                st.plotly_chart(fig, use_container_width=True)
        with dc2:
            if "race" in trend_df.columns:
                r = trend_df["race"].value_counts().reset_index()
                r.columns = ["Race","Count"]
                fig = px.pie(r, values="Count", names="Race", hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(height=250, margin=dict(t=10,b=10), showlegend=True)
                st.markdown("Race")
                st.plotly_chart(fig, use_container_width=True)
        with dc3:
            if "age" in trend_df.columns:
                bins = [0,18,40,60,75,120]
                labels = ["0–17","18–39","40–59","60–74","75+"]
                trend_df["age_group"] = pd.cut(trend_df["age"], bins=bins, labels=labels, right=False)
                ag = trend_df["age_group"].value_counts().sort_index().reset_index()
                ag.columns = ["Age group","Count"]
                fig = px.bar(ag, x="Age group", y="Count",
                             color_discrete_sequence=["#1D9E75"])
                fig.update_layout(height=250, margin=dict(t=10,b=10))
                st.markdown("Age group")
                st.plotly_chart(fig, use_container_width=True)
