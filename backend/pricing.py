"""Pricing recommendations for Printify Matte Vertical Posters"""

# Printify base costs (approximate, verify in your account)
PRINTIFY_BASE_COSTS = {
    "8x10": 5.02,
    "11x14": 7.50,
    "12x16": 8.20,
    "16x20": 10.50,
    "18x24": 12.80,
}

# Shipping costs (US domestic, approximate)
SHIPPING_COSTS = {
    "8x10": 4.50,
    "11x14": 5.00,
    "12x16": 5.50,
    "16x20": 6.00,
    "18x24": 7.00,
}

# Etsy fees: 6.5% transaction + 3% + $0.25 payment processing
ETSY_FEE_PERCENT = 0.10  # ~10% total
ETSY_LISTING_FEE = 0.20

# Target profit margins
MARGIN_STRATEGIES = {
    "competitive": 0.30,
    "standard": 0.45,
    "premium": 0.60,
}


def calculate_price(
    size: str,
    strategy: str = "standard",
    free_shipping: bool = True,
) -> dict:
    """Calculate recommended retail price."""
    base_cost = PRINTIFY_BASE_COSTS.get(size, 10.00)
    shipping = SHIPPING_COSTS.get(size, 5.00) if free_shipping else 0
    margin = MARGIN_STRATEGIES.get(strategy, 0.45)

    total_cost = base_cost + shipping + ETSY_LISTING_FEE

    # price = cost / (1 - margin - etsy_fee)
    price = total_cost / (1 - margin - ETSY_FEE_PERCENT)

    # Round to .99
    price = round(price) - 0.01
    if price < total_cost * 1.2:
        price = round(total_cost * 1.3) - 0.01

    # Calculate actual profit
    etsy_fees = price * ETSY_FEE_PERCENT + ETSY_LISTING_FEE
    profit = price - base_cost - shipping - etsy_fees
    actual_margin = profit / price if price > 0 else 0

    return {
        "size": size,
        "strategy": strategy,
        "recommended_price": price,
        "base_cost": base_cost,
        "shipping_included": shipping,
        "etsy_fees": round(etsy_fees, 2),
        "profit": round(profit, 2),
        "margin_percent": round(actual_margin * 100, 1),
    }


def get_minimum_price(size: str) -> float:
    """Get minimum allowed retail price for a size (below this = guaranteed loss).

    Covers: Printify base cost + shipping + Etsy fees + 15% safety margin.
    Uses conservative defaults for unknown sizes.
    """
    base_cost = PRINTIFY_BASE_COSTS.get(size, 15.00)
    shipping = SHIPPING_COSTS.get(size, 7.00)
    total_cost = base_cost + shipping + ETSY_LISTING_FEE
    # price * (1 - etsy_fee - min_margin) >= total_cost
    min_price = total_cost / (1 - ETSY_FEE_PERCENT - 0.15)
    return round(min_price) + 0.99


def enforce_minimum_price(size: str, price_cents: int) -> int:
    """Ensure price (in cents) is not below minimum for a size.

    Returns corrected price in cents.
    """
    min_price_cents = int(get_minimum_price(size) * 100)
    return max(price_cents, min_price_cents)


def get_all_prices(strategy: str = "standard") -> dict:
    """Get recommended prices for all sizes."""
    return {
        size: calculate_price(size, strategy)
        for size in PRINTIFY_BASE_COSTS.keys()
    }
