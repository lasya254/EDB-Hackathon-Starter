from .data import CUSTOMERS, BONDS, TIER_BONUS


def get_customer_info(customer_id: str) -> dict:
    """Get customer information and membership tier by customer ID."""
    customer = CUSTOMERS.get(customer_id.lower())
    if not customer:
        return {
            "status": "not_found",
            "message": f"No customer found with ID '{customer_id}'."
        }
    return {
        "status": "success",
        "customer_id": customer_id,
        "name": customer["name"],
        "tier": customer["tier"],
        "balance": f"£{customer['balance']}",
        "message": f"Welcome {customer['name']}! You are a {customer['tier'].upper()} member."
    }


def get_available_bonds(investment_amount: float) -> dict:
    """Get all bonds available for a given investment amount."""
    available = [
        {
            "bond_id": bond_id,
            "name": bond["name"],
            "duration": bond["duration"],
            "base_rate": f"{bond['base_rate']}%",
            "min_investment": f"£{bond['min_investment']}",
            "max_investment": f"£{bond['max_investment']}",
        }
        for bond_id, bond in BONDS.items()
        if bond["min_investment"] <= investment_amount <= bond["max_investment"]
    ]

    if not available:
        return {
            "status": "none_available",
            "message": f"No bonds available for £{investment_amount}. Minimum investment is £100."
        }
    return {
        "status": "success",
        "investment_amount": f"£{investment_amount}",
        "available_bonds": available,
        "count": len(available)
    }


def calculate_returns(customer_id: str, bond_id: str, investment_amount: float) -> dict:
    """Calculate final interest rate and returns for a customer investing in a specific bond."""
    customer = CUSTOMERS.get(customer_id.lower())
    if not customer:
        return {"status": "error", "message": f"Customer '{customer_id}' not found."}

    bond = BONDS.get(bond_id.lower())
    if not bond:
        return {"status": "error", "message": f"Bond '{bond_id}' not found."}

    if investment_amount < bond["min_investment"]:
        return {"status": "error", "message": f"Minimum investment for {bond['name']} is £{bond['min_investment']}."}
    if investment_amount > bond["max_investment"]:
        return {"status": "error", "message": f"Maximum investment for {bond['name']} is £{bond['max_investment']}."}

    tier        = customer["tier"]
    base_rate   = bond["base_rate"]
    bonus_rate  = TIER_BONUS.get(tier, 0.0)
    final_rate  = base_rate + bonus_rate
    years       = bond["duration_years"]
    interest    = round(investment_amount * (final_rate / 100) * years, 2)
    total       = round(investment_amount + interest, 2)

    return {
        "status": "success",
        "customer_name": customer["name"],
        "membership_tier": tier.upper(),
        "bond_name": bond["name"],
        "duration": bond["duration"],
        "investment_amount": f"£{investment_amount}",
        "base_interest_rate": f"{base_rate}%",
        "loyalty_bonus": f"+{bonus_rate}%" if bonus_rate > 0 else "None (Standard member)",
        "final_interest_rate": f"{final_rate}%",
        "interest_earned": f"£{interest}",
        "total_return": f"£{total}",
        "summary": (
            f"By investing £{investment_amount} in {bond['name']} for {bond['duration']}, "
            f"you earn £{interest} interest at {final_rate}% "
            f"(base {base_rate}% + {bonus_rate}% {tier.upper()} bonus), "
            f"giving a total return of £{total}."
        )
    }


def compare_bonds(customer_id: str, investment_amount: float) -> dict:
    """Compare all available bonds for a customer showing returns for each."""
    customer = CUSTOMERS.get(customer_id.lower())
    if not customer:
        return {"status": "error", "message": f"Customer '{customer_id}' not found."}

    tier       = customer["tier"]
    bonus_rate = TIER_BONUS.get(tier, 0.0)

    comparison = []
    for bond_id, bond in BONDS.items():
        if bond["min_investment"] <= investment_amount <= bond["max_investment"]:
            final_rate = bond["base_rate"] + bonus_rate
            interest   = round(investment_amount * (final_rate / 100) * bond["duration_years"], 2)
            total      = round(investment_amount + interest, 2)
            comparison.append({
                "bond_id": bond_id,
                "bond_name": bond["name"],
                "duration": bond["duration"],
                "base_rate": f"{bond['base_rate']}%",
                "your_rate": f"{final_rate}%",
                "interest_earned": f"£{interest}",
                "total_return": f"£{total}",
            })

    if not comparison:
        return {"status": "none_available", "message": f"No bonds available for £{investment_amount}."}

    comparison.sort(key=lambda x: float(x["total_return"].replace("£", "")), reverse=True)

    return {
        "status": "success",
        "customer_name": customer["name"],
        "membership_tier": tier.upper(),
        "investment_amount": f"£{investment_amount}",
        "loyalty_bonus": f"+{bonus_rate}%",
        "bond_comparison": comparison,
        "best_bond": comparison[0]["bond_name"]
    }