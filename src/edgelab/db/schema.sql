-- NFL Edge Lab — DuckDB schema, code v0.1
-- Four schemas: ref (reference), nfl (facts, loaded from snapshots), market (prices), lab (research record).
-- nfl.* fact tables are created by the loader from the snapshot's own columns plus snapshot_id,
-- so upstream schema evolution (e.g. depth charts 2025) does not break loads; required columns
-- are asserted by the data-quality layer instead.

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS nfl;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS lab;

-- ---------------------------------------------------------------- ref
CREATE TABLE IF NOT EXISTS ref.team_aliases (
    alias        VARCHAR PRIMARY KEY,   -- any code seen in any source (OAK, SD, STL, LAR, WSH, JAC, ...)
    team         VARCHAR NOT NULL,      -- canonical nflverse code (LV, LAC, LA, WAS, JAX, ...)
    franchise_id VARCHAR NOT NULL,      -- stable across relocations (raiders, chargers, rams, ...)
    note         VARCHAR
);

CREATE TABLE IF NOT EXISTS ref.books (
    book_id      VARCHAR PRIMARY KEY,
    display_name VARCHAR NOT NULL,
    book_type    VARCHAR NOT NULL,      -- book | exchange | reference | aggregate
    odds_api_key VARCHAR,
    region       VARCHAR,
    valid_from   DATE,
    valid_to     DATE,
    notes        VARCHAR
);

-- ---------------------------------------------------------------- market
-- Every price row carries provenance. line_class: open | close | last_pull | snapshot | unknown
CREATE TABLE IF NOT EXISTS market.historical_lines (
    game_id          VARCHAR NOT NULL,
    source           VARCHAR NOT NULL,   -- nflverse | sbr | nfldata_closing | covers | odds_api_hist
    book_id          VARCHAR NOT NULL,
    line_class       VARCHAR NOT NULL,
    observed_at      TIMESTAMPTZ,        -- when WE observed it (snapshot retrieval) or upstream timestamp if documented
    spread_home      DOUBLE,             -- home team spread (negative = home favored); nflverse convention inverted at load
    spread_home_odds INTEGER,
    spread_away_odds INTEGER,
    total            DOUBLE,
    over_odds        INTEGER,
    under_odds       INTEGER,
    ml_home          INTEGER,
    ml_away          INTEGER,
    snapshot_id      VARCHAR NOT NULL,
    notes            VARCHAR
);

CREATE TABLE IF NOT EXISTS market.odds_snapshots (
    snapshot_id        VARCHAR NOT NULL,
    observed_at        TIMESTAMPTZ NOT NULL,
    event_id           VARCHAR NOT NULL,
    commence_time      TIMESTAMPTZ,
    game_id            VARCHAR,          -- resolved to nflverse game_id when possible
    home_team          VARCHAR,          -- canonical code
    away_team          VARCHAR,
    home_name          VARCHAR,
    away_name          VARCHAR,
    book_id            VARCHAR,          -- resolved from ref.books via odds_api_key; null if unknown
    book_key           VARCHAR NOT NULL,
    book_last_update   TIMESTAMPTZ,
    market             VARCHAR NOT NULL, -- h2h | spreads | totals
    market_last_update TIMESTAMPTZ,
    outcome_name       VARCHAR NOT NULL,
    outcome_side       VARCHAR,          -- home | away | over | under
    outcome_point      DOUBLE,
    outcome_price      INTEGER,
    line_class         VARCHAR DEFAULT 'snapshot'
);

CREATE TABLE IF NOT EXISTS market.line_discrepancies (
    game_id     VARCHAR NOT NULL,
    field       VARCHAR NOT NULL,
    source_a    VARCHAR NOT NULL,
    value_a     DOUBLE,
    source_b    VARCHAR NOT NULL,
    value_b     DOUBLE,
    diff        DOUBLE,
    recorded_at TIMESTAMPTZ DEFAULT now(),
    notes       VARCHAR
);

-- ---------------------------------------------------------------- lab (research record)
CREATE TABLE IF NOT EXISTS lab.snapshots (            -- mirror of data/metadata/snapshots.<machine>.jsonl
    snapshot_id   VARCHAR PRIMARY KEY,
    source        VARCHAR, dataset VARCHAR, season INTEGER, url VARCHAR,
    retrieved_at  TIMESTAMPTZ, last_modified VARCHAR, sha256 VARCHAR, bytes BIGINT,
    rows BIGINT, columns INTEGER, ext VARCHAR, path VARCHAR, loader_version VARCHAR,
    duplicate_of  VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.load_runs (
    load_id      VARCHAR PRIMARY KEY,
    table_name   VARCHAR NOT NULL,
    season       INTEGER,
    snapshot_id  VARCHAR NOT NULL,
    rows_loaded  BIGINT,
    loaded_at    TIMESTAMPTZ DEFAULT now(),
    code_version VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.data_quality_runs (
    dq_id       VARCHAR PRIMARY KEY,
    run_at      TIMESTAMPTZ DEFAULT now(),
    scope       VARCHAR,
    n_checks    INTEGER,
    n_pass      INTEGER,
    n_warn      INTEGER,
    n_critical  INTEGER,
    action      VARCHAR,          -- continue | continue_with_warning | stop
    report_path VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.data_quality_findings (
    dq_id    VARCHAR NOT NULL,
    check_id VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,    -- PASS | WARN | CRITICAL
    message  VARCHAR,
    value    VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.model_versions (
    model_id        VARCHAR PRIMARY KEY,  -- m0.1, m0.2, ...
    name            VARCHAR NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    code_version    VARCHAR,
    agents_version  VARCHAR,
    config_hash     VARCHAR,
    config_path     VARCHAR,
    feature_set     VARCHAR,              -- json list of feature_name@version
    training_window VARCHAR,
    seed            INTEGER,
    packages        VARCHAR,              -- json
    status          VARCHAR,              -- candidate | production | retired
    notes           VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.feature_definitions (
    feature_name  VARCHAR NOT NULL,
    version       VARCHAR NOT NULL,
    code_hash     VARCHAR,
    as_of_rule    VARCHAR,
    description   VARCHAR,
    created_at    TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (feature_name, version)
);

CREATE TABLE IF NOT EXISTS lab.research_ideas (
    idea_id           VARCHAR PRIMARY KEY, -- IDEA-001
    title             VARCHAR,
    status            VARCHAR,             -- proposed | testing | accepted | rejected | parked
    hypothesis        VARCHAR,
    mechanism         VARCHAR,
    success_criterion VARCHAR,
    registered_at     TIMESTAMPTZ,
    decided_at        TIMESTAMPTZ,
    decision          VARCHAR,
    card_path         VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.experiments (
    experiment_id VARCHAR PRIMARY KEY,
    idea_id       VARCHAR,
    model_id      VARCHAR,
    started_at    TIMESTAMPTZ DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    attempt_no    INTEGER,          -- counts attempts in the family for multiple-testing control
    family        VARCHAR,
    config_hash   VARCHAR,
    result_json   VARCHAR,
    artifact_path VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.backtest_runs (
    run_id         VARCHAR PRIMARY KEY,
    model_id       VARCHAR NOT NULL,
    started_at     TIMESTAMPTZ DEFAULT now(),
    seasons        VARCHAR,          -- json
    split          VARCHAR,          -- dev | validation | sealed
    commit         VARCHAR,
    snapshot_ids   VARCHAR,          -- json
    feature_set    VARCHAR,
    seed           INTEGER,
    packages       VARCHAR,
    config_hash    VARCHAR,
    artifact_hash  VARCHAR,
    reproduced_by  VARCHAR,          -- backtesting role confirmation
    notes          VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.backtest_predictions (
    run_id            VARCHAR NOT NULL,
    game_id           VARCHAR NOT NULL,
    as_of             TIMESTAMPTZ NOT NULL,
    pred_margin_home  DOUBLE,
    pred_sd           DOUBLE,
    fair_spread_home  DOUBLE,
    p_home_win        DOUBLE,
    market_spread_home DOUBLE,
    market_line_class VARCHAR,
    market_source     VARCHAR,
    p_cover_home      DOUBLE,
    ml_home           INTEGER,
    ml_away           INTEGER,
    p_home_win_market DOUBLE,
    feature_json      VARCHAR,
    PRIMARY KEY (run_id, game_id)
);

-- Official predictions are append-only. The application layer never issues UPDATE/DELETE here;
-- the auditor's prediction checklist verifies no row for (season, week, game_id, model_id) pre-exists.
CREATE TABLE IF NOT EXISTS lab.predictions_official (
    prediction_id     VARCHAR PRIMARY KEY,
    frozen_at         TIMESTAMPTZ NOT NULL,
    cutoff_at         TIMESTAMPTZ NOT NULL,
    season            INTEGER NOT NULL,
    week              INTEGER NOT NULL,
    game_id           VARCHAR NOT NULL,
    model_id          VARCHAR NOT NULL,
    code_version      VARCHAR, agents_version VARCHAR, feature_set VARCHAR, snapshot_ids VARCHAR,
    market_book_id    VARCHAR, market_spread_home DOUBLE, market_spread_odds INTEGER,
    market_ml_home INTEGER, market_ml_away INTEGER, market_observed_at TIMESTAMPTZ,
    fair_spread_home  DOUBLE, pred_margin_home DOUBLE, pred_sd DOUBLE,
    p_home_win DOUBLE, p_cover_home DOUBLE, fair_ml_home INTEGER, fair_ml_away INTEGER,
    edge_ats DOUBLE, ev_ml_home DOUBLE, ev_ml_away DOUBLE,
    confidence        VARCHAR,
    recommendation    VARCHAR,          -- BET | LEAN | PASS | NO_DATA
    side              VARCHAR,          -- e.g. "NE +5.5", "NE ML"
    units             DOUBLE,
    rationale         VARCHAR,
    counterarguments  VARCHAR,
    data_warnings     VARCHAR,
    audit_status      VARCHAR NOT NULL, -- APPROVED | APPROVED_WITH_CONDITIONS | PRELIMINARY
    audit_ref         VARCHAR,
    feature_json      VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.predictions_preliminary AS SELECT * FROM lab.predictions_official WHERE 1=0;

CREATE TABLE IF NOT EXISTS lab.results (
    game_id        VARCHAR PRIMARY KEY,
    home_score INTEGER, away_score INTEGER, margin_home INTEGER, total INTEGER, overtime BOOLEAN,
    close_source VARCHAR, close_book_id VARCHAR, close_spread_home DOUBLE, close_ml_home INTEGER, close_ml_away INTEGER,
    close_observed_at TIMESTAMPTZ,
    scored_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lab.model_ledger (
    ledger_id     VARCHAR PRIMARY KEY,
    prediction_id VARCHAR NOT NULL,
    game_id       VARCHAR NOT NULL,
    bet_type      VARCHAR NOT NULL,   -- ATS | ML
    side          VARCHAR NOT NULL,
    line          DOUBLE,
    price         INTEGER,
    units         DOUBLE NOT NULL,
    book_id       VARCHAR,
    placed_at     TIMESTAMPTZ,        -- = frozen_at for the model ledger
    close_line DOUBLE, close_price INTEGER, clv_points DOUBLE, clv_cents DOUBLE,
    outcome       VARCHAR,            -- win | loss | push | void
    pnl_units     DOUBLE
);

CREATE TABLE IF NOT EXISTS lab.personal_ledger (
    ledger_id     VARCHAR PRIMARY KEY,
    prediction_id VARCHAR,            -- null if the bet had no model recommendation
    game_id       VARCHAR NOT NULL,
    bet_type      VARCHAR NOT NULL,
    side          VARCHAR NOT NULL,
    line          DOUBLE,
    price         INTEGER,
    units         DOUBLE NOT NULL,
    book_id       VARCHAR,
    placed_at     TIMESTAMPTZ NOT NULL,
    close_line DOUBLE, close_price INTEGER, clv_points DOUBLE, clv_cents DOUBLE,
    outcome       VARCHAR,
    pnl_units     DOUBLE,
    notes         VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.overrides (
    override_id            VARCHAR PRIMARY KEY,
    prediction_id          VARCHAR NOT NULL,
    recorded_at            TIMESTAMPTZ DEFAULT now(),
    model_recommendation   VARCHAR,
    human_decision         VARCHAR,
    reason                 VARCHAR,
    final_bet_ledger_id    VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.agent_runs (
    run_id        VARCHAR PRIMARY KEY,
    task_id       VARCHAR NOT NULL,
    agent         VARCHAR NOT NULL,
    agent_version VARCHAR,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    input_hashes  VARCHAR,
    output_paths  VARCHAR,
    audit_status  VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.audit_results (
    audit_id     VARCHAR PRIMARY KEY,
    task_id      VARCHAR NOT NULL,
    audit_type   VARCHAR NOT NULL,   -- data | leakage | backtest | prediction
    verdict      VARCHAR NOT NULL,
    blockers     INTEGER DEFAULT 0,
    majors       INTEGER DEFAULT 0,
    minors       INTEGER DEFAULT 0,
    reaudit      BOOLEAN,
    audited_at   TIMESTAMPTZ DEFAULT now(),
    commit       VARCHAR,
    report_path  VARCHAR
);

CREATE TABLE IF NOT EXISTS lab.events (
    event_id    VARCHAR PRIMARY KEY,
    occurred_at TIMESTAMPTZ DEFAULT now(),
    kind        VARCHAR NOT NULL,    -- version | decision | incident | note
    summary     VARCHAR NOT NULL,
    detail      VARCHAR,
    actor       VARCHAR
);
