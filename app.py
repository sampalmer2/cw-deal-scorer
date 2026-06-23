import streamlit as st
import pandas as pd
from scorer import score_property
import urllib.parse
import io

st.set_page_config(page_title="YAFC Deal Scorer", layout="wide")

st.markdown("## YAFC Deal Scorer")
st.markdown("*Cushman & Wakefield — Net Lease Underwriting Tool*")
st.divider()

mode = st.radio("Scoring Mode", ["Score a Single Property", "Upload Excel — Score Portfolio"], horizontal=True)

# ─────────────────────────────────────────────
# SINGLE PROPERTY MODE
# ─────────────────────────────────────────────
if mode == "Score a Single Property":

    with st.form("property_form"):
        st.markdown("### Property Details")

        col1, col2 = st.columns(2)
        with col1:
            address     = st.text_input("Address")
            city        = st.text_input("City")
            state       = st.text_input("State")
            annual_rent = st.number_input("Annual Rent ($)",    min_value=0, value=350000,  step=1000)
            ebitdar     = st.number_input("EBITDAR ($)",        min_value=0, value=900000,  step=1000)
        with col2:
            sales       = st.number_input("2025 Sales ($)",     min_value=0, value=4000000, step=10000)
            sf          = st.number_input("Building SF",        min_value=0, value=12000,   step=100)
            age         = st.number_input("Store Age (yrs)",    min_value=0, value=15,      step=1)
            pop_5m      = st.number_input("5-Mile Population",  min_value=0, value=75000,   step=1000)
            income_5m   = st.number_input("5-Mile HH Income ($)", min_value=0, value=95000, step=1000)

        st.markdown("### Broker Judgment")
        st.caption("Override the formula for factors only a site visit or Maps check reveals.")

        col3, col4 = st.columns(2)
        with col3:
            site_override = st.select_slider(
                "Site Geometry (S4)",
                options=[-1, 0, 1],
                value=0,
                format_func=lambda x: {
                    -1: "−1  Mid-block, limited access",
                     0: " 0  Standard",
                     1: "+1  Hard corner, signalized, pad site"
                }[x]
            )
        with col4:
            loc_override = st.select_slider(
                "Trade Area (S5)",
                options=[-1, 0, 1],
                value=0,
                format_func=lambda x: {
                    -1: "−1  Warehouse / very low car ownership",
                     0: " 0  Standard",
                     1: "+1  High AADT, strong co-tenancy, college town"
                }[x]
            )

        notes   = st.text_area("Notes",   placeholder="Hard corner Spokane WA, new build 2022...")
        caveats = st.text_area("Caveats", placeholder="Confirm lease term, check rent reset...")
        submitted = st.form_submit_button("Score This Property", type="primary")

    if submitted:
        result = score_property({
            'annual_rent':   annual_rent,
            'ebitdar':       ebitdar,
            'sales':         sales,
            'sf':            sf,
            'age':           age,
            'pop_5m':        pop_5m,
            'income_5m':     income_5m,
            'site_override': site_override,
            'loc_override':  loc_override,
        })

        st.divider()
        st.markdown(f"### {address}, {city} {state}")

        grade_color = {"A":"green","B":"orange","C":"red"}[result['Grade']]
        st.markdown(
            f"<h1 style='color:{grade_color};font-size:64px;margin:0'>{result['Grade']}</h1>"
            f"<p style='font-size:20px;margin:0'><b>{result['Pool']}</b></p>"
            f"<p style='color:gray'>Total Score: {result['Total Score']} / 25</p>",
            unsafe_allow_html=True
        )

        st.divider()
        st.markdown("#### Score Breakdown")
        breakdown = {k:v for k,v in result.items() if k.startswith('S')}
        cols = st.columns(5)
        for i,(label,score) in enumerate(breakdown.items()):
            color = "green" if score>=4 else "orange" if score==3 else "red"
            cols[i].markdown(
                f"<div style='text-align:center'>"
                f"<p style='font-size:11px;color:gray;margin-bottom:2px'>{label}</p>"
                f"<p style='font-size:32px;font-weight:bold;color:{color};margin:0'>{score}</p>"
                f"<p style='font-size:10px;color:gray'>/ 5</p></div>",
                unsafe_allow_html=True
            )

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("EBITDAR / Rent", f"{result['EBITDAR/Rent']}×")
        m2.metric("EBITDAR Margin", f"{result['EBITDAR Margin']}%")
        m3.metric("Rent / Sales",   f"{result['Rent/Sales']}%")

        if notes:   st.info(f"**Notes:** {notes}")
        if caveats: st.warning(f"**Caveats:** {caveats}")

        query = urllib.parse.quote(f"{address}, {city}, {state}")
        st.markdown(
            f"[📍 Google Maps](https://www.google.com/maps/search/{query})"
            f"   |   "
            f"[🏢 Street View](https://www.google.com/maps?q={query}&layer=c)"
        )

# ─────────────────────────────────────────────
# PORTFOLIO UPLOAD MODE
# ─────────────────────────────────────────────
else:
    st.markdown("### Upload Portfolio Excel")
    st.caption("Your Excel file needs these column names — spelling must match exactly.")

    # Show required columns
    with st.expander("📋 Required column names — click to expand"):
        st.markdown("""
        | Column Name | Example |
        |---|---|
        | `Address` | 1211 Harrison Ave |
        | `City` | Bellingham |
        | `State` | WA |
        | `Annual Rent` | 349160 |
        | `EBITDAR` | 1531804 |
        | `Sales` | 5807257 |
        | `Building SF` | 13200 |
        | `Store Age` | 8 |
        | `Pop 5Mi` | 123456 |
        | `Income 5Mi` | 95000 |

        Optional columns (if missing, defaults to 0 override):
        - `Site Override` — enter -1, 0, or 1
        - `Loc Override` — enter -1, 0, or 1
        """)

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx","xls","csv"])

    if uploaded_file:
        # Read file
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        st.success(f"Loaded {len(df)} properties. Scoring now...")

        # Score each row
        results = []
        errors  = []

        for idx, row in df.iterrows():
            try:
                prop = {
                    'annual_rent':   float(row.get('Annual Rent', 0)),
                    'ebitdar':       float(row.get('EBITDAR', 0)),
                    'sales':         float(row.get('Sales', 0)),
                    'sf':            float(row.get('Building SF', 12000)),
                    'age':           float(row.get('Store Age', 20)),
                    'pop_5m':        float(row.get('Pop 5Mi', 50000)),
                    'income_5m':     float(row.get('Income 5Mi', 90000)),
                    'site_override': int(row.get('Site Override', 0)),
                    'loc_override':  int(row.get('Loc Override', 0)),
                }
                scored = score_property(prop)
                results.append({
                    'Address':       row.get('Address',''),
                    'City':          row.get('City',''),
                    'State':         row.get('State',''),
                    'Annual Rent':   prop['annual_rent'],
                    'EBITDAR/Rent':  scored['EBITDAR/Rent'],
                    'Rent/Sales':    scored['Rent/Sales'],
                    'EBITDAR Margin':scored['EBITDAR Margin'],
                    'S1':            scored['S1 — EBITDAR Coverage'],
                    'S2':            scored['S2 — EBITDAR Margin'],
                    'S3':            scored['S3 — Store Performance'],
                    'S4':            scored['S4 — Real Estate'],
                    'S5':            scored['S5 — Location'],
                    'Total Score':   scored['Total Score'],
                    'Grade':         scored['Grade'],
                    'Pool':          scored['Pool'],
                })
            except Exception as e:
                errors.append(f"Row {idx+1}: {e}")

        results_df = pd.DataFrame(results)

        # Summary stats
        st.divider()
        st.markdown("### Portfolio Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Properties", len(results_df))
        c2.metric("Grade A — Launch",   len(results_df[results_df['Grade']=='A']))
        c3.metric("Grade B — Holdback", len(results_df[results_df['Grade']=='B']))
        c4.metric("Grade C — Yield",    len(results_df[results_df['Grade']=='C']))

        st.divider()

        # Filter by grade
        grade_filter = st.multiselect(
            "Filter by Grade",
            options=["A","B","C"],
            default=["A","B","C"]
        )
        filtered = results_df[results_df['Grade'].isin(grade_filter)]

        # Color grade column
        def color_grade(val):
            color = {'A':'background-color:#D4EDDA',
                     'B':'background-color:#FFF3CD',
                     'C':'background-color:#F8D7DA'}.get(val,'')
            return color

        st.dataframe(
            filtered.style.applymap(color_grade, subset=['Grade']),
            use_container_width=True,
            height=500
        )

        # Download scored results
        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            results_df.to_excel(writer, index=False, sheet_name='Scored Portfolio')
        output.seek(0)

        st.download_button(
            label="⬇️ Download Scored Results as Excel",
            data=output,
            file_name="YAFC_Scored_Portfolio.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        if errors:
            with st.expander(f"⚠️ {len(errors)} rows had errors"):
                for e in errors:
                    st.write(e)