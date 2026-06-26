"""
Generates realistic dummy data for all 7 tables and writes them to
bq_seed/*.json  AND  optionally loads them directly into BigQuery.

Usage:
    # Generate JSON files only
    python setup/generate_seed_data.py

    # Generate + load into BigQuery
    python setup/generate_seed_data.py --load

Requirements:
    pip install google-cloud-bigquery python-dotenv
"""

import json
import math
import os
import random
import argparse
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────

SEED_DIR    = Path("bq_seed")
TODAY       = date(2026, 6, 25)          # anchored to runtime date
NUM_CUSTOMERS = 20                        # adjust freely

BQ_PROJECT  = os.getenv("GOOGLE_CLOUD_PROJECT")
BQ_DATASET  = os.getenv("BQ_DATASET")
BQ_LOCATION = os.getenv("BQ_LOCATION", "US")

SEED_DIR.mkdir(exist_ok=True)

random.seed(42)                           # reproducible output

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def date_str(d: date) -> str:
    return d.isoformat()


def past_date(min_days: int, max_days: int) -> date:
    return TODAY - timedelta(days=random.randint(min_days, max_days))


def future_date(min_days: int, max_days: int) -> date:
    return TODAY + timedelta(days=random.randint(min_days, max_days))


def uid(prefix: str, n: int) -> str:
    return f"{prefix}{n:04d}"


def emi_formula(principal: float, annual_rate: float, months: int) -> float:
    """Standard reducing-balance EMI."""
    if annual_rate == 0:
        return round(principal / months, 2)
    r = annual_rate / 12 / 100
    return round(principal * r * math.pow(1 + r, months) / (math.pow(1 + r, months) - 1), 2)


# ─────────────────────────────────────────────────────────────────
# Master customer list
# ─────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Sneha", "Vikram", "Ananya",
    "Kiran", "Meera", "Arjun", "Divya", "Rahul", "Pooja",
    "Nikhil", "Shreya", "Amit", "Kavya", "Suresh", "Nisha",
    "Raj", "Deepa",
]
LAST_NAMES = [
    "Sharma", "Patel", "Iyer", "Reddy", "Singh", "Nair",
    "Joshi", "Gupta", "Kumar", "Verma", "Mehta", "Shah",
    "Rao", "Pillai", "Desai", "Malhotra", "Bose", "Chatterjee",
    "Das", "Nambiar",
]

customers = [
    {
        "id":     uid("C", 1001 + i),
        "name":   f"{FIRST_NAMES[i]} {LAST_NAMES[i]}",
        "age":    random.randint(25, 58),
        "income": random.choice([40000, 60000, 80000, 100000, 125000, 150000, 200000]),
        "risk":   random.choice(["conservative", "moderate", "moderate", "aggressive"]),
        "city_tier": random.choice(["tier1", "tier1", "tier2", "tier3"]),
    }
    for i in range(NUM_CUSTOMERS)
]


# ─────────────────────────────────────────────────────────────────
# 1. ACCOUNTS
# ─────────────────────────────────────────────────────────────────

BANKS      = ["HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak Mahindra", "Yes Bank"]
PROD_TYPES = ["savings", "current", "salary"]

def generate_accounts(customers):
    rows = []
    acc_counter = 1
    customer_accounts = {}  # customer_id → [account_id, ...]

    for c in customers:
        cid  = c["id"]
        naccs = random.randint(1, 3)
        customer_accounts[cid] = []

        for j in range(naccs):
            aid = uid("ACC", acc_counter); acc_counter += 1
            rows.append({
                "account_id":   aid,
                "customer_id":  cid,
                "product_type": "salary" if j == 0 else random.choice(PROD_TYPES),
                "balance":      round(random.uniform(5000, 500000), 2),
            })
            customer_accounts[cid].append(aid)

    return rows, customer_accounts


# ─────────────────────────────────────────────────────────────────
# 2. TRANSACTIONS
# ─────────────────────────────────────────────────────────────────

DEBIT_MERCHANTS = [
    ("SWIGGY ORDER",               "food_delivery"),
    ("ZOMATO ORDER",               "food_delivery"),
    ("BIGBASKET PURCHASE",         "groceries"),
    ("DMART RETAIL",               "groceries"),
    ("AMAZON PURCHASE",            "ecommerce"),
    ("FLIPKART ORDER",             "ecommerce"),
    ("UBER RIDE",                  "transport"),
    ("OLA RIDE",                   "transport"),
    ("INDIAN OIL FUEL",            "fuel"),
    ("HP PETROL STATION",          "fuel"),
    ("NETFLIX SUBSCRIPTION",       "entertainment"),
    ("SPOTIFY SUBSCRIPTION",       "entertainment"),
    ("AIRTEL RECHARGE",            "utilities"),
    ("JIO RECHARGE",               "utilities"),
    ("BESCOM ELECTRICITY",         "utilities"),
    ("APOLLO PHARMACY",            "healthcare"),
    ("MEDPLUS PHARMACY",           "healthcare"),
    ("RENT PAYMENT NEFT",          "rent"),
    ("HDFC BANK EMI DEBIT",        "emi"),
    ("ICICI BANK EMI",             "emi"),
    ("SBI LOAN EMI",               "emi"),
    ("MYNTRA FASHION",             "shopping"),
    ("H&M STORE",                  "shopping"),
    ("STARBUCKS",                  "food_dining"),
    ("DOMINOS PIZZA",              "food_dining"),
]

CREDIT_SOURCES = [
    "SALARY CREDIT NEFT",
    "UPI TRANSFER RECEIVED",
    "NEFT CREDIT",
    "INTEREST CREDIT",
    "REFUND CREDIT",
    "CASHBACK CREDIT",
]

DEBIT_RANGES = {
    "food_delivery":  (150,  900),
    "groceries":      (500, 4000),
    "ecommerce":      (300, 8000),
    "transport":      (80,   500),
    "fuel":           (500, 3500),
    "entertainment":  (149,  649),
    "utilities":      (300, 2500),
    "healthcare":     (200, 3000),
    "rent":           (8000, 35000),
    "emi":            (5000, 50000),
    "shopping":       (500, 6000),
    "food_dining":    (200, 1200),
}

def generate_transactions(customer_accounts, customers, months_back=6):
    rows = []
    customer_income = {c["id"]: c["income"] for c in customers}

    for cid, account_ids in customer_accounts.items():
        primary_acc = account_ids[0]
        income = customer_income.get(cid, 60000)

        # Generate daily transactions over the last N months
        start = TODAY - timedelta(days=months_back * 30)
        current = start

        while current <= TODAY:
            # Salary on the 1st of each month
            if current.day == 1:
                rows.append({
                    "account_id":  primary_acc,
                    "description": "SALARY CREDIT NEFT",
                    "amount":      round(income * random.uniform(0.95, 1.05), 2),
                    "type":        "credit",
                    "date":        date_str(current),
                })

            # 2-5 random debits per day
            n_debits = random.randint(0, 4)
            for _ in range(n_debits):
                merchant, category = random.choice(DEBIT_MERCHANTS)
                lo, hi = DEBIT_RANGES.get(category, (100, 1000))
                amount = round(random.uniform(lo, hi), 2)

                rows.append({
                    "account_id":  random.choice(account_ids),
                    "description": merchant,
                    "amount":      amount,
                    "type":        "debit",
                    "date":        date_str(current),
                })

            # Occasional extra credits (transfers, refunds)
            if random.random() < 0.05:
                rows.append({
                    "account_id":  primary_acc,
                    "description": random.choice(CREDIT_SOURCES[1:]),
                    "amount":      round(random.uniform(500, 10000), 2),
                    "type":        "credit",
                    "date":        date_str(current),
                })

            current += timedelta(days=1)

    return rows


# ─────────────────────────────────────────────────────────────────
# 3. INVESTMENTS
# ─────────────────────────────────────────────────────────────────

MUTUAL_FUNDS = [
    ("Parag Parikh Flexicap",       "mutual_fund", "equity",  "medium"),
    ("Mirae Asset Large Cap",       "mutual_fund", "equity",  "medium"),
    ("Axis Midcap Fund",            "mutual_fund", "equity",  "high"),
    ("Kotak Small Cap Fund",        "mutual_fund", "equity",  "high"),
    ("ICICI Pru Balanced Advantage","mutual_fund", "hybrid",  "medium"),
    ("HDFC Corporate Bond",         "mutual_fund", "debt",    "low"),
    ("SBI Liquid Fund",             "mutual_fund", "debt",    "low"),
    ("Nippon India Gold ETF",       "etf",         "gold",    "low"),
    ("Nifty 50 Index Fund",         "etf",         "equity",  "medium"),
    ("HDFC Nifty Next 50",          "etf",         "equity",  "medium"),
]
STOCKS = [
    ("Reliance Industries",  "stocks", "equity", "high"),
    ("Infosys Ltd",          "stocks", "equity", "high"),
    ("HDFC Bank",            "stocks", "equity", "medium"),
    ("TCS",                  "stocks", "equity", "high"),
    ("ITC Ltd",              "stocks", "equity", "medium"),
]
ALTERNATIVES = [
    ("Digital Gold - MMTC",  "gold",   "gold",  "low"),
    ("Sovereign Gold Bond",  "gold",   "gold",  "low"),
    ("PPF Account",          "ppf",    "debt",  "low"),
    ("NPS Tier 1",           "nps",    "debt",  "low"),
]

ALL_INSTRUMENTS = MUTUAL_FUNDS + STOCKS + ALTERNATIVES

def generate_investments(customers):
    rows = []
    inv_counter = 1

    for c in customers:
        cid    = c["id"]
        income = c["income"]
        risk   = c["risk"]

        # Decide number of investments by risk profile
        n = {"conservative": 2, "moderate": 4, "aggressive": 6}.get(risk, 3)
        n = min(n, len(ALL_INSTRUMENTS))

        # Filter instruments by risk profile
        if risk == "conservative":
            pool = [i for i in ALL_INSTRUMENTS if i[3] == "low"]
        elif risk == "aggressive":
            pool = [i for i in ALL_INSTRUMENTS if i[3] in ("medium", "high")]
        else:
            pool = ALL_INSTRUMENTS

        pool = pool or ALL_INSTRUMENTS  # fallback
        chosen = random.sample(pool, min(n, len(pool)))

        for name, asset_type, category, risk_level in chosen:
            invested = round(random.uniform(income * 0.5, income * 8), 2)
            ret      = random.uniform(-0.08, 0.35)   # -8% to +35%
            current  = round(invested * (1 + ret), 2)
            sip      = round(random.choice([0, 1000, 2000, 3000, 5000, 7000, 10000]), 2) \
                       if asset_type in ("mutual_fund", "etf", "gold") else 0.0
            p_date   = past_date(180, 1460)   # 6 months to 4 years ago

            rows.append({
                "investment_id":   uid("INV", inv_counter),
                "customer_id":     cid,
                "asset_type":      asset_type,
                "asset_name":      name,
                "invested_amount": invested,
                "current_value":   current,
                "monthly_sip":     sip,
                "risk_level":      risk_level,
                "category":        category,
                "purchase_date":   date_str(p_date),
                "status":          "active",
            })
            inv_counter += 1

    return rows


# ─────────────────────────────────────────────────────────────────
# 4. LOANS
# ─────────────────────────────────────────────────────────────────

LOAN_CONFIG = {
    # type            principal_range        rate_range  tenure_range(months)
    "home":     ((2000000, 10000000), (8.25, 9.50),  (120, 300)),
    "car":      ((300000,  1500000),  (8.50, 11.00), (36,  84)),
    "personal": ((50000,   800000),   (11.0, 18.00), (12,  60)),
    "education":((500000,  3000000),  (8.00, 10.50), (60, 120)),
}

LENDERS = {
    "home":     ["HDFC Bank", "SBI", "LIC Housing Finance", "PNB Housing"],
    "car":      ["HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Mahindra"],
    "personal": ["ICICI Bank", "HDFC Bank", "Bajaj Finance", "IDFC First"],
    "education":["SBI", "Bank of Baroda", "Axis Bank", "Canara Bank"],
}

def generate_loans(customers):
    rows = []
    loan_counter = 1

    for c in customers:
        cid    = c["id"]
        income = c["income"]

        # 50% chance of a home loan (only if income > 60k)
        loan_types_assigned = []
        if income >= 60000 and random.random() < 0.5:
            loan_types_assigned.append("home")

        # 40% chance of a car loan
        if random.random() < 0.4:
            loan_types_assigned.append("car")

        # 30% chance of a personal loan
        if random.random() < 0.3:
            loan_types_assigned.append("personal")

        for loan_type in loan_types_assigned:
            p_range, r_range, t_range = LOAN_CONFIG[loan_type]
            principal = round(random.uniform(*p_range), -3)   # round to nearest 1000
            rate      = round(random.uniform(*r_range), 2)
            tenure    = random.randint(*t_range)
            emi       = emi_formula(principal, rate, tenure)

            elapsed     = random.randint(6, max(7, tenure - 6))
            remaining   = tenure - elapsed
            outstanding = round(principal * remaining / tenure * random.uniform(0.9, 1.05), 2)

            start = TODAY - timedelta(days=elapsed * 30)
            end   = start  + timedelta(days=tenure * 30)

            rows.append({
                "loan_id":            uid("LN", loan_counter),
                "customer_id":        cid,
                "loan_type":          loan_type,
                "lender_name":        random.choice(LENDERS[loan_type]),
                "principal_amount":   principal,
                "outstanding_amount": outstanding,
                "interest_rate":      rate,
                "emi":                emi,
                "tenure_months":      tenure,
                "remaining_months":   remaining,
                "start_date":         date_str(start),
                "end_date":           date_str(end),
                "status":             "active",
            })
            loan_counter += 1

    return rows


# ─────────────────────────────────────────────────────────────────
# 5. CREDIT CARDS
# ─────────────────────────────────────────────────────────────────

CARD_CATALOG = [
    ("HDFC Regalia",         "HDFC Bank",       300000, 500000),
    ("ICICI Amazon Pay",     "ICICI Bank",       100000, 300000),
    ("SBI SimplyCLICK",      "SBI",              100000, 200000),
    ("Axis ACE",             "Axis Bank",        200000, 400000),
    ("Kotak 811",            "Kotak Mahindra",   50000,  150000),
    ("HDFC MoneyBack",       "HDFC Bank",        50000,  200000),
    ("Yes First Preferred",  "Yes Bank",         200000, 500000),
    ("ICICI Sapphiro",       "ICICI Bank",       300000, 600000),
]

def generate_credit_cards(customers):
    rows = []
    card_counter = 1

    for c in customers:
        cid    = c["id"]
        income = c["income"]

        # 65% of customers have at least one card
        if random.random() > 0.35:
            n_cards = random.randint(1, 2)
            chosen  = random.sample(CARD_CATALOG, min(n_cards, len(CARD_CATALOG)))

            for card_name, issuer, limit_lo, limit_hi in chosen:
                limit       = round(random.uniform(limit_lo, limit_hi), -3)
                outstanding = round(random.uniform(0, limit * 0.65), 2)
                min_due     = round(outstanding * 0.05, 2)
                due_date    = future_date(3, 25)

                rows.append({
                    "card_id":             uid("CC", card_counter),
                    "customer_id":         cid,
                    "card_name":           card_name,
                    "issuer":              issuer,
                    "credit_limit":        limit,
                    "current_outstanding": outstanding,
                    "minimum_due":         min_due,
                    "payment_due_date":    date_str(due_date),
                    "interest_rate":       3.5,      # standard 3.5% monthly
                    "status":              "active",
                })
                card_counter += 1

    return rows


# ─────────────────────────────────────────────────────────────────
# 6. FIXED DEPOSITS
# ─────────────────────────────────────────────────────────────────

FD_BANKS = ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "Post Office", "Kotak Mahindra"]

FD_RATE_BY_TENURE = {
    6:   6.50,
    12:  7.00,
    18:  7.25,
    24:  7.25,
    36:  7.10,
    60:  7.00,
}

def generate_fixed_deposits(customers):
    rows = []
    fd_counter = 1

    for c in customers:
        cid    = c["id"]
        income = c["income"]

        # 55% of customers have at least one FD
        if random.random() < 0.55:
            n_fds = random.randint(1, 3)

            for _ in range(n_fds):
                tenure_months = random.choice(list(FD_RATE_BY_TENURE.keys()))
                rate          = FD_RATE_BY_TENURE[tenure_months]
                principal     = round(random.uniform(income * 1, income * 10), -3)
                start         = past_date(30, tenure_months * 30 - 10)
                maturity      = start + timedelta(days=tenure_months * 30)

                # Simple interest approximation for maturity amount
                maturity_amt  = round(
                    principal * (1 + rate / 100 * tenure_months / 12), 2
                )

                rows.append({
                    "fd_id":             uid("FD", fd_counter),
                    "customer_id":       cid,
                    "bank_name":         random.choice(FD_BANKS),
                    "principal_amount":  principal,
                    "interest_rate":     rate,
                    "maturity_amount":   maturity_amt,
                    "start_date":        date_str(start),
                    "maturity_date":     date_str(maturity),
                    "tenure_months":     tenure_months,
                    "status":            "active",
                })
                fd_counter += 1

    return rows


# ─────────────────────────────────────────────────────────────────
# 7. INSURANCE
# ─────────────────────────────────────────────────────────────────

INSURERS = {
    "term_life": ["HDFC Life", "ICICI Pru Life", "Max Life", "LIC"],
    "health":    ["Star Health", "HDFC Ergo", "Care Health", "Niva Bupa"],
    "motor":     ["ICICI Lombard", "Bajaj Allianz", "HDFC Ergo", "New India"],
    "home":      ["HDFC Ergo", "Bajaj Allianz", "Tata AIG"],
}

POLICY_NAMES = {
    "term_life": ["Click 2 Protect", "iProtect Smart", "Smart Term Plan", "Jeevan Amar"],
    "health":    ["Comprehensive Plan", "Family Floater", "Super Health Plus", "Health Recharge"],
    "motor":     ["Comprehensive Motor", "Private Car Policy", "Two Wheeler Policy"],
    "home":      ["Home Shield", "Property Guard", "My Home Insurance"],
}

NOMINEES = ["Spouse", "Father", "Mother", "Son", "Daughter", "Brother", "Sister"]

def generate_insurance(customers):
    rows = []
    pol_counter = 1

    for c in customers:
        cid    = c["id"]
        income = c["income"]
        age    = c["age"]

        # Term life — 70% of earning customers
        if income >= 40000 and random.random() < 0.70:
            cover    = round(income * 12 * random.randint(8, 15), -5)
            premium  = round(cover * 0.003, 0)                  # ~0.3% of cover
            start    = past_date(365, 1825)
            end      = start + timedelta(days=random.randint(15, 30) * 365)

            rows.append({
                "policy_id":   uid("POL", pol_counter),
                "customer_id": cid,
                "policy_type": "term_life",
                "policy_name": random.choice(POLICY_NAMES["term_life"]),
                "insurer":     random.choice(INSURERS["term_life"]),
                "sum_assured": cover,
                "premium":     premium,
                "frequency":   "annual",
                "start_date":  date_str(start),
                "end_date":    date_str(end),
                "nominee":     random.choice(NOMINEES),
                "status":      "active",
            })
            pol_counter += 1

        # Health — 75% of customers
        if random.random() < 0.75:
            cover    = random.choice([500000, 750000, 1000000, 1500000, 2000000])
            premium  = round(cover * random.uniform(0.012, 0.020), 0)
            start    = past_date(30, 700)
            end      = start + timedelta(days=365)

            rows.append({
                "policy_id":   uid("POL", pol_counter),
                "customer_id": cid,
                "policy_type": "health",
                "policy_name": random.choice(POLICY_NAMES["health"]),
                "insurer":     random.choice(INSURERS["health"]),
                "sum_assured": cover,
                "premium":     premium,
                "frequency":   "annual",
                "start_date":  date_str(start),
                "end_date":    date_str(end),
                "nominee":     "Self",
                "status":      "active",
            })
            pol_counter += 1

        # Motor — 50% chance
        if random.random() < 0.50:
            vehicle_value = round(random.uniform(300000, 1500000), -3)
            premium       = round(vehicle_value * random.uniform(0.02, 0.04), 0)
            start         = past_date(30, 300)
            end           = start + timedelta(days=365)

            rows.append({
                "policy_id":   uid("POL", pol_counter),
                "customer_id": cid,
                "policy_type": "motor",
                "policy_name": random.choice(POLICY_NAMES["motor"]),
                "insurer":     random.choice(INSURERS["motor"]),
                "sum_assured": vehicle_value,
                "premium":     premium,
                "frequency":   "annual",
                "start_date":  date_str(start),
                "end_date":    date_str(end),
                "nominee":     "NA",
                "status":      "active",
            })
            pol_counter += 1

    return rows


# ─────────────────────────────────────────────────────────────────
# Write to JSON files
# ─────────────────────────────────────────────────────────────────

def save(name: str, rows: list):
    path = SEED_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"  ✅  {path}  ({len(rows):,} rows)")


# ─────────────────────────────────────────────────────────────────
# Load into BigQuery
# ─────────────────────────────────────────────────────────────────

def load_to_bq(table_name: str, rows: list):
    from google.cloud import bigquery

    client = bigquery.Client(project=BQ_PROJECT, location=BQ_LOCATION)
    table_ref = f"{BQ_PROJECT}.{BQ_DATASET}.{table_name}"

    errors = client.insert_rows_json(table_ref, rows)
    if errors:
        print(f"  ❌  {table_name}: {errors[:2]}")
    else:
        print(f"  ✅  Loaded {len(rows):,} rows → {table_ref}")


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def main(load: bool = False):
    print(f"\n{'─'*55}")
    print(f"  Generating seed data for {NUM_CUSTOMERS} customers")
    print(f"  Reference date: {TODAY}")
    print(f"{'─'*55}\n")

    # ── Generate ────────────────────────────────────────────────
    print("Generating accounts...")
    accounts, customer_accounts = generate_accounts(customers)
    save("accounts", accounts)

    print("Generating transactions (may take a moment)...")
    transactions = generate_transactions(customer_accounts, customers, months_back=6)
    save("transactions", transactions)

    print("Generating investments...")
    investments = generate_investments(customers)
    save("investments", investments)

    print("Generating loans...")
    loans = generate_loans(customers)
    save("loans", loans)

    print("Generating credit cards...")
    credit_cards = generate_credit_cards(customers)
    save("credit_cards", credit_cards)

    print("Generating fixed deposits...")
    fixed_deposits = generate_fixed_deposits(customers)
    save("fixed_deposits", fixed_deposits)

    print("Generating insurance policies...")
    insurance = generate_insurance(customers)
    save("insurance", insurance)

    # ── Summary ─────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print("  SUMMARY")
    print(f"{'─'*55}")
    print(f"  Customers     : {NUM_CUSTOMERS}")
    print(f"  Accounts      : {len(accounts)}")
    print(f"  Transactions  : {len(transactions)}")
    print(f"  Investments   : {len(investments)}")
    print(f"  Loans         : {len(loans)}")
    print(f"  Credit Cards  : {len(credit_cards)}")
    print(f"  Fixed Deposits: {len(fixed_deposits)}")
    print(f"  Insurance     : {len(insurance)}")
    print(f"{'─'*55}\n")

    # ── Optionally load into BigQuery ────────────────────────────
    if load:
        if not BQ_PROJECT or not BQ_DATASET:
            print("❌  BQ_PROJECT or BQ_DATASET not set in .env — skipping BigQuery load.")
            return

        print(f"Loading into BigQuery: {BQ_PROJECT}.{BQ_DATASET}\n")
        load_to_bq("accounts",       accounts)
        load_to_bq("transactions",   transactions)
        load_to_bq("investments",    investments)
        load_to_bq("loans",          loans)
        load_to_bq("credit_cards",   credit_cards)
        load_to_bq("fixed_deposits", fixed_deposits)
        load_to_bq("insurance",      insurance)
        print("\n✅  All tables loaded.\n")
    else:
        print("JSON files written to bq_seed/")
        print("To load into BigQuery, run:")
        print("  python setup/generate_seed_data.py --load\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--load",
        action="store_true",
        help="Load generated data directly into BigQuery after generation",
    )
    args = parser.parse_args()
    main(load=args.load)
