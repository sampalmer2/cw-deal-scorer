def score_property(p):
    # S1: EBITDAR / Rent Coverage
    e2r = p['ebitdar'] / p['annual_rent']
    s1 = 5 if e2r>=3.5 else 4 if e2r>=2.5 else 3 if e2r>=2.0 else 2 if e2r>=1.5 else 1

    # S2: EBITDAR Margin
    m = p['ebitdar'] / p['sales']
    s2 = 5 if m>=0.25 else 4 if m>=0.22 else 3 if m>=0.18 else 2 if m>=0.14 else 1

    # S3: Store Performance (Rent/Sales + Volume)
    r2s = p['annual_rent'] / p['sales']
    s3 = 5 if (r2s<=0.06 and p['sales']>=4e6) else \
         4 if (r2s<=0.07 and p['sales']>=3e6) else \
         3 if r2s<=0.085 else 2 if r2s<=0.10 else 1

    # S4: Real Estate (Fee Simple + SF + Age + Site Geometry)
    base = 3
    sf  = p.get('sf', 12000)
    age = p.get('age', 20)
    if sf >= 14000:  base += 1
    elif sf < 8000:  base -= 1
    if age <= 10:    base += 1
    elif age >= 30:  base -= 1
    # Broker override for site geometry (-1, 0, +1)
    base += p.get('site_override', 0)
    s4 = max(1, min(5, base))

    # S5: Location / Demographics
    pop = p.get('pop_5m', 50000)
    inc = p.get('income_5m', 90000)
    ps  = 5 if pop>=200000 else 4 if pop>=100000 else \
          3 if pop>=50000  else 2 if pop>=20000  else 1
    ins = 5 if inc>=150000 else 4 if inc>=110000 else \
          3 if inc>=85000  else 2 if inc>=70000  else 1
    # Broker override for trade area quality (-1, 0, +1)
    loc_override = p.get('loc_override', 0)
    s5 = max(1, min(5, round((ps + ins) / 2) + loc_override))

    total = s1 + s2 + s3 + s4 + s5
    grade = 'A' if total >= 20 else 'B' if total >= 13 else 'C'
    pool  = 'Launch Pool' if grade=='A' else \
            'Holdback Pool' if grade=='B' else 'Yield Pool'

    return {
        'S1 — EBITDAR Coverage':  s1,
        'S2 — EBITDAR Margin':    s2,
        'S3 — Store Performance': s3,
        'S4 — Real Estate':       s4,
        'S5 — Location':          s5,
        'Total Score':            total,
        'Grade':                  grade,
        'Pool':                   pool,
        'EBITDAR/Rent':           round(e2r, 2),
        'EBITDAR Margin':         round(m * 100, 1),
        'Rent/Sales':             round(r2s * 100, 1),
    }