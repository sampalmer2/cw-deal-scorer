import os
import psycopg2
import psycopg2.extras
import streamlit as st


def get_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scored_properties (
                    id                  SERIAL PRIMARY KEY,
                    scored_at           TIMESTAMPTZ DEFAULT NOW(),
                    address             TEXT,
                    city                TEXT,
                    state               TEXT,
                    annual_rent         NUMERIC,
                    ebitdar             NUMERIC,
                    sales               NUMERIC,
                    sf                  INTEGER,
                    age                 INTEGER,
                    pop_5m              INTEGER,
                    income_5m           INTEGER,
                    aadt                INTEGER,
                    site_override       INTEGER,
                    access_score        INTEGER,
                    loc_override        INTEGER,
                    infill_score        INTEGER,
                    geo_constraint      BOOLEAN,
                    s1                  INTEGER,
                    s2                  INTEGER,
                    s3                  INTEGER,
                    s4a                 INTEGER,
                    s4b                 INTEGER,
                    s5                  INTEGER,
                    s6                  INTEGER,
                    total_score         INTEGER,
                    grade               TEXT,
                    pool                TEXT,
                    ebitdar_rent        NUMERIC,
                    ebitdar_margin      NUMERIC,
                    rent_sales          NUMERIC,
                    aadt_modifier       INTEGER,
                    notes               TEXT,
                    caveats             TEXT
                )
            """)
        conn.commit()


def save_property(inputs: dict, result: dict, notes: str, caveats: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO scored_properties (
                    address, city, state,
                    annual_rent, ebitdar, sales,
                    sf, age, pop_5m, income_5m, aadt,
                    site_override, access_score, loc_override,
                    infill_score, geo_constraint,
                    s1, s2, s3, s4a, s4b, s5, s6,
                    total_score, grade, pool,
                    ebitdar_rent, ebitdar_margin, rent_sales,
                    aadt_modifier, notes, caveats
                ) VALUES (
                    %(address)s, %(city)s, %(state)s,
                    %(annual_rent)s, %(ebitdar)s, %(sales)s,
                    %(sf)s, %(age)s, %(pop_5m)s, %(income_5m)s, %(aadt)s,
                    %(site_override)s, %(access_score)s, %(loc_override)s,
                    %(infill_score)s, %(geo_constraint)s,
                    %(s1)s, %(s2)s, %(s3)s, %(s4a)s, %(s4b)s, %(s5)s, %(s6)s,
                    %(total_score)s, %(grade)s, %(pool)s,
                    %(ebitdar_rent)s, %(ebitdar_margin)s, %(rent_sales)s,
                    %(aadt_modifier)s, %(notes)s, %(caveats)s
                )
            """, {
                'address':       inputs.get('address', ''),
                'city':          inputs.get('city', ''),
                'state':         inputs.get('state', ''),
                'annual_rent':   inputs['annual_rent'],
                'ebitdar':       inputs['ebitdar'],
                'sales':         inputs['sales'],
                'sf':            inputs.get('sf', 12000),
                'age':           inputs.get('age', 20),
                'pop_5m':        inputs.get('pop_5m', 50000),
                'income_5m':     inputs.get('income_5m', 90000),
                'aadt':          inputs.get('aadt', 0),
                'site_override': inputs.get('site_override', 0),
                'access_score':  inputs.get('access_score', 3),
                'loc_override':  inputs.get('loc_override', 0),
                'infill_score':  inputs.get('infill_score', 3),
                'geo_constraint': inputs.get('geo_constraint', False),
                's1':            result['S1 — EBITDAR Coverage'],
                's2':            result['S2 — EBITDAR Margin'],
                's3':            result['S3 — Store Performance'],
                's4a':           result['S4a — Physical Asset'],
                's4b':           result['S4b — Site Access'],
                's5':            result['S5 — Location'],
                's6':            result['S6 — Infill & Supply'],
                'total_score':   result['Total Score'],
                'grade':         result['Grade'],
                'pool':          result['Pool'],
                'ebitdar_rent':  result['EBITDAR/Rent'],
                'ebitdar_margin': result['EBITDAR Margin'],
                'rent_sales':    result['Rent/Sales'],
                'aadt_modifier': result['AADT Modifier'],
                'notes':         notes,
                'caveats':       caveats,
            })
        conn.commit()


def load_all() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM scored_properties
                ORDER BY scored_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def load_summary() -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                                    AS total,
                    COUNT(*) FILTER (WHERE grade = 'A')         AS grade_a,
                    COUNT(*) FILTER (WHERE grade = 'B')         AS grade_b,
                    COUNT(*) FILTER (WHERE grade = 'C')         AS grade_c,
                    ROUND(AVG(total_score)::numeric, 1)         AS avg_score,
                    ROUND(AVG(ebitdar_rent)::numeric, 2)        AS avg_coverage,
                    ROUND(AVG(ebitdar_margin)::numeric, 1)      AS avg_margin,
                    COUNT(*) FILTER (WHERE geo_constraint)      AS geo_constrained,
                    COUNT(*) FILTER (WHERE aadt_modifier = 1)   AS high_traffic,
                    COUNT(*) FILTER (WHERE aadt_modifier = -1)  AS low_traffic
                FROM scored_properties
            """)
            return dict(cur.fetchone())
