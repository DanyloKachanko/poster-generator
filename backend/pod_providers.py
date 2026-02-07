"""
POD (Print on Demand) provider comparison data.
Reference information for choosing the best provider.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class PODProvider:
    id: str
    name: str
    has_etsy_integration: bool
    has_api: bool
    quality_rating: int  # 1-5
    poster_prices: Dict[str, float]  # size -> base cost USD
    shipping_us: Dict[str, float]    # size -> shipping cost USD
    paper_types: List[str]
    finishes: List[str]
    branding_options: List[str]
    production_days: str
    shipping_days_us: str
    notes: str


POD_PROVIDERS = {
    "printify": PODProvider(
        id="printify",
        name="Printify",
        has_etsy_integration=True,
        has_api=True,
        quality_rating=4,
        poster_prices={
            "8x10": 5.02, "11x14": 7.50, "12x16": 8.20,
            "16x20": 10.50, "18x24": 12.80, "24x36": 18.50,
        },
        shipping_us={
            "8x10": 4.50, "11x14": 5.00, "12x16": 5.50,
            "16x20": 6.00, "18x24": 7.00, "24x36": 9.00,
        },
        paper_types=["Matte", "Glossy", "Semi-Glossy"],
        finishes=["Standard", "Premium"],
        branding_options=["Custom packing slip"],
        production_days="2-5",
        shipping_days_us="3-8",
        notes="Multiple print providers. Printify Choice (provider 99) recommended. 20% off with Premium plan ($29/mo).",
    ),
    "printful": PODProvider(
        id="printful",
        name="Printful",
        has_etsy_integration=True,
        has_api=True,
        quality_rating=5,
        poster_prices={
            "8x10": 8.97, "11x14": 10.95, "12x16": 12.95,
            "16x20": 14.95, "18x24": 18.95, "24x36": 24.95,
        },
        shipping_us={
            "8x10": 3.99, "11x14": 4.49, "12x16": 4.99,
            "16x20": 5.49, "18x24": 5.99, "24x36": 7.99,
        },
        paper_types=["Enhanced Matte", "Luster Photo"],
        finishes=["Matte", "Glossy"],
        branding_options=["Custom labels", "Pack-ins", "Custom packaging"],
        production_days="2-5",
        shipping_days_us="3-8",
        notes="Owns production. Best quality control. Higher prices but consistent quality.",
    ),
    "gooten": PODProvider(
        id="gooten",
        name="Gooten",
        has_etsy_integration=True,
        has_api=True,
        quality_rating=3,
        poster_prices={
            "8x10": 4.90, "11x14": 6.50, "12x16": 7.50,
            "16x20": 9.00, "18x24": 11.00, "24x36": 15.00,
        },
        shipping_us={
            "8x10": 5.00, "11x14": 5.50, "12x16": 6.00,
            "16x20": 6.50, "18x24": 7.50, "24x36": 10.00,
        },
        paper_types=["Matte", "Glossy"],
        finishes=["Standard"],
        branding_options=["Custom neck labels ($2)", "Custom packing slips"],
        production_days="1-4",
        shipping_days_us="3-10",
        notes="Lowest prices. Quality varies by provider. Best for 250+ orders/month. Volume discounts.",
    ),
    "gelato": PODProvider(
        id="gelato",
        name="Gelato",
        has_etsy_integration=True,
        has_api=True,
        quality_rating=4,
        poster_prices={
            "8x10": 6.50, "11x14": 8.00, "12x16": 9.50,
            "16x20": 11.00, "18x24": 14.00, "24x36": 18.00,
        },
        shipping_us={
            "8x10": 3.50, "11x14": 4.00, "12x16": 4.50,
            "16x20": 5.00, "18x24": 5.50, "24x36": 7.50,
        },
        paper_types=["Premium Matte", "Fine Art", "Photo Lustre"],
        finishes=["Matte", "Glossy", "Semi-Glossy"],
        branding_options=["Custom packaging", "Thank you cards"],
        production_days="1-3",
        shipping_days_us="2-5",
        notes="Local production in 32 countries. Fastest shipping. Eco-friendly. Gelato+ subscription for discounts.",
    ),
    "prodigi": PODProvider(
        id="prodigi",
        name="Prodigi",
        has_etsy_integration=False,
        has_api=True,
        quality_rating=5,
        poster_prices={
            "8x10": 7.00, "11x14": 9.00, "12x16": 10.50,
            "16x20": 12.00, "18x24": 15.00, "24x36": 20.00,
        },
        shipping_us={
            "8x10": 4.00, "11x14": 4.50, "12x16": 5.00,
            "16x20": 5.50, "18x24": 6.00, "24x36": 8.00,
        },
        paper_types=["Fine Art", "Photo Lustre", "Canvas"],
        finishes=["Matte", "Glossy", "Metallic"],
        branding_options=["Full white-label"],
        production_days="2-5",
        shipping_days_us="5-10",
        notes="Premium fine art printing. Best paper quality. Museum-grade. No direct Etsy integration - API only.",
    ),
}

RECOMMENDATIONS = {
    "starting_out": {
        "provider": "printify",
        "reason": "Best balance of price and quality. Easy Etsy integration. Multiple print providers.",
        "tips": [
            "Use Printify Choice as print provider for posters",
            "Start with Matte finish - most popular",
            "Consider Premium plan if doing 10+ orders/month",
        ],
    },
    "premium_quality": {
        "provider": "printful",
        "reason": "Owns production, consistent quality. Best for building premium brand.",
        "tips": [
            "Use Enhanced Matte paper for art prints",
            "Add custom branding for premium feel",
            "Higher prices allow for premium positioning",
        ],
    },
    "budget_focus": {
        "provider": "gooten",
        "reason": "Lowest base prices. Good for high volume.",
        "tips": [
            "Order samples first - quality varies",
            "Best for 250+ orders/month",
            "Volume discounts available",
        ],
    },
    "global_shipping": {
        "provider": "gelato",
        "reason": "Local production in 32 countries. Fastest international shipping.",
        "tips": [
            "Great for EU customers",
            "Eco-friendly production",
            "Consider Gelato+ for discounts",
        ],
    },
    "fine_art": {
        "provider": "prodigi",
        "reason": "Museum-grade printing. Best paper quality.",
        "tips": [
            "API integration only - more setup required",
            "Target art collectors market",
            "Premium pricing justified by quality",
        ],
    },
}


def get_all_providers() -> list:
    return [asdict(p) for p in POD_PROVIDERS.values()]


def compare_providers(size: str) -> list:
    results = []
    for p in POD_PROVIDERS.values():
        if size in p.poster_prices:
            base = p.poster_prices[size]
            ship = p.shipping_us.get(size, 5.0)
            results.append({
                "provider": p.name,
                "provider_id": p.id,
                "base_cost": base,
                "shipping": ship,
                "total": round(base + ship, 2),
                "quality": p.quality_rating,
                "production_days": p.production_days,
                "has_etsy": p.has_etsy_integration,
            })
    return sorted(results, key=lambda x: x["total"])
