import streamlit as st
from scorer import score_property
import pandas as pd

st.set_page_config(page_title="CW Deal Scorer", layout="centered")

# Header
st.markdown("## CW Deal Scorer")
st.markdown("*Cushman & Wakefield — Net Lease Underwriting Tool*")
st.divider()

# Input form
with st.form("property_form"):
    st.markdown("### Property Details")

    col1, col2 = st.columns(2)
    with col1:
        address  = st.text_input("Address")
        city     = st.text_input("City")
        state    = st.text_input("State")
        annual_rent = st.number_input("Annual Rent ($)", min_value=0, value=350000, step=1000)
        ebitdar     = st.number_input("EBITDAR ($)",     min_value=0, value=900000, step=1000)
    with col2:
        sales       = st.number_input("2025 Sales ($)",  min_value=0, value=4000000, step=10000)
        sf          = st.number_input("Building SF",     min_value=0, value=12000,   step=100)
        age         = st.number_input("Store Age (yrs)", min_value=0, value=15,      step=1)
        pop_5m      = st.number_input("5-Mile Pop.",     min_value=0, value=75000,   step=1000)
        income_5m   = st.number_input("5-Mile HH Income ($)", min_value=0, value=95000, step=1000)

    st.markdown("### Broker Judgment")
    st.caption("These override the formula for factors only a site visit or Maps check reveals.")

    col3, col4 = st.columns(2)
    with col3:
        site_override = st.select_slider(
            "Site Geometry Override (S4)",
            options=[-1, 0, 1],
            value=0,
            format_func=lambda x: {-1:"−1  Mid-block, limited access", 0:"0  Standard", 1:"+1  Hard corner, signalized, pad site"}[x]
        )
    with col4:
        loc_override = st.select_slider(
            "Trade Area Override (S5)",
            options=[-1, 0, 1],
            value=0,
            format_func=lambda x: {-1:"−1  College town / warehouse / low car ownership", 0:"0  Standard", 1:"+1  High AADT, strong co-tenancy, car-dependent market"}[x]
        )

    notes    = st.text_area("Notes", placeholder="Hard corner Spokane WA, new build 2022...")
    caveats  = st.text_area("Caveats / Flags", placeholder="Confirm lease term, check CO rent reset...")

    submitted = st.form_submit_button("Score This Property", type="primary")

# Results
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

    # Grade display
    grade_color = {"A":"green","B":"orange","C":"red"}[result['Grade']]
    st.markdown(
        f"<h1 style='color:{grade_color};font-size:64px;margin:0'>{result['Grade']}</h1>"
        f"<p style='font-size:20px;margin:0'>{result['Pool']}</p>"
        f"<p style='color:gray'>Total Score: {result['Total Score']} / 25</p>",
        unsafe_allow_html=True
    )

    st.divider()

    # Score breakdown
    st.markdown("#### Score Breakdown")
    breakdown = {k:v for k,v in result.items()
                 if k.startswith('S')}
    cols = st.columns(5)
    for i,(label, score) in enumerate(breakdown.items()):
        color = "green" if score>=4 else "orange" if score==3 else "red"
        cols[i].markdown(
            f"<div style='text-align:center'>"
            f"<p style='font-size:11px;color:gray;margin-bottom:2px'>{label}</p>"
            f"<p style='font-size:32px;font-weight:bold;color:{color};margin:0'>{score}</p>"
            f"<p style='font-size:10px;color:gray'>/ 5</p></div>",
            unsafe_allow_html=True
        )

    # Key metrics
    st.divider()
    st.markdown("#### Key Metrics")
    m1, m2, m3 = st.columns(3)
    m1.metric("EBITDAR / Rent", f"{result['EBITDAR/Rent']}×")
    m2.metric("EBITDAR Margin", f"{result['EBITDAR Margin']}%")
    m3.metric("Rent / Sales",   f"{result['Rent/Sales']}%")

    if notes:
        st.info(f"**Notes:** {notes}")
    if caveats:
        st.warning(f"**Caveats:** {caveats}")

    # Google Maps link
    import urllib.parse
    query = urllib.parse.quote(f"{address}, {city}, {state}")
    st.markdown(
        f"[📍 Open in Google Maps](https://www.google.com/maps/search/{query})"
        f"   |   "
        f"[🏢 Street View](https://www.google.com/maps?q={query}&layer=c)"
    )