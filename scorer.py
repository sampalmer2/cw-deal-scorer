MODULES = {
    'automotive_service': {
        'name':          'Automotive Service',
        's5_label':      'EBITDAR Margin',
        's6_label':      'Store Performance',
        's7_label':      'Infill & Supply',
        's5_blind_label': 'Brand Strength',
        's6_blind_label': 'Service Bay Count',
        's7_blind_label': 'Infill & Supply',
    },
    'qsr': {
        'name':          'QSR / Fast Casual',
        's5_label':      'AUV vs Brand Average',
        's6_label':      'Drive-Thru',
        's7_label':      'Operator Quality',
        's5_blind_label': 'Brand Tier',
        's6_blind_label': 'Drive-Thru',
        's7_blind_label': 'Guarantee Quality',
    },
    'car_wash': {
        'name':          'Car Wash',
        's5_label':      'Membership Penetration',
        's6_label':      'Wash Format',
        's7_label':      'Daily Volume',
        's5_blind_label': 'Brand Strength',
        's6_blind_label': 'Wash Format',
        's7_blind_label': 'Infill & Supply',
    },
    'medical': {
        'name':          'Medical / Dental',
        's5_label':      'Specialty & Buildout',
        's6_label':      'Payer Mix',
        's7_label':      'TI Investment',
        's5_blind_label': 'Specialty & Buildout',
        's6_blind_label': 'Operator Size',
        's7_blind_label': 'TI Investment',
    },
    'convenience': {
        'name':          'Convenience / Fuel',
        's5_label':      'Fuel Volume',
        's6_label':      'Inside Sales Mix',
        's7_label':      'Fuel Brand',
        's5_blind_label': 'Fuel Brand',
        's6_blind_label': 'Canopy Condition',
        's7_blind_label': 'Infill & Supply',
    },
    'dollar_store': {
        'name':          'Dollar Stores',
        's5_label':      'Sales per SF',
        's6_label':      'Lease Structure',
        's7_label':      'Market Competition',
        's5_blind_label': 'Brand Tier',
        's6_blind_label': 'Lease Structure',
        's7_blind_label': 'Market Competition',
    },
    'fitness': {
        'name':          'Fitness',
        's5_label':      'Membership Count',
        's6_label':      'Format & Equipment',
        's7_label':      'Lease–Equipment Alignment',
        's5_blind_label': 'Brand Strength',
        's6_blind_label': 'Format & Equipment',
        's7_blind_label': 'Lease Term vs Equipment',
    },
}


def score_property(p):

    # ── Financial data extraction ────────────────────────────────────────────
    ebitdar              = float(p.get('ebitdar', 0) or 0)
    annual_rent          = float(p.get('annual_rent', 0) or 0)
    sales                = float(p.get('sales', 0) or 0)
    financials_available = p.get('financials_available', True)

    # ── S1: Financial Signal — auto-detect scoring mode ──────────────────────
    # Priority: Coverage Ratio > Rent/Sales > Financial Blind
    e2r = None
    if ebitdar > 0 and annual_rent > 0:
        e2r = ebitdar / annual_rent
        s1  = 5 if e2r >= 3.5 else 4 if e2r >= 2.5 else 3 if e2r >= 2.0 else 2 if e2r >= 1.5 else 1
        scoring_mode = 'Coverage Ratio'
    elif sales > 0 and annual_rent > 0:
        r2s_s1 = annual_rent / sales
        s1 = 5 if r2s_s1 <= 0.06 else 4 if r2s_s1 <= 0.08 else \
             3 if r2s_s1 <= 0.10 else 2 if r2s_s1 <= 0.12 else 1
        scoring_mode = 'Rent/Sales Ratio'
    else:
        # rent_vs_market: -2 to +2 maps to 1-5
        rent_vs_market = p.get('rent_vs_market', 0)
        s1 = max(1, min(5, 3 + rent_vs_market))
        scoring_mode = 'Financial Blind'

    # financial_blind: True when no financials provided OR mode auto-detected blind
    financial_blind = (not financials_available) or (scoring_mode == 'Financial Blind')

    # ── S2: Lease Quality (broker judgment) ───────────────────────────────────
    # 5 = 15+ yrs, corporate guarantee, >=10% bumps
    # 4 = 10-15 yrs, corporate guarantee, standard bumps
    # 3 = 7-10 yrs or franchisee / subsidiary guarantee
    # 2 = 5-7 yrs or weak guarantee structure
    # 1 = <5 yrs remaining or personal guarantee only
    s2 = p.get('lease_score', 3)

    # ── S3a: Physical Asset Quality ───────────────────────────────────────────
    base = 3
    sf  = p.get('sf', 12000)
    age = p.get('age', 20)
    if sf >= 14000:  base += 1
    elif sf < 8000:  base -= 1
    if age <= 10:    base += 1
    elif age >= 30:  base -= 1
    base += p.get('site_override', 0)
    s3a = max(1, min(5, base))

    # ── S3b: Site Access Quality (broker judgment) ────────────────────────────
    s3b = p.get('access_score', 3)

    # ── S4: Location / Demographics + AADT + Geographic Constraint ───────────
    pop = p.get('pop_5m', 50000)
    inc = p.get('income_5m', 90000)
    ps  = 5 if pop >= 200000 else 4 if pop >= 100000 else \
          3 if pop >= 50000  else 2 if pop >= 20000  else 1
    ins = 5 if inc >= 150000 else 4 if inc >= 110000 else \
          3 if inc >= 85000  else 2 if inc >= 70000  else 1

    aadt = p.get('aadt', 0)
    if aadt >= 40000:               aadt_mod =  1
    elif aadt > 0 and aadt < 10000: aadt_mod = -1
    else:                           aadt_mod =  0

    loc_override   = p.get('loc_override', 0)
    geo_constraint = p.get('geo_constraint', False)

    # Small affluent geographically constrained market: weight income 70/30
    if geo_constraint and pop < 25000 and inc >= 120000:
        s4 = max(1, min(5, round(
            (ps * 0.3) + (ins * 0.7) + loc_override + aadt_mod
        )))
    else:
        s4 = max(1, min(5, round(
            (ps + ins) / 2 + loc_override + aadt_mod
        )))

    # ── Asset Class Module (S5, S6, S7) ─────────────────────────────────────
    asset_class = p.get('asset_class', 'automotive_service')
    module = MODULES.get(asset_class, MODULES['automotive_service'])

    if asset_class == 'automotive_service':
        if not financial_blind and ebitdar > 0 and sales > 0:
            m   = ebitdar / sales
            s5  = 5 if m >= 0.25 else 4 if m >= 0.22 else \
                  3 if m >= 0.18 else 2 if m >= 0.14 else 1
            r2s = annual_rent / sales
            s6  = 5 if (r2s <= 0.06 and sales >= 4e6) else \
                  4 if (r2s <= 0.07 and sales >= 3e6) else \
                  3 if r2s <= 0.085 else 2 if r2s <= 0.10 else 1
        else:
            s5 = p.get('brand_strength', 3)
            s6 = p.get('service_bay_count', 3)
        infill = p.get('infill_score', 3)
        s7 = max(4, infill) if geo_constraint else infill

    elif asset_class == 'qsr':
        if not financial_blind:
            s5 = p.get('auv_vs_brand', 3)
            s6 = p.get('drive_thru_score', 3)
            s7 = p.get('operator_score', 3)
        else:
            s5 = p.get('brand_tier', 3)
            s6 = p.get('drive_thru_score', 3)
            s7 = p.get('guarantee_score', 3)

    elif asset_class == 'car_wash':
        if not financial_blind:
            s5 = p.get('membership_pct', 3)
            s6 = p.get('wash_format', 3)
            s7 = p.get('daily_volume', 3)
        else:
            s5 = p.get('brand_strength', 3)
            s6 = p.get('wash_format', 3)
            infill = p.get('infill_score', 3)
            s7 = max(4, infill) if geo_constraint else infill

    elif asset_class == 'medical':
        if not financial_blind:
            s5 = p.get('medical_specialty', 3)
            s6 = p.get('payer_mix', 3)
            s7 = p.get('ti_investment', 3)
        else:
            s5 = p.get('medical_specialty', 3)
            s6 = p.get('operator_size', 3)
            s7 = p.get('ti_investment', 3)

    elif asset_class == 'convenience':
        if not financial_blind:
            s5 = p.get('fuel_volume', 3)
            s6 = p.get('inside_sales_pct', 3)
            s7 = p.get('fuel_brand', 3)
        else:
            s5 = p.get('fuel_brand', 3)
            s6 = p.get('canopy_condition', 3)
            infill = p.get('infill_score', 3)
            s7 = max(4, infill) if geo_constraint else infill

    elif asset_class == 'dollar_store':
        if not financial_blind:
            s5 = p.get('sales_psf', 3)
            s6 = p.get('lease_structure', 3)
            s7 = p.get('competition_score', 3)
        else:
            s5 = p.get('brand_tier', 3)
            s6 = p.get('lease_structure', 3)
            s7 = p.get('competition_score', 3)

    elif asset_class == 'fitness':
        if not financial_blind:
            s5 = p.get('membership_penetration', 3)
            s6 = p.get('fitness_format', 3)
            s7 = p.get('equip_lease_alignment', 3)
        else:
            s5 = p.get('brand_strength', 3)
            s6 = p.get('fitness_format', 3)
            s7 = p.get('lease_term_vs_equipment', 3)

    else:
        s5 = p.get('s5_score', 3)
        s6 = p.get('s6_score', 3)
        s7 = p.get('s7_score', 3)

    # Module labels depend on mode
    s5_lbl = module['s5_blind_label'] if financial_blind else module['s5_label']
    s6_lbl = module['s6_blind_label'] if financial_blind else module['s6_label']
    s7_lbl = module['s7_blind_label'] if financial_blind else module['s7_label']

    total = s1 + s2 + s3a + s3b + s4 + s5 + s6 + s7
    grade = 'A' if total >= 28 else 'B' if total >= 19 else 'C'
    pool  = 'Launch Pool'   if grade == 'A' else \
            'Holdback Pool' if grade == 'B' else \
            'Yield Pool'

    result = {
        'S1 — Rent Coverage':         s1,
        'S2 — Lease Quality':         s2,
        'S3a — Physical Asset':       s3a,
        'S3b — Site Access':          s3b,
        'S4 — Location':              s4,
        f"S5 — {s5_lbl}":             s5,
        f"S6 — {s6_lbl}":             s6,
        f"S7 — {s7_lbl}":             s7,
        'Total Score':                total,
        'Grade':                      grade,
        'Pool':                       pool,
        'EBITDAR/Rent':               round(e2r, 2) if e2r is not None else None,
        'Geo Constraint Applied':     geo_constraint,
        'AADT Modifier':              aadt_mod,
        'Asset Class':                asset_class,
        'Scoring Mode':               scoring_mode,
    }

    # Automotive financial ratios only when computed from real financials
    if asset_class == 'automotive_service' and not financial_blind and ebitdar > 0 and sales > 0:
        result['EBITDAR Margin'] = round(m * 100, 1)
        result['Rent/Sales']     = round(r2s * 100, 1)

    return result
