-- ─────────────────────────────────────────────────────────────────
-- Run once to create all tables in your BigQuery dataset
-- Replace YOUR_PROJECT and YOUR_DATASET with actual values
-- Location: US  (matches your BQ data location)
-- ─────────────────────────────────────────────────────────────────

-- ── Phase 1 ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS `ltc-ipnihack-prj-11.BANK_DATA.accounts` (
    account_id   STRING    NOT NULL,
    customer_id  STRING    NOT NULL,
    product_type STRING,              -- savings | current | salary | fd | nps
    balance      FLOAT64
)
OPTIONS (description = 'Customer bank accounts and balances');


CREATE TABLE IF NOT EXISTS `ltc-ipnihack-prj-11.BANK_DATA.transactions` (
    account_id  STRING  NOT NULL,
    description STRING,
    amount      FLOAT64,
    type        STRING,               -- credit | debit
    date        STRING                -- YYYY-MM-DD string
)
OPTIONS (description = 'Account-level debit and credit transactions');


-- ── Phase 2 ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS `ltc-ipnihack-prj-11.BANK_DATA.investments` (
    investment_id   STRING  NOT NULL,
    customer_id     STRING  NOT NULL,
    asset_type      STRING,           -- mutual_fund | stocks | etf | gold | bonds | ppf | nps
    asset_name      STRING,
    invested_amount FLOAT64,
    current_value   FLOAT64,
    monthly_sip     FLOAT64,          -- 0 if lump sum only
    risk_level      STRING,           -- low | medium | high
    category        STRING,           -- equity | debt | hybrid | gold
    purchase_date   STRING,           -- YYYY-MM-DD
    status          STRING            -- active | redeemed
)
OPTIONS (description = 'Customer investment portfolio across all asset classes');


CREATE TABLE IF NOT EXISTS `ltc-ipnihack-prj-11.BANK_DATA.loans` (
    loan_id            STRING  NOT NULL,
    customer_id        STRING  NOT NULL,
    loan_type          STRING,         -- home | car | personal | education | gold
    lender_name        STRING,
    principal_amount   FLOAT64,
    outstanding_amount FLOAT64,
    interest_rate      FLOAT64,        -- annual percentage
    emi                FLOAT64,        -- monthly EMI amount
    tenure_months      INT64,
    remaining_months   INT64,
    start_date         STRING,         -- YYYY-MM-DD
    end_date           STRING,         -- YYYY-MM-DD
    status             STRING          -- active | closed | npa
)
OPTIONS (description = 'Customer loan obligations across all loan types');


CREATE TABLE IF NOT EXISTS `ltc-ipnihack-prj-11.BANK_DATA.credit_cards` (
    card_id             STRING  NOT NULL,
    customer_id         STRING  NOT NULL,
    card_name           STRING,
    issuer              STRING,
    credit_limit        FLOAT64,
    current_outstanding FLOAT64,
    minimum_due         FLOAT64,
    payment_due_date    STRING,        -- YYYY-MM-DD
    interest_rate       FLOAT64,       -- monthly percentage, e.g. 3.5
    status              STRING         -- active | blocked | cancelled
)
OPTIONS (description = 'Customer credit cards with utilisation and due details');


CREATE TABLE IF NOT EXISTS `ltc-ipnihack-prj-11.BANK_DATA.fixed_deposits` (
    fd_id            STRING  NOT NULL,
    customer_id      STRING  NOT NULL,
    bank_name        STRING,
    principal_amount FLOAT64,
    interest_rate    FLOAT64,          -- annual percentage
    maturity_amount  FLOAT64,
    start_date       STRING,           -- YYYY-MM-DD
    maturity_date    STRING,           -- YYYY-MM-DD
    tenure_months    INT64,
    status           STRING            -- active | matured | broken
)
OPTIONS (description = 'Customer fixed deposits across banks');


CREATE TABLE IF NOT EXISTS `ltc-ipnihack-prj-11.BANK_DATA.insurance` (
    policy_id    STRING  NOT NULL,
    customer_id  STRING  NOT NULL,
    policy_type  STRING,               -- term_life | health | motor | home | personal_accident
    policy_name  STRING,
    insurer      STRING,
    sum_assured  FLOAT64,
    premium      FLOAT64,
    frequency    STRING,               -- monthly | quarterly | annual
    start_date   STRING,               -- YYYY-MM-DD
    end_date     STRING,               -- YYYY-MM-DD
    nominee      STRING,
    status       STRING                -- active | lapsed | claimed
)
OPTIONS (description = 'Customer insurance policies across all policy types');
