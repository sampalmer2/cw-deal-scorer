import psycopg2
import psycopg2.extras
import streamlit as st

# Columns written on every save and read back on every load.
# These must exactly match the scores table schema.
_COLS = [
    'portfolio_name', 'asset_class', 'deal_type', 'client_name',
    'address', 'city', 'state',
    'annual_rent', 'ebitdar', 'sales',
    'aadt', 'pop_5m', 'income_5m', 'sf', 'age',
    'site_override', 'access_score', 'loc_override',
    'infill_score', 'geo_constraint',
    's1', 's2', 's3', 's4a', 's4b', 's5', 's6',
    'total_score', 'formula_grade', 'formula_pool',
    'broker_name', 'broker_grade', 'override_reason',
    'notes', 'caveats', 'formula_version',
]


def get_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id               SERIAL PRIMARY KEY,
                    scored_at        TIMESTAMPTZ DEFAULT NOW(),
                    portfolio_name   TEXT,
                    asset_class      TEXT,
                    deal_type        TEXT,
                    client_name      TEXT,
                    address          TEXT,
                    city             TEXT,
                    state            TEXT,
                    annual_rent      NUMERIC,
                    ebitdar          NUMERIC,
                    sales            NUMERIC,
                    aadt             INTEGER,
                    pop_5m           INTEGER,
                    income_5m        INTEGER,
                    sf               INTEGER,
                    age              INTEGER,
                    site_override    INTEGER,
                    access_score     INTEGER,
                    loc_override     INTEGER,
                    infill_score     INTEGER,
                    geo_constraint   BOOLEAN,
                    s1               INTEGER,
                    s2               INTEGER,
                    s3               INTEGER,
                    s4a              INTEGER,
                    s4b              INTEGER,
                    s5               INTEGER,
                    s6               INTEGER,
                    total_score      INTEGER,
                    formula_grade    TEXT,
                    formula_pool     TEXT,
                    broker_name      TEXT,
                    broker_grade     TEXT,
                    override_reason  TEXT,
                    notes            TEXT,
                    caveats          TEXT,
                    formula_version  TEXT
                )
            """)
        conn.commit()


def save_property(inputs: dict, result: dict, notes: str, caveats: str):
    row = {
        'portfolio_name':  None,
        'asset_class':     None,
        'deal_type':       None,
        'client_name':     None,
        'address':         inputs.get('address', ''),
        'city':            inputs.get('city', ''),
        'state':           inputs.get('state', ''),
        'annual_rent':     inputs['annual_rent'],
        'ebitdar':         inputs['ebitdar'],
        'sales':           inputs['sales'],
        'aadt':            inputs.get('aadt', 0),
        'pop_5m':          inputs.get('pop_5m', 50000),
        'income_5m':       inputs.get('income_5m', 90000),
        'sf':              inputs.get('sf', 12000),
        'age':             inputs.get('age', 20),
        'site_override':   inputs.get('site_override', 0),
        'access_score':    inputs.get('access_score', 3),
        'loc_override':    inputs.get('loc_override', 0),
        'infill_score':    inputs.get('infill_score', 3),
        'geo_constraint':  inputs.get('geo_constraint', False),
        's1':              result['S1 — EBITDAR Coverage'],
        's2':              result['S2 — EBITDAR Margin'],
        's3':              result['S3 — Store Performance'],
        's4a':             result['S4a — Physical Asset'],
        's4b':             result['S4b — Site Access'],
        's5':              result['S5 — Location'],
        's6':              result['S6 — Infill & Supply'],
        'total_score':     result['Total Score'],
        'formula_grade':   result['Grade'],
        'formula_pool':    result['Pool'],
        'broker_name':     None,
        'broker_grade':    None,
        'override_reason': None,
        'notes':           notes,
        'caveats':         caveats,
        'formula_version': '1.0',
    }

    col_list = ', '.join(_COLS)
    placeholders = ', '.join(f'%({c})s' for c in _COLS)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO scores ({col_list}) VALUES ({placeholders})",
                row
            )
        conn.commit()


def load_all() -> list[dict]:
    select_cols = ', '.join(['id', 'scored_at'] + _COLS)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT {select_cols} FROM scores ORDER BY scored_at DESC"
            )
            return [dict(r) for r in cur.fetchall()]


def load_summary() -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                                             AS total,
                    COUNT(*) FILTER (WHERE formula_grade = 'A')         AS grade_a,
                    COUNT(*) FILTER (WHERE formula_grade = 'B')         AS grade_b,
                    COUNT(*) FILTER (WHERE formula_grade = 'C')         AS grade_c,
                    ROUND(AVG(total_score)::numeric, 1)                 AS avg_score,
                    ROUND(AVG(ebitdar / NULLIF(annual_rent, 0))::numeric, 2)  AS avg_coverage,
                    ROUND(AVG(ebitdar / NULLIF(sales, 0) * 100)::numeric, 1)  AS avg_margin,
                    COUNT(*) FILTER (WHERE geo_constraint)              AS geo_constrained,
                    COUNT(*) FILTER (WHERE aadt >= 40000)               AS high_traffic,
                    COUNT(*) FILTER (WHERE aadt > 0 AND aadt < 10000)   AS low_traffic
                FROM scores
            """)
            return dict(cur.fetchone())
