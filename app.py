import streamlit as st
import pandas as pd
from scorer import score_property
from database import init_db, save_property, load_all, load_summary
import urllib.parse
import io

st.set_page_config(page_title="YAFC Deal Scorer", layout="wide")

st.markdown("## YAFC Deal Scorer")
st.markdown("*Cushman & Wakefield — Net Lease Underwriting Tool*")
st.divider()

# Init DB on every cold start (CREATE TABLE IF NOT EXISTS — safe to call repeatedly)
try:
    init_db()
    db_ok = True
except Exception:
    db_ok = False

tab_score, tab_dash, tab_upload = st.tabs([
    "📋 Score Property",
    "📊 Dashboard",
    "📁 Upload Portfolio",
])

# ─────────────────────────────────────────────
# TAB 1 — SCORE PROPERTY
# ─────────────────────────────────────────────
with tab_score:

    with st.form("property_form"):
        st.markdown("### Property Details")

        col1, col2 = st.columns(2)
        with col1:
            address     = st.text_input("Address")
            city        = st.text_input("City")
            state       = st.text_input("State")
            annual_rent = st.number_input("Annual Rent ($)",
                            min_value=0, value=350000, step=1000)
            ebitdar     = st.number_input("EBITDAR ($)",
                            min_value=0, value=900000, step=1000)
        with col2:
            sales       = st.number_input("2025 Sales ($)",
                            min_value=0, value=4000000, step=10000)
            sf          = st.number_input("Building SF",
                            min_value=0, value=12000, step=100)
            age         = st.number_input("Store Age (yrs)",
                            min_value=0, value=15, step=1)
            pop_5m      = st.number_input("5-Mile Population",
                            min_value=0, value=75000, step=1000)
            income_5m   = st.number_input("5-Mile HH Income ($)",
                            min_value=0, value=95000, step=1000)

        st.markdown("### Broker Judgment")
        st.caption(
            "These three inputs require eyes on the market — "
            "Maps check, site visit, or local knowledge. "
            "They capture what no database can."
        )

        col3, col4, col5 = st.columns(3)

        with col3:
            site_override = st.select_slider(
                "Physical Asset (S4a)",
                options=[-1, 0, 1, 2],
                value=0,
                format_func=lambda x: {
                    -1: "−1  Mid-block, poor visibility",
                     0: " 0  Standard standalone pad",
                     1: "+1  Hard corner, signalized",
                     2: "+2  Outparcel — anchor-adjacent"
                }[x]
            )
            st.caption(
                "**+2 Outparcel:** Freestanding pad in front of "
                "an established anchor. Tightest cap rates. "
                "**−1:** Buried in strip center, limited road visibility."
            )

            access_score = st.select_slider(
                "Site Access Quality (S4b)",
                options=[1, 2, 3, 4, 5],
                value=3,
                format_func=lambda x: {
                    1: "1 — Poor · single cut, no signal, "
                       "blocks street when queued",
                    2: "2 — Limited · right-in/right-out only "
                       "or shared access",
                    3: "3 — Standard · one or two cuts, "
                       "acceptable flow",
                    4: "4 — Good · signalized or multiple "
                       "full-movement cuts",
                    5: "5 — Excellent · multiple cuts, dedicated "
                       "turn lane, easy truck access"
                }[x]
            )
            st.caption(
                "Check on Google Maps Street View. "
                "Look for: number of curb cuts, signal vs. "
                "stop sign, stacking room, truck turning radius. "
                "A tire shop with poor access loses customers "
                "before they park."
            )

        with col4:
            aadt = st.number_input(
                "Traffic Count — AADT",
                min_value=0,
                value=0,
                step=1000,
                help="Annual Average Daily Traffic on the "
                     "fronting road. Leave 0 if unknown."
            )
            if aadt >= 40000:
                st.success(f"✅ {aadt:,} AADT — major arterial (+1 to S5)")
            elif aadt >= 20000:
                st.info(f"ℹ️ {aadt:,} AADT — standard corridor (no modifier)")
            elif aadt >= 10000:
                st.info(f"ℹ️ {aadt:,} AADT — secondary road (no modifier)")
            elif aadt > 0:
                st.warning(f"⚠️ {aadt:,} AADT — low traffic (−1 to S5)")

            loc_override = st.select_slider(
                "Trade Area Override (S5)",
                options=[-1, 0, 1],
                value=0,
                format_func=lambda x: {
                    -1: "−1  Warehouse / very low car ownership",
                     0: " 0  Standard",
                     1: "+1  Strong co-tenancy / captive corridor"
                }[x]
            )

            geo_constraint = st.checkbox(
                "📍 Geographic permanence",
                value=False,
                help="Check if physical geography permanently "
                     "prevents competitive development"
            )
            if geo_constraint:
                st.success(
                    "✅ Geographic constraint active — "
                    "S5 weighted for affluent small market · "
                    "S6 floor set to 4"
                )
            st.caption(
                "**Check for:** Mountain towns surrounded by BLM / "
                "National Forest / wilderness · resort markets · "
                "coastal peninsulas · island markets. "
                "Examples: Sun Valley ID · Jackson WY · "
                "Aspen CO · coastal Oregon towns."
            )

        with col5:
            infill_score = st.select_slider(
                "Infill & Supply Constraint (S6)",
                options=[1, 2, 3, 4, 5],
                value=3,
                format_func=lambda x: {
                    1: "1 — Greenfield, open land, no supply constraint",
                    2: "2 — Growth market, land available nearby",
                    3: "3 — Established corridor, standard",
                    4: "4 — Strong infill, limited land, high barriers",
                    5: "5 — Irreplaceable, classic infill or anchor outparcel"
                }[x]
            )
            st.caption(
                "**Score 5:** Site cannot be replicated. Established "
                "urban or infill corridor — no available land within "
                "1 mile, high zoning and cost barriers, or outparcel "
                "on an anchor that was developed decades ago. "
                "**Score 1:** Competitor could open next door tomorrow."
            )

        st.divider()
        notes   = st.text_area(
            "Notes",
            placeholder="Hard corner Spokane WA · outparcel in front of "
                        "Costco · new build 2022 · established corridor..."
        )
        caveats = st.text_area(
            "Caveats / Flags",
            placeholder="Confirm lease term · check CO rent reset · "
                        "verify anchor tenancy still active..."
        )

        submitted = st.form_submit_button(
            "Score This Property", type="primary"
        )

    if submitted:
        inputs = {
            'address':        address,
            'city':           city,
            'state':          state,
            'annual_rent':    annual_rent,
            'ebitdar':        ebitdar,
            'sales':          sales,
            'sf':             sf,
            'age':            age,
            'pop_5m':         pop_5m,
            'income_5m':      income_5m,
            'site_override':  site_override,
            'access_score':   access_score,
            'loc_override':   loc_override,
            'infill_score':   infill_score,
            'aadt':           aadt,
            'geo_constraint': geo_constraint,
        }
        result = score_property(inputs)

        st.divider()
        st.markdown(f"### {address}, {city} {state}")

        grade_color = {"A": "green", "B": "orange", "C": "red"}[result['Grade']]
        st.markdown(
            f"<h1 style='color:{grade_color};"
            f"font-size:64px;margin:0'>{result['Grade']}</h1>"
            f"<p style='font-size:20px;margin:0'>"
            f"<b>{result['Pool']}</b></p>"
            f"<p style='color:gray'>"
            f"Total Score: {result['Total Score']} / 35</p>",
            unsafe_allow_html=True
        )

        st.divider()
        st.markdown("#### Score Breakdown")
        breakdown = {k: v for k, v in result.items() if k.startswith('S')}
        cols = st.columns(7)
        for i, (label, score) in enumerate(breakdown.items()):
            color = "green" if score >= 4 else "orange" if score == 3 else "red"
            cols[i].markdown(
                f"<div style='text-align:center'>"
                f"<p style='font-size:10px;color:gray;"
                f"margin-bottom:2px'>{label}</p>"
                f"<p style='font-size:28px;font-weight:bold;"
                f"color:{color};margin:0'>{score}</p>"
                f"<p style='font-size:10px;color:gray'>/ 5</p>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("EBITDAR / Rent",  f"{result['EBITDAR/Rent']}×")
        m2.metric("EBITDAR Margin",  f"{result['EBITDAR Margin']}%")
        m3.metric("Rent / Sales",    f"{result['Rent/Sales']}%")

        if notes:
            st.info(f"**Notes:** {notes}")
        if caveats:
            st.warning(f"**Caveats:** {caveats}")

        query = urllib.parse.quote(f"{address}, {city}, {state}")
        st.markdown(
            f"[📍 Google Maps]"
            f"(https://www.google.com/maps/search/{query})"
            f"   |   "
            f"[🏢 Street View]"
            f"(https://www.google.com/maps?q={query}&layer=c)"
        )

        # ── Save to database ──────────────────────────────────────
        st.divider()
        if db_ok:
            try:
                save_property(inputs, result, notes, caveats)
                st.success("✅ Saved to database.")
            except Exception as e:
                st.warning(f"Score complete — database save failed: {e}")
        else:
            st.info("Database not configured — score not saved. "
                    "Add DATABASE_URL to Streamlit secrets to enable.")

# ─────────────────────────────────────────────
# TAB 2 — DASHBOARD
# ─────────────────────────────────────────────
with tab_dash:
    st.markdown("### Scored Properties")

    if not db_ok:
        st.info("Add DATABASE_URL to Streamlit secrets to enable the dashboard.")
        st.stop()

    try:
        summary = load_summary()
        rows    = load_all()
    except Exception as e:
        st.error(f"Could not load data: {e}")
        st.stop()

    if not rows:
        st.info("No properties scored yet. Score a property to populate the dashboard.")
        st.stop()

    # ── Summary metrics ───────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Scored",      summary['total'])
    c2.metric("Grade A — Launch",  summary['grade_a'])
    c3.metric("Grade B — Holdback", summary['grade_b'])
    c4.metric("Grade C — Yield",   summary['grade_c'])
    c5.metric("Avg Score",         summary['avg_score'])
    c6.metric("Avg Coverage",      f"{summary['avg_coverage']}×")

    st.divider()

    # ── Override analysis ─────────────────────────────────────────
    st.markdown("#### Override Analysis")
    ov1, ov2, ov3 = st.columns(3)
    ov1.metric("Geo Constrained",  summary['geo_constrained'],
               help="Properties with geographic permanence flag active")
    ov2.metric("High Traffic (+1)", summary['high_traffic'],
               help="AADT ≥ 40,000 — received +1 to S5")
    ov3.metric("Low Traffic (−1)",  summary['low_traffic'],
               help="AADT < 10,000 — received −1 to S5")

    st.divider()

    # ── Property table ────────────────────────────────────────────
    df = pd.DataFrame(rows)

    display_cols = [
        'scored_at', 'address', 'city', 'state',
        's1', 's2', 's3', 's4a', 's4b', 's5', 's6',
        'total_score', 'formula_grade', 'formula_pool',
        'annual_rent', 'ebitdar', 'sales',
        'geo_constraint', 'aadt',
    ]
    df_display = df[[c for c in display_cols if c in df.columns]].copy()
    df_display['scored_at'] = pd.to_datetime(
        df_display['scored_at']
    ).dt.strftime('%Y-%m-%d %H:%M')

    grade_filter = st.multiselect(
        "Filter by Grade",
        options=["A", "B", "C"],
        default=["A", "B", "C"],
        key="dash_grade_filter"
    )
    df_display = df_display[df_display['formula_grade'].isin(grade_filter)]

    def color_grade(val):
        return {
            'A': 'background-color:#D4EDDA',
            'B': 'background-color:#FFF3CD',
            'C': 'background-color:#F8D7DA'
        }.get(val, '')

    st.dataframe(
        df_display.style.map(color_grade, subset=['formula_grade']),
        use_container_width=True,
        height=500
    )

    # ── Download full history ─────────────────────────────────────
    st.divider()
    output = io.BytesIO()
    df_export = pd.DataFrame(rows).astype(str).replace('None', '').replace('nan', '')
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(
            writer, index=False, sheet_name='Scored Properties'
        )
    output.seek(0)
    st.download_button(
        label="⬇️ Download Full History as Excel",
        data=output,
        file_name="YAFC_Scored_History.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ─────────────────────────────────────────────
# TAB 3 — UPLOAD PORTFOLIO
# ─────────────────────────────────────────────
with tab_upload:
    st.markdown("### Upload Portfolio Excel")
    st.caption(
        "Upload a spreadsheet with one row per property. "
        "Scores all properties automatically and returns "
        "a downloadable graded portfolio."
    )

    with st.expander("📋 Required column names — click to expand"):
        st.markdown("""
| Column Name | Example | Notes |
|---|---|---|
| `Address` | 1211 Harrison Ave | |
| `City` | Bellingham | |
| `State` | WA | |
| `Annual Rent` | 349160 | |
| `EBITDAR` | 1531804 | |
| `Sales` | 5807257 | |
| `Building SF` | 13200 | Optional — defaults to 12,000 |
| `Store Age` | 8 | Optional — defaults to 20 |
| `Pop 5Mi` | 123456 | Optional — defaults to 50,000 |
| `Income 5Mi` | 95000 | Optional — defaults to 90,000 |
| `AADT` | 32000 | Optional — fronting road traffic count, 0 if unknown |
| `Site Override` | 0 | Optional — −1, 0, +1, or +2 for outparcel (S4a) |
| `Access Score` | 3 | Optional — 1 through 5 (S4b site access) |
| `Loc Override` | 0 | Optional — −1, 0, or +1 |
| `Infill Score` | 3 | Optional — 1 through 5 |
| `Geo Constraint` | FALSE | Optional — TRUE if geography permanently prevents competition |
        """)

    uploaded_file = st.file_uploader(
        "Upload your Excel or CSV file",
        type=["xlsx", "xls", "csv"]
    )

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        st.success(f"Loaded {len(df)} properties — scoring now...")

        results = []
        errors  = []

        for idx, row in df.iterrows():
            try:
                prop = {
                    'annual_rent':    float(row.get('Annual Rent', 0)),
                    'ebitdar':        float(row.get('EBITDAR', 0)),
                    'sales':          float(row.get('Sales', 0)),
                    'sf':             float(row.get('Building SF', 12000)),
                    'age':            float(row.get('Store Age', 20)),
                    'pop_5m':         float(row.get('Pop 5Mi', 50000)),
                    'income_5m':      float(row.get('Income 5Mi', 90000)),
                    'aadt':           float(row.get('AADT', 0)),
                    'site_override':  int(row.get('Site Override', 0)),
                    'access_score':   int(row.get('Access Score', 3)),
                    'loc_override':   int(row.get('Loc Override', 0)),
                    'infill_score':   int(row.get('Infill Score', 3)),
                    'geo_constraint': bool(row.get('Geo Constraint', False)),
                }
                scored = score_property(prop)
                results.append({
                    'Address':        row.get('Address', ''),
                    'City':           row.get('City', ''),
                    'State':          row.get('State', ''),
                    'Annual Rent':    prop['annual_rent'],
                    'EBITDAR/Rent':   scored['EBITDAR/Rent'],
                    'Rent/Sales':     scored['Rent/Sales'],
                    'EBITDAR Margin': scored['EBITDAR Margin'],
                    'S1 Coverage':    scored['S1 — EBITDAR Coverage'],
                    'S2 Margin':      scored['S2 — EBITDAR Margin'],
                    'S3 Performance': scored['S3 — Store Performance'],
                    'S4a Physical':   scored['S4a — Physical Asset'],
                    'S4b Access':     scored['S4b — Site Access'],
                    'S5 Location':    scored['S5 — Location'],
                    'S6 Infill':      scored['S6 — Infill & Supply'],
                    'Total Score':    scored['Total Score'],
                    'Grade':          scored['Grade'],
                    'Pool':           scored['Pool'],
                })
            except Exception as e:
                errors.append(f"Row {idx + 1}: {e}")

        results_df = pd.DataFrame(results)

        st.divider()
        st.markdown("### Portfolio Summary")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Properties",   len(results_df))
        c2.metric("Grade A — Launch",
                  len(results_df[results_df['Grade'] == 'A']))
        c3.metric("Grade B — Holdback",
                  len(results_df[results_df['Grade'] == 'B']))
        c4.metric("Grade C — Yield",
                  len(results_df[results_df['Grade'] == 'C']))

        st.divider()

        grade_filter = st.multiselect(
            "Filter by Grade",
            options=["A", "B", "C"],
            default=["A", "B", "C"],
            key="upload_grade_filter"
        )
        filtered = results_df[results_df['Grade'].isin(grade_filter)]

        def color_grade_upload(val):
            return {
                'A': 'background-color:#D4EDDA',
                'B': 'background-color:#FFF3CD',
                'C': 'background-color:#F8D7DA'
            }.get(val, '')

        st.dataframe(
            filtered.style.map(color_grade_upload, subset=['Grade']),
            use_container_width=True,
            height=500
        )

        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            results_df.to_excel(
                writer, index=False, sheet_name='Scored Portfolio'
            )
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
