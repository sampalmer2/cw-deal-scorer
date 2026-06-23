import psycopg2
import psycopg2.extras
import streamlit as st

# Columns written on every INSERT and read back on every load.
# Order matters — must stay in sync with the row dict in save_property().
_COLS = [
    # ── Identity ─────────────────────────────────────────────────────────────
    'portfolio_name', 'asset_class', 'deal_type', 'client_name',
    'address', 'city', 'state',
    # ── Financials ───────────────────────────────────────────────────────────
    'annual_rent', 'ebitdar', 'sales',
    # ── Site / Demographics ──────────────────────────────────────────────────
    'aadt', 'pop_5m', 'income_5m', 'sf', 'age',
    'site_override', 'access_score', 'loc_override',
    'infill_score', 'geo_constraint',
    # ── Module Scores ────────────────────────────────────────────────────────
    's1', 's2', 's3', 's4a', 's4b', 's5', 's6',
    # ── Formula Output ───────────────────────────────────────────────────────
    'total_score', 'formula_grade', 'formula_pool',
    # ── Broker Override ──────────────────────────────────────────────────────
    'broker_name', 'broker_grade', 'override_reason', 'override_notes',
    # ── Notes ────────────────────────────────────────────────────────────────
    'notes', 'caveats', 'scoring_notes', 'broker_thesis',
    # ── Metadata ─────────────────────────────────────────────────────────────
    'formula_version', 'record_type',
    'scored_by', 'scoring_time_seconds', 'score_iteration',
    # ── Market Context ───────────────────────────────────────────────────────
    'cap_rate_market', 'interest_rate_10yr',
    # ── Deal Tracking ────────────────────────────────────────────────────────
    'deal_status', 'deal_dead_reason',
    'list_price', 'close_price',
    'days_to_loi', 'days_to_close',
    'buyer_type',
    # ── Portfolio ────────────────────────────────────────────────────────────
    'is_portfolio_deal', 'portfolio_id',
]


def get_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── scores table ─────────────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id                   SERIAL PRIMARY KEY,
                    scored_at            TIMESTAMPTZ DEFAULT NOW(),
                    portfolio_name       TEXT,
                    asset_class          TEXT,
                    deal_type            TEXT,
                    client_name          TEXT,
                    address              TEXT,
                    city                 TEXT,
                    state                TEXT,
                    annual_rent          NUMERIC,
                    ebitdar              NUMERIC,
                    sales                NUMERIC,
                    aadt                 INTEGER,
                    pop_5m               INTEGER,
                    income_5m            INTEGER,
                    sf                   INTEGER,
                    age                  INTEGER,
                    site_override        INTEGER,
                    access_score         INTEGER,
                    loc_override         INTEGER,
                    infill_score         INTEGER,
                    geo_constraint       BOOLEAN,
                    s1                   INTEGER,
                    s2                   INTEGER,
                    s3                   INTEGER,
                    s4a                  INTEGER,
                    s4b                  INTEGER,
                    s5                   INTEGER,
                    s6                   INTEGER,
                    total_score          INTEGER,
                    formula_grade        TEXT,
                    formula_pool         TEXT,
                    broker_name          TEXT,
                    broker_grade         TEXT,         -- NULL = broker agreed with formula
                    override_reason      TEXT,
                    override_notes       TEXT,
                    notes                TEXT,
                    caveats              TEXT,
                    scoring_notes        TEXT,
                    formula_version      TEXT,
                    record_type          VARCHAR(20)  DEFAULT 'test',
                    scored_by            TEXT,
                    scoring_time_seconds NUMERIC,
                    score_iteration      INTEGER      DEFAULT 1,
                    cap_rate_market      NUMERIC,
                    interest_rate_10yr   NUMERIC,
                    deal_status          TEXT,
                    deal_dead_reason     TEXT,
                    list_price           NUMERIC,
                    close_price          NUMERIC,
                    days_to_loi          INTEGER,
                    days_to_close        INTEGER,
                    buyer_type           TEXT,
                    is_portfolio_deal    BOOLEAN      DEFAULT FALSE,
                    portfolio_id         TEXT
                )
            """)

            # ── Idempotent migrations for columns added after initial deploy ──
            for stmt in [
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS record_type          VARCHAR(20) DEFAULT 'test'",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS override_notes        TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS scoring_notes         TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS scored_by             TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS scoring_time_seconds  NUMERIC",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS score_iteration       INTEGER DEFAULT 1",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS cap_rate_market       NUMERIC",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS interest_rate_10yr    NUMERIC",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS deal_status           TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS deal_dead_reason      TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS list_price            NUMERIC",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS close_price           NUMERIC",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS days_to_loi           INTEGER",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS days_to_close         INTEGER",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS buyer_type            TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS is_portfolio_deal     BOOLEAN DEFAULT FALSE",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS portfolio_id          TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS broker_thesis         TEXT",
                "ALTER TABLE scores ADD COLUMN IF NOT EXISTS close_cap_rate        NUMERIC",
            ]:
                cur.execute(stmt)

            # ── score_history table ──────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS score_history (
                    id            SERIAL PRIMARY KEY,
                    changed_at    TIMESTAMPTZ DEFAULT NOW(),
                    score_id      INTEGER REFERENCES scores(id) ON DELETE CASCADE,
                    changed_by    TEXT,
                    field_changed TEXT,
                    old_value     TEXT,
                    new_value     TEXT
                )
            """)

        conn.commit()


def _sval(result: dict, key_prefix: str):
    """Return value of the first result key starting with 'key_prefix — '."""
    return next(
        (v for k, v in result.items() if k.startswith(key_prefix + ' —')),
        None,
    )


def save_property(inputs: dict, result: dict, notes: str, caveats: str):
    # Score column mapping (new framework → existing DB columns):
    # s1   = S1 Rent Coverage   (unchanged)
    # s2   = S2 Lease Quality
    # s4a  = S3a Physical Asset
    # s4b  = S3b Site Access
    # s5   = S4 Location
    # s3   = module S5          (repurposed column)
    # s6   = module S6
    # S7 has no DB column — not saved
    row = {
        # Identity
        'portfolio_name':       inputs.get('portfolio_name', None),
        'asset_class':          inputs.get('asset_class', 'automotive_service'),
        'deal_type':            inputs.get('deal_type', None),
        'client_name':          inputs.get('client_name', None),
        'address':              inputs.get('address', ''),
        'city':                 inputs.get('city', ''),
        'state':                inputs.get('state', ''),
        # Financials
        'annual_rent':          inputs['annual_rent'],
        'ebitdar':              inputs['ebitdar'],
        'sales':                inputs['sales'],
        # Site / Demographics
        'aadt':                 inputs.get('aadt', 0),
        'pop_5m':               inputs.get('pop_5m', 50000),
        'income_5m':            inputs.get('income_5m', 90000),
        'sf':                   inputs.get('sf', 12000),
        'age':                  inputs.get('age', 20),
        'site_override':        inputs.get('site_override', 0),
        'access_score':         inputs.get('access_score', 3),
        'loc_override':         inputs.get('loc_override', 0),
        'infill_score':         inputs.get('infill_score', 3),
        'geo_constraint':       inputs.get('geo_constraint', False),
        # Module Scores
        's1':                   _sval(result, 'S1'),
        's2':                   _sval(result, 'S2'),
        's4a':                  _sval(result, 'S3a'),
        's4b':                  _sval(result, 'S3b'),
        's5':                   _sval(result, 'S4'),
        's3':                   _sval(result, 'S5'),
        's6':                   _sval(result, 'S6'),
        # Formula Output
        'total_score':          result['Total Score'],
        'formula_grade':        result['Grade'],
        'formula_pool':         result['Pool'],
        # Broker Override — broker_grade NULL means broker agreed with formula
        'broker_name':          inputs.get('broker_name', None),
        'broker_grade':         inputs.get('broker_grade', None),
        'override_reason':      inputs.get('override_reason', None),
        'override_notes':       inputs.get('override_notes', None),
        # Notes
        'notes':                notes,
        'caveats':              caveats,
        'scoring_notes':        inputs.get('scoring_notes', None),
        'broker_thesis':        inputs.get('broker_thesis', None),
        # Metadata
        'formula_version':      inputs.get('formula_version', 'v1.1'),
        'record_type':          inputs.get('record_type', 'test'),
        'scored_by':            inputs.get('scored_by', None),
        'scoring_time_seconds': inputs.get('scoring_time_seconds', None),
        'score_iteration':      inputs.get('score_iteration', 1),
        # Market Context
        'cap_rate_market':      inputs.get('cap_rate_market', None),
        'interest_rate_10yr':   inputs.get('interest_rate_10yr', None),
        # Deal Tracking
        'deal_status':          inputs.get('deal_status', None),
        'deal_dead_reason':     inputs.get('deal_dead_reason', None),
        'list_price':           inputs.get('list_price', None),
        'close_price':          inputs.get('close_price', None),
        'days_to_loi':          inputs.get('days_to_loi', None),
        'days_to_close':        inputs.get('days_to_close', None),
        'buyer_type':           inputs.get('buyer_type', None),
        # Portfolio
        'is_portfolio_deal':    inputs.get('is_portfolio_deal', False),
        'portfolio_id':         inputs.get('portfolio_id', None),
    }

    col_list     = ', '.join(_COLS)
    placeholders = ', '.join(f'%({c})s' for c in _COLS)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO scores ({col_list}) VALUES ({placeholders})",
                row,
            )
        conn.commit()


def log_score_change(score_id: int, changed_by: str, field_changed: str,
                     old_value, new_value):
    """Insert an audit row into score_history whenever a score record is updated."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO score_history
                    (score_id, changed_by, field_changed, old_value, new_value)
                VALUES
                    (%(score_id)s, %(changed_by)s, %(field_changed)s,
                     %(old_value)s, %(new_value)s)
                """,
                {
                    'score_id':      score_id,
                    'changed_by':    changed_by,
                    'field_changed': field_changed,
                    'old_value':     str(old_value) if old_value is not None else None,
                    'new_value':     str(new_value) if new_value is not None else None,
                },
            )
        conn.commit()


def find_similar_deals(asset_class: str, grade: str = None, state: str = None,
                       rent_min: float = None, rent_max: float = None) -> list[dict]:
    """Return live scored deals matching the given filters, newest first."""
    conditions = ["record_type = 'live'", "asset_class = %(asset_class)s"]
    params: dict = {'asset_class': asset_class}

    if grade and grade != 'All':
        conditions.append("formula_grade = %(grade)s")
        params['grade'] = grade

    if state:
        conditions.append("UPPER(state) = UPPER(%(state)s)")
        params['state'] = state.strip()

    if rent_min is not None and rent_min > 0:
        conditions.append("annual_rent >= %(rent_min)s")
        params['rent_min'] = rent_min

    if rent_max is not None and rent_max > 0:
        conditions.append("annual_rent <= %(rent_max)s")
        params['rent_max'] = rent_max

    where = ' AND '.join(conditions)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    address,
                    city,
                    state,
                    asset_class,
                    formula_grade,
                    broker_grade,
                    annual_rent,
                    close_cap_rate,
                    override_reason,
                    broker_thesis,
                    scored_at
                FROM scores
                WHERE {where}
                ORDER BY scored_at DESC
            """, params)
            return [dict(r) for r in cur.fetchall()]


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


def get_all_scores():
    """Return all rows as (list_of_tuples, col_names) for DataFrame construction."""
    dicts = load_all()
    if not dicts:
        return [], []
    cols = list(dicts[0].keys())
    rows = [list(d.values()) for d in dicts]
    return rows, cols


def save_outcome(score_id: int, outcome: dict):
    """Update close/outcome data on an existing scored row."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE scores SET
                    outcome         = %(outcome)s,
                    close_date      = %(close_date)s,
                    list_price      = %(list_price)s,
                    close_price     = %(close_price)s,
                    list_cap_rate   = %(list_cap_rate)s,
                    close_cap_rate  = %(close_cap_rate)s,
                    days_on_market  = %(days_on_market)s,
                    buyer_type      = %(buyer_type)s,
                    num_offers      = %(num_offers)s,
                    financing       = %(financing)s
                WHERE id = %(id)s
            """, {**outcome, 'id': score_id})
        conn.commit()


def get_outcomes_for_analysis():
    """Return all scored deals that have close data."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id, address, city, state, asset_class,
                    s1, s2, s4a, s4b, s5, s3, s6,
                    total_score, formula_grade, broker_grade,
                    override_reason, close_cap_rate, close_price,
                    days_on_market, buyer_type, num_offers,
                    outcome, close_date
                FROM scores
                WHERE close_cap_rate IS NOT NULL
                ORDER BY close_date DESC
            """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
    return rows, cols


def get_disagreements():
    """Return formula vs broker grade disagreements grouped by state and asset class."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    state,
                    asset_class,
                    formula_grade,
                    broker_grade,
                    COUNT(*)                                     AS count,
                    AVG(total_score)                             AS avg_score,
                    STRING_AGG(DISTINCT override_reason, ' | ') AS reasons
                FROM scores
                WHERE broker_grade IS NOT NULL
                  AND broker_grade != ''
                  AND broker_grade != formula_grade
                GROUP BY state, asset_class, formula_grade, broker_grade
                ORDER BY count DESC
            """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
    return rows, cols


def get_accuracy_metrics() -> dict:
    """Return aggregate scoring accuracy and outcome metrics."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                                                                           AS total_scored,
                    COUNT(broker_grade) FILTER (WHERE broker_grade IS NOT NULL AND broker_grade != '') AS total_broker_scored,
                    COUNT(*) FILTER (WHERE broker_grade = formula_grade)                               AS agreements,
                    COUNT(*) FILTER (WHERE broker_grade != formula_grade
                                      AND broker_grade IS NOT NULL AND broker_grade != '')             AS disagreements,
                    COUNT(*) FILTER (WHERE close_cap_rate IS NOT NULL)                                 AS total_with_outcomes,
                    AVG(close_cap_rate) FILTER (WHERE formula_grade = 'A')                             AS avg_cap_a,
                    AVG(close_cap_rate) FILTER (WHERE formula_grade = 'B')                             AS avg_cap_b,
                    AVG(close_cap_rate) FILTER (WHERE formula_grade = 'C')                             AS avg_cap_c,
                    AVG(days_on_market) FILTER (WHERE formula_grade = 'A')                             AS avg_dom_a,
                    AVG(days_on_market) FILTER (WHERE formula_grade = 'B')                             AS avg_dom_b,
                    AVG(days_on_market) FILTER (WHERE formula_grade = 'C')                             AS avg_dom_c
                FROM scores
            """)
            row  = cur.fetchone()
            cols = [d[0] for d in cur.description]
    return dict(zip(cols, row)) if row else {}
