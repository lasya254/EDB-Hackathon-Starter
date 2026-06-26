# ─── Customer Seed Data ───────────────────────────────────────────────
CUSTOMERS = {
    "c001": {"name": "Alice Johnson", "tier": "premium",  "balance": 5000.00},
    "c002": {"name": "Bob Smith",     "tier": "standard", "balance": 2000.00},
    "c003": {"name": "Carol White",   "tier": "premium",  "balance": 15000.00},
    "c004": {"name": "David Brown",   "tier": "standard", "balance": 800.00},
}

# ─── Bond Product Seed Data ───────────────────────────────────────────
BONDS = {
    "bond_1yr": {
        "name": "Fixed Rate Bond - 1 Year",
        "duration": "1 year",
        "duration_years": 1,
        "base_rate": 2.5,
        "min_investment": 500,
        "max_investment": 50000,
    },
    "bond_2yr": {
        "name": "Fixed Rate Bond - 2 Years",
        "duration": "2 years",
        "duration_years": 2,
        "base_rate": 3.0,
        "min_investment": 500,
        "max_investment": 50000,
    },
    "bond_5yr": {
        "name": "Fixed Rate Bond - 5 Years",
        "duration": "5 years",
        "duration_years": 5,
        "base_rate": 4.0,
        "min_investment": 1000,
        "max_investment": 100000,
    },
    "bond_easy": {
        "name": "Easy Access Savings Bond",
        "duration": "Flexible",
        "duration_years": 1,
        "base_rate": 1.8,
        "min_investment": 100,
        "max_investment": 20000,
    },
}

# ─── Membership Tier Bonus Rates ──────────────────────────────────────
TIER_BONUS = {
    "standard": 0.0,
    "premium":  0.5,
    "vip":      1.0,
}