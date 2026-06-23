import streamlit as st
import pandas as pd
from scorer import score_property, MODULES
from database import init_db, save_property, load_all, load_summary
import urllib.parse
import io

st.set_page_config(
    page_title="YAFC Deal Scorer",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS — one injection, no inline HTML elsewhere ───────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
.block-container,
[data-testid="stMainBlockContainer"],
[data-testid="stAppViewBlockContainer"] {
    padding-top: 0 !important;
    padding-bottom: 3rem !important;
}
[data-testid="stMetricLabel"] p {
    font-size: 0.62rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.09em !important;
    text-transform: uppercase !important;
    color: #6B7280 !important;
}
[data-testid="stFormSubmitButton"] > button {
    background: #F1B434 !important;
    color: #1D1740 !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 0.5rem 2rem !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    background: #d9a028 !important;
}
[data-testid="stDownloadButton"] > button {
    background: transparent !important;
    border: 1.5px solid #1D1740 !important;
    color: #1D1740 !important;
    font-weight: 500 !important;
    border-radius: 4px !important;
    letter-spacing: 0.02em !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: #1D1740 !important;
    color: #fff !important;
}
button[data-baseweb="tab"] {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
h1, h2, h3 {
    color: #1D1740 !important;
    letter-spacing: -0.02em !important;
}
hr { border-color: #EAECEF !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="padding:2rem 0 1.5rem 0;">'
    '<p style="font-size:2.2rem;font-weight:700;color:#1D1740;'
    'letter-spacing:-0.03em;margin:0;line-height:1.1;">YAFC Intelligence</p>'
    '<p style="font-size:0.85rem;color:#6B7280;margin:0.4rem 0 0 0;'
    'letter-spacing:0.01em;">'
    'Net Lease Deal Scoring &nbsp;&mdash;&nbsp; Cushman &amp; Wakefield Capital Markets'
    '</p>'
    '</div>',
    unsafe_allow_html=True,
)

# Init DB
try:
    init_db()
    db_ok = True
except Exception:
    db_ok = False

tab_score, tab_dash, tab_upload = st.tabs([
    "Score Property", "Dashboard", "Upload Portfolio",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — SCORE PROPERTY
# ─────────────────────────────────────────────────────────────────────────────
with tab_score:

    # Asset class selector sits above the form so changing it re-renders inputs
    asset_class = st.selectbox(
        "Asset Class",
        options=list(MODULES.keys()),
        format_func=lambda x: MODULES[x]['name'],
        key="asset_class_selector",
    )
    module_info = MODULES[asset_class]

    with st.form("property_form"):

        # ── Property Details ─────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**Property Details**")
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
                sales     = st.number_input("Sales ($)",
                                min_value=0, value=4000000, step=10000,
                                help="Unit-level revenue. Required for Automotive; context for other modules.")
                sf        = st.number_input("Building SF",
                                min_value=0, value=12000, step=100)
                age       = st.number_input("Store Age (years)",
                                min_value=0, value=15, step=1)
                pop_5m    = st.number_input("5-Mile Population",
                                min_value=0, value=75000, step=1000)
                income_5m = st.number_input("5-Mile Median Income ($)",
                                min_value=0, value=95000, step=1000)

        # ── Broker Judgment — Universal (S2, S3, S4) ────────────────────────
        with st.container(border=True):
            st.markdown("**Broker Judgment — Universal Criteria**")
            st.caption(
                "Site visit or Maps check required. "
                "These inputs capture what no database can."
            )

            # S2: Lease Quality — full-width row above the three columns
            lc1, lc2 = st.columns([1, 1])
            with lc1:
                st.caption("Lease Quality — S2")
                lease_score = st.select_slider(
                    "Lease Quality",
                    options=[1, 2, 3, 4, 5],
                    value=3,
                    format_func=lambda x: {
                        1: "1 — <5 yrs remaining or personal guarantee only",
                        2: "2 — 5-7 yrs remaining or weak guarantee",
                        3: "3 — 7-10 yrs or franchisee / subsidiary guarantee",
                        4: "4 — 10-15 yrs, corporate guarantee, standard bumps",
                        5: "5 — 15+ yrs, corporate guarantee, >=10% rent bumps",
                    }[x],
                    label_visibility="collapsed",
                )

            st.divider()

            col3, col4, col5 = st.columns(3)

            with col3:
                st.caption("Physical Asset — S3a")
                site_override = st.select_slider(
                    "Site Geometry",
                    options=[-1, 0, 1, 2],
                    value=0,
                    format_func=lambda x: {
                        -1: "-1  Mid-block, poor visibility",
                         0: " 0  Standard standalone pad",
                         1: "+1  Hard corner, signalized",
                         2: "+2  Outparcel, anchor-adjacent",
                    }[x],
                    label_visibility="collapsed",
                )
                st.caption(
                    "+2 Outparcel: freestanding pad in front of an established anchor. "
                    "Captures road and anchor traffic. Tightest cap rates in the market."
                )

                st.caption("Site Access — S3b")
                access_score = st.select_slider(
                    "Access",
                    options=[1, 2, 3, 4, 5],
                    value=3,
                    format_func=lambda x: {
                        1: "1 — Poor: single cut, no signal, stacking blocks street",
                        2: "2 — Limited: right-in/right-out or shared access",
                        3: "3 — Standard: one or two cuts, acceptable flow",
                        4: "4 — Good: signalized or multiple full-movement cuts",
                        5: "5 — Excellent: multiple cuts, dedicated turn lane",
                    }[x],
                    label_visibility="collapsed",
                )
                st.caption(
                    "Check Street View. Look for curb cuts, signal vs. stop sign, "
                    "stacking room, truck turning radius."
                )

            with col4:
                st.caption("Traffic Count — AADT")
                aadt = st.number_input(
                    "AADT",
                    min_value=0, value=0, step=1000,
                    help="Annual Average Daily Traffic on the fronting road. Leave 0 if unknown.",
                    label_visibility="collapsed",
                )
                if aadt >= 40000:
                    st.success(f"{aadt:,} AADT — major arterial (+1 to S4)")
                elif aadt >= 20000:
                    st.info(f"{aadt:,} AADT — standard corridor (no modifier)")
                elif aadt >= 10000:
                    st.info(f"{aadt:,} AADT — secondary road (no modifier)")
                elif aadt > 0:
                    st.warning(f"{aadt:,} AADT — low traffic (-1 to S4)")

                st.caption("Trade Area Override — S4")
                loc_override = st.select_slider(
                    "Trade Area Override",
                    options=[-1, 0, 1],
                    value=0,
                    format_func=lambda x: {
                        -1: "-1  Warehouse / very low car ownership",
                         0: " 0  Standard",
                         1: "+1  Strong co-tenancy / captive corridor",
                    }[x],
                    label_visibility="collapsed",
                )

            with col5:
                geo_constraint = st.checkbox(
                    "Geographic permanence",
                    value=False,
                    help="Check if physical geography permanently prevents competitive development.",
                )
                if geo_constraint:
                    st.success(
                        "Geographic constraint active — "
                        "S4 weighted for affluent small market. "
                        "S7 Infill floor set to 4 (Automotive)."
                    )
                st.caption(
                    "Mountain towns (BLM / National Forest), resort markets, coastal peninsulas. "
                    "Examples: Sun Valley ID, Jackson WY, Aspen CO."
                )

        # ── Asset Class Module — S5, S6, S7 ─────────────────────────────────
        with st.container(border=True):
            st.markdown(f"**{module_info['name']} Module — S5, S6, S7**")

            if asset_class == 'automotive_service':
                st.caption(
                    "S5 (EBITDAR Margin) and S6 (Store Performance / Rent-to-Sales) "
                    "are calculated from the financial inputs above."
                )
                st.caption(f"Infill & Supply Constraint — S7")
                infill_score = st.select_slider(
                    "Infill",
                    options=[1, 2, 3, 4, 5],
                    value=3,
                    format_func=lambda x: {
                        1: "1 — Greenfield, open land, no supply constraint",
                        2: "2 — Growth market, land available nearby",
                        3: "3 — Established corridor, standard",
                        4: "4 — Strong infill, limited land, high barriers",
                        5: "5 — Irreplaceable: classic infill or anchor outparcel",
                    }[x],
                    label_visibility="collapsed",
                )
                st.caption(
                    "Score 5 if the site cannot be replicated — established urban corridor, "
                    "no available land within 1 mile, or outparcel on an anchor developed decades ago."
                )
                # Defaults for unused module vars
                auv_vs_brand = drive_thru_score = operator_score = 3
                membership_pct = wash_format = daily_volume = 3
                medical_specialty = payer_mix = ti_investment = 3
                fuel_volume = inside_sales_pct = fuel_brand = 3
                sales_psf = lease_structure = competition_score = 3
                membership_penetration = fitness_format = equip_lease_alignment = 3

            elif asset_class == 'qsr':
                c5, c6, c7 = st.columns(3)
                with c5:
                    st.caption(f"AUV vs Brand Average — S5")
                    auv_vs_brand = st.select_slider(
                        "AUV",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — <70% of brand AUV — underperforming unit",
                            2: "2 — 70-90% of brand AUV",
                            3: "3 — 90-110% — at brand average",
                            4: "4 — 110-130% of brand AUV",
                            5: "5 — >130% of brand AUV — top performer",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c6:
                    st.caption(f"Drive-Thru — S6")
                    drive_thru_score = st.select_slider(
                        "Drive-Thru",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — No drive-thru, format mismatched to market",
                            2: "2 — Walk-up/counter only in drive-thru market",
                            3: "3 — Drive-thru, limited stacking or shared access",
                            4: "4 — Single DT lane, good stacking",
                            5: "5 — Double DT lane or pickup + DT",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c7:
                    st.caption(f"Operator Quality — S7")
                    operator_score = st.select_slider(
                        "Operator",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — Single-unit franchisee, no track record",
                            2: "2 — Small franchisee (<10 units)",
                            3: "3 — Established franchisee (10-50 units)",
                            4: "4 — Top-tier multi-unit franchisee (50+ units)",
                            5: "5 — Corporate owned",
                        }[x],
                        label_visibility="collapsed",
                    )
                infill_score = 3
                membership_pct = wash_format = daily_volume = 3
                medical_specialty = payer_mix = ti_investment = 3
                fuel_volume = inside_sales_pct = fuel_brand = 3
                sales_psf = lease_structure = competition_score = 3
                membership_penetration = fitness_format = equip_lease_alignment = 3

            elif asset_class == 'car_wash':
                c5, c6, c7 = st.columns(3)
                with c5:
                    st.caption(f"Membership Penetration — S5")
                    membership_pct = st.select_slider(
                        "Membership",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — No membership model, transaction-based only",
                            2: "2 — <20% membership penetration",
                            3: "3 — 20-40% membership",
                            4: "4 — 40-60% membership",
                            5: "5 — >60% EFT membership penetration",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c6:
                    st.caption(f"Wash Format — S6")
                    wash_format = st.select_slider(
                        "Format",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — Self-serve, minimal investment value",
                            2: "2 — Full service — labor dependent, margin risk",
                            3: "3 — In-bay automatic (IBA)",
                            4: "4 — Express conveyor with detailing add-on",
                            5: "5 — Express exterior conveyor, newer build, high throughput",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c7:
                    st.caption(f"Daily Volume — S7")
                    daily_volume = st.select_slider(
                        "Volume",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — <50 cars/day — below breakeven",
                            2: "2 — 50-100 cars/day",
                            3: "3 — 100-200 cars/day",
                            4: "4 — 200-300 cars/day",
                            5: "5 — >300 cars/day average",
                        }[x],
                        label_visibility="collapsed",
                    )
                infill_score = 3
                auv_vs_brand = drive_thru_score = operator_score = 3
                medical_specialty = payer_mix = ti_investment = 3
                fuel_volume = inside_sales_pct = fuel_brand = 3
                sales_psf = lease_structure = competition_score = 3
                membership_penetration = fitness_format = equip_lease_alignment = 3

            elif asset_class == 'medical':
                c5, c6, c7 = st.columns(3)
                with c5:
                    st.caption(f"Specialty & Buildout — S5")
                    medical_specialty = st.select_slider(
                        "Specialty",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — General/urgent care in generic space",
                            2: "2 — Primary care, basic buildout",
                            3: "3 — Specialty clinic (ortho, cardio), standard TI",
                            4: "4 — Surgery center or high-acuity specialty, heavy TI",
                            5: "5 — Cancer center, hospital affiliate — irreplaceable",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c6:
                    st.caption(f"Payer Mix — S6")
                    payer_mix = st.select_slider(
                        "Payer Mix",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — >80% Medicaid — high reimbursement risk",
                            2: "2 — Medicaid-heavy, some commercial",
                            3: "3 — Balanced payer mix",
                            4: "4 — Medicare + commercial dominant",
                            5: "5 — >70% commercial, high-income insured market",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c7:
                    st.caption(f"TI Investment — S7")
                    ti_investment = st.select_slider(
                        "TI",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — <$50/SF — minimal, generic",
                            2: "2 — $50-100/SF",
                            3: "3 — $100-200/SF — meaningful build-to-suit signal",
                            4: "4 — $200-350/SF — strong anchor investment",
                            5: "5 — >$350/SF — hospital-grade, irreplaceable buildout",
                        }[x],
                        label_visibility="collapsed",
                    )
                infill_score = 3
                auv_vs_brand = drive_thru_score = operator_score = 3
                membership_pct = wash_format = daily_volume = 3
                fuel_volume = inside_sales_pct = fuel_brand = 3
                sales_psf = lease_structure = competition_score = 3
                membership_penetration = fitness_format = equip_lease_alignment = 3

            elif asset_class == 'convenience':
                c5, c6, c7 = st.columns(3)
                with c5:
                    st.caption(f"Fuel Volume — S5")
                    fuel_volume = st.select_slider(
                        "Fuel Volume",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — <50,000 gallons/month",
                            2: "2 — 50-100k gallons/month",
                            3: "3 — 100-200k gallons/month",
                            4: "4 — 200-300k gallons/month",
                            5: "5 — >300k gallons/month",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c6:
                    st.caption(f"Inside Sales Mix — S6")
                    inside_sales_pct = st.select_slider(
                        "Inside Sales",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — Fuel only or <$500k inside sales",
                            2: "2 — Basic convenience, <15% inside margin contribution",
                            3: "3 — Standard c-store, food/beverage mix",
                            4: "4 — Strong foodservice program (Subway, branded)",
                            5: "5 — Proprietary food, loyalty program, >30% inside revenue",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c7:
                    st.caption(f"Fuel Brand — S7")
                    fuel_brand = st.select_slider(
                        "Fuel Brand",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — Unbranded independent",
                            2: "2 — Regional independent brand",
                            3: "3 — National brand (Shell, BP, Chevron) — standard",
                            4: "4 — National brand with long-term supply agreement",
                            5: "5 — Premium brand (Wawa, Buc-ee's) or exclusive supply",
                        }[x],
                        label_visibility="collapsed",
                    )
                infill_score = 3
                auv_vs_brand = drive_thru_score = operator_score = 3
                membership_pct = wash_format = daily_volume = 3
                medical_specialty = payer_mix = ti_investment = 3
                sales_psf = lease_structure = competition_score = 3
                membership_penetration = fitness_format = equip_lease_alignment = 3

            elif asset_class == 'dollar_store':
                c5, c6, c7 = st.columns(3)
                with c5:
                    st.caption(f"Sales per SF — S5")
                    sales_psf = st.select_slider(
                        "Sales PSF",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — <$120/SF — below system average",
                            2: "2 — $120-160/SF",
                            3: "3 — $160-210/SF — at system average",
                            4: "4 — $210-260/SF",
                            5: "5 — >$260/SF — high-volume location",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c6:
                    st.caption(f"Lease Structure — S6")
                    lease_structure = st.select_slider(
                        "Lease Structure",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — Gross lease, landlord bears all costs",
                            2: "2 — Modified gross with partial expenses",
                            3: "3 — NNN with minor landlord carve-outs",
                            4: "4 — Absolute NNN, tenant pays all",
                            5: "5 — Absolute NNN + corporate guarantee + rent bumps",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c7:
                    st.caption(f"Market Competition — S7")
                    competition_score = st.select_slider(
                        "Competition",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — 2+ competing dollar stores within 1 mile",
                            2: "2 — 1 direct competitor nearby",
                            3: "3 — Limited local competition",
                            4: "4 — Only dollar store within 3+ miles",
                            5: "5 — Dominant format in underserved market",
                        }[x],
                        label_visibility="collapsed",
                    )
                infill_score = 3
                auv_vs_brand = drive_thru_score = operator_score = 3
                membership_pct = wash_format = daily_volume = 3
                medical_specialty = payer_mix = ti_investment = 3
                fuel_volume = inside_sales_pct = fuel_brand = 3
                membership_penetration = fitness_format = equip_lease_alignment = 3

            elif asset_class == 'fitness':
                c5, c6, c7 = st.columns(3)
                with c5:
                    st.caption(f"Membership Count — S5")
                    membership_penetration = st.select_slider(
                        "Membership Count",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — <500 active members",
                            2: "2 — 500-1,000 members",
                            3: "3 — 1,000-2,500 members",
                            4: "4 — 2,500-4,000 members",
                            5: "5 — >4,000 active members or wait list",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c6:
                    st.caption(f"Format & Equipment — S6")
                    fitness_format = st.select_slider(
                        "Fitness Format",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — Basic gym, commodity equipment, no differentiation",
                            2: "2 — Budget gym in highly competitive market",
                            3: "3 — Midmarket — full cardio, weights, group classes",
                            4: "4 — Premium: CrossFit, boutique, or medical fitness",
                            5: "5 — Unique format with high switching cost",
                        }[x],
                        label_visibility="collapsed",
                    )
                with c7:
                    st.caption(f"Lease-Equipment Alignment — S7")
                    equip_lease_alignment = st.select_slider(
                        "Lease Alignment",
                        options=[1, 2, 3, 4, 5],
                        value=3,
                        format_func=lambda x: {
                            1: "1 — Short lease, expensive equipment being removed",
                            2: "2 — Lease expires before equipment depreciation",
                            3: "3 — Standard term, acceptable alignment",
                            4: "4 — Lease matches equipment life with renewal options",
                            5: "5 — Long-term lease, equipment replacement cost prohibitive",
                        }[x],
                        label_visibility="collapsed",
                    )
                infill_score = 3
                auv_vs_brand = drive_thru_score = operator_score = 3
                membership_pct = wash_format = daily_volume = 3
                medical_specialty = payer_mix = ti_investment = 3
                fuel_volume = inside_sales_pct = fuel_brand = 3
                sales_psf = lease_structure = competition_score = 3

        # ── Notes and caveats ────────────────────────────────────────────────
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            notes = st.text_area(
                "Notes",
                placeholder="Hard corner Spokane WA · outparcel in front of Costco · new build 2022...",
            )
        with col_n2:
            caveats = st.text_area(
                "Caveats",
                placeholder="Confirm lease term · check rent reset · verify anchor tenancy...",
            )

        submitted = st.form_submit_button("Score This Property", type="primary")

    # ── Results ───────────────────────────────────────────────────────────────
    if submitted:
        inputs = {
            'asset_class':    asset_class,
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
            'lease_score':    lease_score,
            'site_override':  site_override,
            'access_score':   access_score,
            'loc_override':   loc_override,
            'aadt':           aadt,
            'geo_constraint': geo_constraint,
            # Module-specific (safe defaults for non-active modules)
            'infill_score':              infill_score,
            'auv_vs_brand':              auv_vs_brand,
            'drive_thru_score':          drive_thru_score,
            'operator_score':            operator_score,
            'membership_pct':            membership_pct,
            'wash_format':               wash_format,
            'daily_volume':              daily_volume,
            'medical_specialty':         medical_specialty,
            'payer_mix':                 payer_mix,
            'ti_investment':             ti_investment,
            'fuel_volume':               fuel_volume,
            'inside_sales_pct':          inside_sales_pct,
            'fuel_brand':                fuel_brand,
            'sales_psf':                 sales_psf,
            'lease_structure':           lease_structure,
            'competition_score':         competition_score,
            'membership_penetration':    membership_penetration,
            'fitness_format':            fitness_format,
            'equip_lease_alignment':     equip_lease_alignment,
        }
        result = score_property(inputs)

        st.divider()
        if address:
            st.markdown(f"### {address}, {city} {state}")

        # Grade, pool, total score
        g1, g2, g3, _ = st.columns([1, 2, 2, 4])
        g1.metric("Grade",       result['Grade'])
        g2.metric("Pool",        result['Pool'])
        g3.metric("Total Score", f"{result['Total Score']} / 40")

        st.divider()

        # Score breakdown
        st.caption("Score Breakdown")
        score_items = [(k, v) for k, v in result.items() if k.startswith('S') and ' — ' in k]
        s_cols = st.columns(len(score_items))
        for i, (label, val) in enumerate(score_items):
            short = label.split(' —')[0].strip()
            desc  = label.split('— ')[1].strip() if '— ' in label else label
            s_cols[i].metric(short, f"{val} / 5", help=desc)

        st.divider()

        # Financial ratios
        st.caption("Financial Ratios")
        if asset_class == 'automotive_service':
            m1, m2, m3 = st.columns(3)
            m1.metric("EBITDAR / Rent", f"{result['EBITDAR/Rent']}x")
            m2.metric("EBITDAR Margin", f"{result['EBITDAR Margin']}%")
            m3.metric("Rent / Sales",   f"{result['Rent/Sales']}%")
        else:
            m1, _ = st.columns([1, 3])
            m1.metric("EBITDAR / Rent", f"{result['EBITDAR/Rent']}x")

        if notes:
            st.info(notes)
        if caveats:
            st.warning(caveats)

        query = urllib.parse.quote(f"{address}, {city}, {state}")
        st.markdown(
            f"[Google Maps](https://www.google.com/maps/search/{query})"
            f"  ·  "
            f"[Street View](https://www.google.com/maps?q={query}&layer=c)"
        )

        # Save to database
        st.divider()
        if db_ok:
            try:
                save_property(inputs, result, notes, caveats)
                st.success("Saved to database.")
            except Exception as e:
                st.warning(f"Score complete — database save failed: {e}")
        else:
            st.info(
                "Database not configured. "
                "Add DATABASE_URL to Streamlit secrets to enable saving."
            )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dash:

    if not db_ok:
        st.info("Add DATABASE_URL to Streamlit secrets to enable the dashboard.")
    else:
        try:
            summary      = load_summary()
            rows         = load_all()
            dash_load_ok = True
        except Exception as e:
            st.error(f"Could not load data: {e}")
            dash_load_ok = False
            rows         = []
            summary      = None

        if dash_load_ok and not rows:
            st.info("No scored properties yet — score a property and save it to see it here.")
        elif dash_load_ok and rows:

            # Summary metrics
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Total Scored",       summary['total'])
            c2.metric("Grade A — Launch",   summary['grade_a'])
            c3.metric("Grade B — Holdback", summary['grade_b'])
            c4.metric("Grade C — Yield",    summary['grade_c'])
            c5.metric("Avg Score",          summary['avg_score'])
            c6.metric("Avg Coverage",       f"{summary['avg_coverage']}x")

            st.divider()

            # Override analysis
            st.caption("Override Analysis")
            ov1, ov2, ov3 = st.columns(3)
            ov1.metric("Geo Constrained",   summary['geo_constrained'],
                       help="Properties with geographic permanence flag active")
            ov2.metric("High Traffic (+1)", summary['high_traffic'],
                       help="AADT >= 40,000 — received +1 to S4")
            ov3.metric("Low Traffic (-1)",  summary['low_traffic'],
                       help="AADT < 10,000 — received -1 to S4")

            st.divider()

            # Property table
            df = pd.DataFrame(rows)
            display_cols = [
                'scored_at', 'asset_class', 'address', 'city', 'state',
                's1', 's2', 's4a', 's4b', 's5', 's3', 's6',
                'total_score', 'formula_grade', 'formula_pool',
                'annual_rent', 'ebitdar', 'sales',
                'geo_constraint', 'aadt',
            ]
            df_display = df[[c for c in display_cols if c in df.columns]].copy()
            df_display['scored_at'] = pd.to_datetime(
                df_display['scored_at']
            ).dt.strftime('%Y-%m-%d %H:%M')

            grade_filter = st.multiselect(
                "Filter by grade",
                options=["A", "B", "C"],
                default=["A", "B", "C"],
                key="dash_grade_filter",
            )
            df_display = df_display[df_display['formula_grade'].isin(grade_filter)]

            st.dataframe(df_display, use_container_width=True, height=460)

            st.divider()
            output = io.BytesIO()
            df_export = (
                pd.DataFrame(rows)
                .astype(str)
                .replace('None', '')
                .replace('nan', '')
            )
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Scored Properties')
            output.seek(0)
            st.download_button(
                "Download Full History",
                data=output,
                file_name="YAFC_Scored_History.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — UPLOAD PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────
with tab_upload:
    st.markdown("### Upload Portfolio")
    st.caption(
        "Upload a spreadsheet with one row per property. "
        "Scores all properties and returns a downloadable graded portfolio."
    )

    with st.expander("Required column names"):
        st.markdown("""
| Column | Example | Notes |
|---|---|---|
| `Address` | 1211 Harrison Ave | |
| `City` | Bellingham | |
| `State` | WA | |
| `Annual Rent` | 349160 | |
| `EBITDAR` | 1531804 | |
| `Sales` | 5807257 | Required for Automotive |
| `Asset Class` | automotive_service | Optional — default automotive_service |
| `Building SF` | 13200 | Optional — default 12,000 |
| `Store Age` | 8 | Optional — default 20 |
| `Pop 5Mi` | 123456 | Optional — default 50,000 |
| `Income 5Mi` | 95000 | Optional — default 90,000 |
| `AADT` | 32000 | Optional — 0 if unknown |
| `Lease Score` | 3 | Optional — 1 to 5 |
| `Site Override` | 0 | Optional — -1, 0, +1, +2 |
| `Access Score` | 3 | Optional — 1 to 5 |
| `Loc Override` | 0 | Optional — -1, 0, +1 |
| `Infill Score` | 3 | Optional — 1 to 5 (Automotive only) |
| `Geo Constraint` | FALSE | Optional |
        """)

    uploaded_file = st.file_uploader(
        "Excel or CSV file",
        type=["xlsx", "xls", "csv"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        try:
            df = (
                pd.read_csv(uploaded_file)
                if uploaded_file.name.endswith('.csv')
                else pd.read_excel(uploaded_file)
            )
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        st.success(f"{len(df)} properties loaded.")

        results = []
        errors  = []

        for idx, row in df.iterrows():
            try:
                prop = {
                    'asset_class':   str(row.get('Asset Class', 'automotive_service')).strip() or 'automotive_service',
                    'annual_rent':   float(row.get('Annual Rent', 0)),
                    'ebitdar':       float(row.get('EBITDAR', 0)),
                    'sales':         float(row.get('Sales', 0)),
                    'sf':            float(row.get('Building SF', 12000)),
                    'age':           float(row.get('Store Age', 20)),
                    'pop_5m':        float(row.get('Pop 5Mi', 50000)),
                    'income_5m':     float(row.get('Income 5Mi', 90000)),
                    'aadt':          float(row.get('AADT', 0)),
                    'lease_score':   int(row.get('Lease Score', 3)),
                    'site_override': int(row.get('Site Override', 0)),
                    'access_score':  int(row.get('Access Score', 3)),
                    'loc_override':  int(row.get('Loc Override', 0)),
                    'infill_score':  int(row.get('Infill Score', 3)),
                    'geo_constraint': bool(row.get('Geo Constraint', False)),
                }
                scored = score_property(prop)

                # Extract S1–S7 generically
                s_scores = {
                    k.split(' — ')[0]: v
                    for k, v in scored.items()
                    if ' — ' in k and k[0] == 'S'
                }

                row_out = {
                    'Address':      row.get('Address', ''),
                    'City':         row.get('City', ''),
                    'State':        row.get('State', ''),
                    'Asset Class':  prop['asset_class'],
                    'Annual Rent':  prop['annual_rent'],
                    'EBITDAR/Rent': scored['EBITDAR/Rent'],
                }
                row_out.update(s_scores)
                row_out['Total Score'] = scored['Total Score']
                row_out['Grade']       = scored['Grade']
                row_out['Pool']        = scored['Pool']

                results.append(row_out)
            except Exception as e:
                errors.append(f"Row {idx + 1}: {e}")

        results_df = pd.DataFrame(results)

        st.divider()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total",   len(results_df))
        c2.metric("Grade A", len(results_df[results_df['Grade'] == 'A']))
        c3.metric("Grade B", len(results_df[results_df['Grade'] == 'B']))
        c4.metric("Grade C", len(results_df[results_df['Grade'] == 'C']))

        st.divider()

        grade_filter = st.multiselect(
            "Filter by grade",
            options=["A", "B", "C"],
            default=["A", "B", "C"],
            key="upload_grade_filter",
        )
        filtered = results_df[results_df['Grade'].isin(grade_filter)]

        st.dataframe(filtered, use_container_width=True, height=460)

        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            results_df.to_excel(writer, index=False, sheet_name='Scored Portfolio')
        output.seek(0)
        st.download_button(
            "Download Scored Portfolio",
            data=output,
            file_name="YAFC_Scored_Portfolio.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if errors:
            with st.expander(f"{len(errors)} rows had errors"):
                for e in errors:
                    st.write(e)
