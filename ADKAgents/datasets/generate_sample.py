# generate_sample_data.py

from google.cloud import bigquery
from faker import Faker
import random
from datetime import datetime, timedelta
import uuid

fake = Faker('en_IN')
client = bigquery.Client()

PROJECT = "lbg-pec-hack"
DATASET = "lbg_pec_hack"

def generate_customers(num_customers: int = 100):
    """Generate sample customer data."""
    customers = []
    profiles = []
    
    for i in range(num_customers):
        customer_id = f"C{1001 + i}"
        
        # Customer basic info
        customers.append({
            "customer_id": customer_id,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "date_of_birth": fake.date_of_birth(minimum_age=25, maximum_age=60).isoformat(),
            "address": fake.address(),
            "city": random.choice(["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune", "Kolkata"]),
            "state": random.choice(["Maharashtra", "Karnataka", "Tamil Nadu", "Telangana", "Delhi", "West Bengal"]),
            "country": "India",
            "created_at": datetime.now().isoformat()
        })
        
        # Customer profile
        age = datetime.now().year - int(customers[-1]["date_of_birth"][:4])
        income_base = random.choice([50000, 75000, 100000, 150000, 200000, 300000])
        
        profiles.append({
            "profile_id": f"P{1001 + i}",
            "customer_id": customer_id,
            "monthly_income": income_base + random.randint(-10000, 20000),
            "employment_type": random.choices(
                ["salaried", "self_employed", "business"],
                weights=[70, 20, 10]
            )[0],
            "occupation": random.choice([
                "Software Engineer", "Doctor", "Teacher", "Business Analyst",
                "Manager", "Consultant", "Accountant", "Designer"
            ]),
            "employer_name": fake.company(),
            "marital_status": random.choice(["single", "married"]),
            "dependents": random.randint(0, 3),
            "risk_appetite": random.choice(["conservative", "moderate", "aggressive"]),
            "investment_experience": random.choice(["beginner", "intermediate", "expert"]),
            "preferred_language": "en",
            "financial_literacy": random.choice(["basic", "intermediate", "advanced"]),
            "created_at": datetime.now().isoformat()
        })
    
    # Insert into BigQuery
    client.insert_rows_json(f"{PROJECT}.{DATASET}.customers", customers)
    client.insert_rows_json(f"{PROJECT}.{DATASET}.customer_profile", profiles)
    
    return customers, profiles

def generate_accounts(customers: list):
    """Generate account data for customers."""
    accounts = []
    
    for customer in customers:
        customer_id = customer["customer_id"]
        
        # Primary savings account
        accounts.append({
            "account_id": f"ACC{uuid.uuid4().hex[:8].upper()}",
            "customer_id": customer_id,
            "account_type": "savings",
            "account_number": fake.bban(),
            "bank_name": random.choice(["HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak"]),
            "branch": fake.city(),
            "balance": random.uniform(50000, 500000),
            "currency": "INR",
            "is_primary": True,
            "opened_date": fake.date_between(start_date="-5y", end_date="-1y").isoformat(),
            "status": "active",
            "created_at": datetime.now().isoformat()
        })
        
        # Additional accounts for some customers
        if random.random() > 0.5:
            accounts.append({
                "account_id": f"ACC{uuid.uuid4().hex[:8].upper()}",
                "customer_id": customer_id,
                "account_type": random.choice(["savings", "current"]),
                "account_number": fake.bban(),
                "bank_name": random.choice(["HDFC Bank", "ICICI Bank", "SBI", "Axis Bank"]),
                "branch": fake.city(),
                "balance": random.uniform(10000, 200000),
                "currency": "INR",
                "is_primary": False,
                "opened_date": fake.date_between(start_date="-3y", end_date="-6m").isoformat(),
                "status": "active",
                "created_at": datetime.now().isoformat()
            })
    
    client.insert_rows_json(f"{PROJECT}.{DATASET}.accounts", accounts)
    return accounts

def generate_transactions(accounts: list, months: int = 6):
    """Generate realistic transaction data."""
    transactions = []
    
    # Transaction templates
    expense_templates = [
        ("SWIGGY", "Food & Dining", 200, 800),
        ("ZOMATO", "Food & Dining", 300, 1000),
        ("AMAZON", "Shopping", 500, 15000),
        ("FLIPKART", "Shopping", 500, 10000),
        ("UBER", "Transportation", 150, 500),
        ("OLA", "Transportation", 100, 400),
        ("NETFLIX", "Entertainment", 199, 649),
        ("SPOTIFY", "Entertainment", 119, 119),
        ("BIGBASKET", "Groceries", 1000, 5000),
        ("DMART", "Groceries", 500, 3000),
        ("INDIAN OIL", "Fuel", 1000, 4000),
        ("ELECTRICITY", "Utilities", 1500, 4000),
        ("MOBILE RECHARGE", "Utilities", 299, 999),
    ]
    
    for account in accounts:
        account_id = account["account_id"]
        customer_id = account["customer_id"]
        
        start_date = datetime.now() - timedelta(days=months * 30)
        current_date = start_date
        balance = account["balance"]
        
        while current_date < datetime.now():
            # Generate 2-5 transactions per day
            num_transactions = random.randint(2, 5)
            
            for _ in range(num_transactions):
                # 80% debits, 20% credits
                is_credit = random.random() > 0.8
                
                if is_credit:
                    # Income transactions (salary, transfers)
                    if current_date.day == 1:  # Salary on 1st
                        amount = random.uniform(50000, 200000)
                        description = "SALARY CREDIT"
                    else:
                        amount = random.uniform(1000, 10000)
                        description = random.choice(["UPI CREDIT", "NEFT CREDIT", "REFUND"])
                    
                    balance += amount
                    tx_type = "credit"
                else:
                    # Expense transactions
                    template = random.choice(expense_templates)
                    description = template[0]
                    amount = random.uniform(template[2], template[3])
                    balance -= amount
                    tx_type = "debit"
                
                transactions.append({
                    "transaction_id": f"TXN{uuid.uuid4().hex[:12].upper()}",
                    "account_id": account_id,
                    "customer_id": customer_id,
                    "transaction_date": current_date.isoformat(),
                    "transaction_type": tx_type,
                    "amount": round(amount, 2),
                    "balance_after": round(balance, 2),
                    "description": description,
                    "merchant_name": description.split()[0],
                    "category": template[1] if not is_credit else "Income",
                    "payment_mode": random.choice(["upi", "card", "neft"]),
                    "reference_number": fake.bban()[:12],
                    "status": "completed"
                })
            
            current_date += timedelta(days=1)
    
    # Insert in batches
    batch_size = 1000
    for i in range(0, len(transactions), batch_size):
        batch = transactions[i:i + batch_size]
        client.insert_rows_json(f"{PROJECT}.{DATASET}.transactions", batch)
    
    return transactions

def generate_investments(profiles: list):
    """Generate investment portfolio data."""
    investments = []
    
    mf_options = [
        ("Parag Parikh Flexicap", "equity", "large_cap", "medium"),
        ("Mirae Asset Large Cap", "equity", "large_cap", "medium"),
        ("Axis Midcap", "equity", "mid_cap", "high"),
        ("Kotak Small Cap", "equity", "small_cap", "high"),
        ("HDFC Corporate Bond", "debt", "corporate_bond", "low"),
        ("SBI Liquid Fund", "debt", "liquid", "low"),
        ("ICICI Pru Balanced Advantage", "hybrid", "balanced", "medium"),
    ]
    
    for profile in profiles:
        customer_id = profile["customer_id"]
        income = profile["monthly_income"]
        risk = profile["risk_appetite"]
        
        # Number of investments based on income
        num_investments = random.randint(2, 5)
        
        for _ in range(num_investments):
            mf = random.choice(mf_options)
            invested = random.uniform(50000, income * 6)
            returns = random.uniform(-0.1, 0.3)  # -10% to +30%
            current = invested * (1 + returns)
            
            investments.append({
                "investment_id": f"INV{uuid.uuid4().hex[:8].upper()}",
                "customer_id": customer_id,
                "asset_type": "mutual_fund",
                "asset_name": mf[0],
                "asset_code": f"MF{random.randint(1000, 9999)}",
                "units": round(invested / random.uniform(50, 500), 3),
                "invested_amount": round(invested, 2),
                "current_value": round(current, 2),
                "purchase_date": fake.date_between(start_date="-3y", end_date="-1m").isoformat(),
                "monthly_sip": round(random.choice([0, 2000, 5000, 10000, 15000]), 2),
                "sip_date": random.randint(1, 28),
                "risk_level": mf[3],
                "category": mf[1],
                "subcategory": mf[2],
                "status": "active",
                "created_at": datetime.now().isoformat()
            })
    
    client.insert_rows_json(f"{PROJECT}.{DATASET}.investments", investments)
    return investments

def generate_loans(profiles: list):
    """Generate loan data."""
    loans = []
    
    loan_types = [
        ("home", 5000000, 10000000, 7.5, 9.5, 180, 300),
        ("car", 500000, 1500000, 8.5, 11, 36, 72),
        ("personal", 100000, 500000, 12, 18, 12, 60),
        ("education", 500000, 2000000, 8, 10, 60, 120),
    ]
    
    for profile in profiles:
        customer_id = profile["customer_id"]
        income = profile["monthly_income"]
        
        # 60% customers have at least one loan
        if random.random() > 0.4:
            # 1-2 loans per customer
            num_loans = random.randint(1, 2)
            
            for _ in range(num_loans):
                loan_type = random.choice(loan_types)
                principal = random.uniform(loan_type[1], loan_type[2])
                rate = random.uniform(loan_type[3], loan_type[4])
                tenure = random.randint(loan_type[5], loan_type[6])
                
                # Calculate EMI
                monthly_rate = rate / 12 / 100
                emi = principal * monthly_rate * pow(1 + monthly_rate, tenure) / \
                      (pow(1 + monthly_rate, tenure) - 1)
                
                # Random remaining tenure
                elapsed = random.randint(6, min(tenure - 6, 48))
                remaining = tenure - elapsed
                
                # Outstanding amount (simplified)
                outstanding = principal * remaining / tenure
                
                start_date = datetime.now() - timedelta(days=elapsed * 30)
                end_date = start_date + timedelta(days=tenure * 30)
                
                loans.append({
                    "loan_id": f"LN{uuid.uuid4().hex[:8].upper()}",
                    "customer_id": customer_id,
                    "loan_type": loan_type[0],
                    "lender_name": random.choice(["HDFC", "ICICI", "SBI", "Axis"]),
                    "principal_amount": round(principal, 2),
                    "outstanding_amount": round(outstanding, 2),
                    "interest_rate": round(rate, 2),
                    "emi": round(emi, 2),
                    "tenure_months": tenure,
                    "remaining_months": remaining,
                    "emi_date": random.randint(1, 15),
                    "start_date": start_date.date().isoformat(),
                    "end_date": end_date.date().isoformat(),
                    "collateral": "Property" if loan_type[0] == "home" else None,
                    "status": "active",
                    "created_at": datetime.now().isoformat()
                })
    
    client.insert_rows_json(f"{PROJECT}.{DATASET}.loans", loans)
    return loans

def generate_credit_cards(profiles: list):
    """Generate credit card data."""
    cards = []
    
    card_types = [
        ("HDFC Regalia", "HDFC", 300000, 500000),
        ("ICICI Amazon Pay", "ICICI", 100000, 300000),
        ("SBI SimplyCLICK", "SBI", 100000, 200000),
        ("Axis Ace", "Axis", 200000, 400000),
    ]
    
    for profile in profiles:
        customer_id = profile["customer_id"]
        income = profile["monthly_income"]
        
        # 70% customers have credit cards
        if random.random() > 0.3:
            num_cards = random.randint(1, 2)
            
            for _ in range(num_cards):
                card = random.choice(card_types)
                limit = random.uniform(card[2], card[3])
                outstanding = random.uniform(0, limit * 0.6)
                
                due_date = datetime.now() + timedelta(days=random.randint(5, 25))
                
                cards.append({
                    "card_id": f"CC{uuid.uuid4().hex[:8].upper()}",
                    "customer_id": customer_id,
                    "card_name": card[0],
                    "card_number_masked": f"XXXX-XXXX-XXXX-{random.randint(1000, 9999)}",
                    "issuer": card[1],
                    "credit_limit": round(limit, 2),
                    "current_outstanding": round(outstanding, 2),
                    "available_limit": round(limit - outstanding, 2),
                    "minimum_due": round(outstanding * 0.05, 2),
                    "total_due": round(outstanding, 2),
                    "payment_due_date": due_date.date().isoformat(),
                    "last_payment_date": (datetime.now() - timedelta(days=random.randint(1, 25))).date().isoformat(),
                    "last_payment_amount": round(random.uniform(5000, 20000), 2),
                    "reward_points": random.randint(1000, 50000),
                    "annual_fee": random.choice([0, 500, 1000, 2500]),
                    "interest_rate": 3.5,  # Monthly rate
                    "status": "active",
                    "created_at": datetime.now().isoformat()
                })
    
    client.insert_rows_json(f"{PROJECT}.{DATASET}.credit_cards", cards)
    return cards

def generate_insurance(profiles: list):
    """Generate insurance policy data."""
    policies = []
    
    for profile in profiles:
        customer_id = profile["customer_id"]
        income = profile["monthly_income"]
        
        # Term life insurance (80% have)
        if random.random() > 0.2:
            cover = income * 12 * random.randint(8, 15)
            policies.append({
                "policy_id": f"POL{uuid.uuid4().hex[:8].upper()}",
                "customer_id": customer_id,
                "policy_type": "term_life",
                "policy_name": random.choice(["HDFC Click 2 Protect", "ICICI iProtect", "Max Life Smart Term"]),
                "insurer": random.choice(["HDFC Life", "ICICI Pru", "Max Life"]),
                "policy_number": fake.bban()[:12],
                "sum_assured": round(cover, 0),
                "premium": round(cover * 0.003, 0),  # Approx 0.3%
                "premium_frequency": "annual",
                "start_date": fake.date_between(start_date="-5y", end_date="-1y").isoformat(),
                "end_date": fake.date_between(start_date="+10y", end_date="+30y").isoformat(),
                "nominee": fake.name(),
                "nominee_relation": random.choice(["Spouse", "Parent", "Child"]),
                "riders": random.choice(["", "Critical Illness", "Accidental Death"]),
                "status": "active",
                "created_at": datetime.now().isoformat()
            })
        
        # Health insurance (70% have)
        if random.random() > 0.3:
            cover = random.choice([500000, 1000000, 1500000, 2000000])
            policies.append({
                "policy_id": f"POL{uuid.uuid4().hex[:8].upper()}",
                "customer_id": customer_id,
                "policy_type": "health",
                "policy_name": random.choice(["Star Health", "HDFC Ergo Health", "Care Health"]),
                "insurer": random.choice(["Star Health", "HDFC Ergo", "Care Health"]),
                "policy_number": fake.bban()[:12],
                "sum_assured": cover,
                "premium": round(cover * 0.015, 0),  # Approx 1.5%
                "premium_frequency": "annual",
                "start_date": fake.date_between(start_date="-2y", end_date="-1m").isoformat(),
                "end_date": fake.date_between(start_date="+6m", end_date="+1y").isoformat(),
                "nominee": fake.name(),
                "nominee_relation": "Self",
                "riders": "",
                "status": "active",
                "created_at": datetime.now().isoformat()
            })
    
    client.insert_rows_json(f"{PROJECT}.{DATASET}.insurance", policies)
    return policies

def generate_financial_goals(profiles: list):
    """Generate financial goals data."""
    goals = []
    
    goal_templates = [
        ("Emergency Fund", "emergency", 3, 12, 0.5),
        ("Retirement Corpus", "retirement", 120, 300, 10),
        ("Child Education", "education", 60, 180, 5),
        ("Home Down Payment", "house", 24, 60, 2),
        ("Dream Vacation", "travel", 6, 18, 0.3),
        ("New Car", "car", 12, 36, 0.8),
    ]
    
    for profile in profiles:
        customer_id = profile["customer_id"]
        income = profile["monthly_income"]
        
        # 2-4 goals per customer
        num_goals = random.randint(2, 4)
        selected = random.sample(goal_templates, num_goals)
        
        for i, goal in enumerate(selected):
            target_months = random.randint(goal[2], goal[3])
            target_amount = income * 12 * goal[4]
            progress = random.uniform(0.1, 0.6)
            
            goals.append({
                "goal_id": f"G{uuid.uuid4().hex[:8].upper()}",
                "customer_id": customer_id,
                "goal_name": goal[0],
                "goal_category": goal[1],
                "target_amount": round(target_amount, 0),
                "current_amount": round(target_amount * progress, 0),
                "target_date": (datetime.now() + timedelta(days=target_months * 30)).date().isoformat(),
                "priority": i + 1,
                "monthly_contribution": round(target_amount * (1 - progress) / target_months, 0),
                "linked_investments": "",
                "risk_level": random.choice(["conservative", "moderate", "aggressive"]),
                "status": "active",
                "created_at": datetime.now().isoformat()
            })
    
    client.insert_rows_json(f"{PROJECT}.{DATASET}.financial_goals", goals)
    return goals

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    print("Generating sample financial data...")
    
    # Generate data
    print("1. Generating customers and profiles...")
    customers, profiles = generate_customers(100)
    
    print("2. Generating accounts...")
    accounts = generate_accounts(customers)
    
    print("3. Generating transactions (this may take a while)...")
    transactions = generate_transactions(accounts, months=6)
    
    print("4. Generating investments...")
    investments = generate_investments(profiles)
    
    print("5. Generating loans...")
    loans = generate_loans(profiles)
    
    print("6. Generating credit cards...")
    cards = generate_credit_cards(profiles)
    
    print("7. Generating insurance policies...")
    insurance = generate_insurance(profiles)
    
    print("8. Generating financial goals...")
    goals = generate_financial_goals(profiles)
    
    print("\n✅ Sample data generation complete!")
    print(f"   - Customers: {len(customers)}")
    print(f"   - Accounts: {len(accounts)}")
    print(f"   - Transactions: {len(transactions)}")
    print(f"   - Investments: {len(investments)}")
    print(f"   - Loans: {len(loans)}")
    print(f"   - Credit Cards: {len(cards)}")
    print(f"   - Insurance Policies: {len(insurance)}")
    print(f"   - Financial Goals: {len(goals)}")
