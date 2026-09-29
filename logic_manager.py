"""
Applies business rules to AI-enriched product records.
All decisions driven by the AI response from ai_manager.
"""

from datetime import datetime, timedelta

MAX_DISCOUNT_PCT = 70          # Never recommend 100% discount
MIN_PRICE_FLOOR_PCT = 30       # Product must sell for at least 30% of original price
NEAR_EXPIRY_DAYS = 7           # Products expiring within 7 days are "near expiry"
CRITICAL_EXPIRY_DAYS = 2       # Products expiring within 2 days are "critical"
MEMBERSHIP_POINTS_RATE = 0.05  # 5% of purchase value as membership points


def evaluate(record):
    """
    Run all business rules against an AI-enriched record.
    Returns a decision dict with final recommendations.

    Multi-condition rules applied:
    1. Expiry + urgency → final discount
    2. Existing discount + membership → stacking prevention
    3. Risk score + quantity → priority routing
    """
    ai_data = record.get("ai_analysis", {})
    decision = {}

    # Rule 1: expired products cannot be sold
    days_left = record.get("days_until_expiry", 0)
    if days_left <= 0:
        decision["status"] = "EXPIRED"
        decision["can_sell"] = False
        decision["recommended_discount_pct"] = 0
        decision["final_price"] = 0
        decision["action"] = "REMOVE FROM SHELF — product has expired"
        decision["priority"] = "CRITICAL"
        decision["membership_points_eligible"] = False
        decision["discount_approved"] = False
        decision["estimated_waste_cost"] = round(
            record.get("quantity", 0) * record.get("price", 0), 2
        )
        decision["estimated_unsold_units"] = record.get("quantity", 0)
        decision["predicted_demand_units"] = 0
        decision["reasoning"] = "Product has passed its expiry date and must be removed."
        return decision

    # Rule 2: products NOT near expiry get no discount
    if days_left > NEAR_EXPIRY_DAYS:
        decision["status"] = "OK"
        decision["can_sell"] = True
        decision["recommended_discount_pct"] = 0
        decision["final_price"] = round(record.get("price", 0), 2)
        decision["action"] = "NO ACTION NEEDED — product is not near expiry"
        decision["priority"] = "LOW"
        decision["membership_points_eligible"] = record.get("is_member", False)
        decision["discount_approved"] = False
        decision["estimated_waste_cost"] = round(ai_data.get("estimated_waste_cost", 0), 2)
        decision["estimated_unsold_units"] = ai_data.get("estimated_unsold_units", 0)
        decision["predicted_demand_units"] = ai_data.get("predicted_demand_units", 0)
        decision["reasoning"] = (
            f"Product expires in {days_left} days (> {NEAR_EXPIRY_DAYS} day threshold). "
            "No discount needed at this time."
        )
        return decision

    # Near-expiry products: apply AI-driven discount
    decision["status"] = "NEAR_EXPIRY"
    decision["can_sell"] = True

    # MULTI-CONDITION RULE 1: discount depends on AI urgency AND days left
    ai_discount = ai_data.get("recommended_discount_pct", 0)
    urgency = ai_data.get("urgency_level", "low")
    risk_score = ai_data.get("risk_score", 1)

    # Adjust discount based on urgency-days combination
    if days_left <= CRITICAL_EXPIRY_DAYS and urgency in ("high", "critical"):
        # Critical: use higher of AI suggestion or 50%, capped at MAX
        final_discount = max(ai_discount, 50)
    elif days_left <= CRITICAL_EXPIRY_DAYS:
        # Close to expiry but AI says low urgency - still bump to at least 30%
        final_discount = max(ai_discount, 30)
    elif urgency in ("high", "critical") and risk_score >= 7:
        # AI flagged high urgency with high risk - use AI discount as-is
        final_discount = ai_discount
    else:
        # Normal near-expiry - use AI discount but ensure at least 10%
        final_discount = max(ai_discount, 10)

    # Cap at maximum allowed
    final_discount = min(final_discount, MAX_DISCOUNT_PCT)

    # MULTI-CONDITION RULE 2: no stacking if product already discounted
    has_existing_discount = record.get("has_existing_discount", False)
    is_member = record.get("is_member", False)

    if has_existing_discount:
        # Don't stack - override with 0 discount
        final_discount = 0
        decision["action"] = (
            "ALREADY DISCOUNTED — existing promotion active. "
            "No additional expiry discount applied."
        )
        decision["discount_stacking_blocked"] = True
    else:
        decision["discount_stacking_blocked"] = False

    decision["recommended_discount_pct"] = final_discount

    # Calculate final price
    original_price = record.get("price", 0)
    final_price = round(original_price * (1 - final_discount / 100), 2)

    # Ensure price floor
    min_price = round(original_price * (MIN_PRICE_FLOOR_PCT / 100), 2)
    if final_price < min_price and final_discount > 0:
        final_price = min_price
        # Recalculate actual discount percentage
        final_discount = round((1 - min_price / original_price) * 100) if original_price > 0 else 0
        decision["recommended_discount_pct"] = final_discount

    decision["final_price"] = final_price

    # MULTI-CONDITION RULE 3: membership - no additional discount but earn points
    if is_member and has_existing_discount:
        decision["membership_points_eligible"] = True
        decision["membership_discount_applied"] = False
    elif is_member:
        decision["membership_points_eligible"] = True
        decision["membership_discount_applied"] = False  # No stacking with expiry discount
    else:
        decision["membership_points_eligible"] = False
        decision["membership_discount_applied"] = False

    # Membership points calculation
    if decision["membership_points_eligible"]:
        decision["membership_points_earned"] = round(
            final_price * record.get("quantity", 0) * MEMBERSHIP_POINTS_RATE, 2
        )
    else:
        decision["membership_points_earned"] = 0

    # AI-driven fields
    decision["estimated_waste_cost"] = round(ai_data.get("estimated_waste_cost", 0), 2)
    decision["estimated_unsold_units"] = ai_data.get("estimated_unsold_units", 0)
    decision["predicted_demand_units"] = ai_data.get("predicted_demand_units", 0)

    # Set action if not already set
    if "action" not in decision or not decision.get("discount_stacking_blocked"):
        decision["action"] = ai_data.get("action_plan", "Apply recommended discount")

    decision["reasoning"] = ai_data.get("reasoning", "")
    decision["discount_approved"] = False  # Staff must approve

    return decision


def score(record):
    """
    Produce a numeric priority score from AI output fields.
    Used for ranking products by urgency.
    Higher score = more urgent action needed.

    Score formula (0-100):
      risk_score (×5)          → 0-50 points
      urgency multiplier       → ×1.0 to ×2.0
      days penalty             → 0-30 points (fewer days = more points)
      quantity factor           → 0-20 points
    """
    ai_data = record.get("ai_analysis", {})
    days_left = record.get("days_until_expiry", 999)

    # Base from AI risk score (1-10 → 5-50)
    risk = ai_data.get("risk_score", 1)
    base_score = risk * 5

    # Urgency multiplier
    urgency = ai_data.get("urgency_level", "low")
    urgency_multipliers = {
        "low": 1.0,
        "medium": 1.3,
        "high": 1.6,
        "critical": 2.0
    }
    multiplier = urgency_multipliers.get(urgency, 1.0)

    # Days penalty (0-30 points)
    if days_left <= 0:
        days_penalty = 30
    elif days_left <= 2:
        days_penalty = 25
    elif days_left <= 5:
        days_penalty = 15
    elif days_left <= 7:
        days_penalty = 10
    else:
        days_penalty = 0

    # Quantity factor - more stock = higher urgency
    quantity = record.get("quantity", 0)
    unsold = ai_data.get("estimated_unsold_units", 0)
    if quantity > 0 and unsold > 0:
        waste_ratio = unsold / quantity
        quantity_factor = round(waste_ratio * 20)
    else:
        quantity_factor = 0

    total = round(base_score * multiplier + days_penalty + quantity_factor)
    return min(total, 100)  # Cap at 100


def route(record):
    """
    Assign the record to a category / outcome path based on evaluation.
    Returns a route string used by io_manager for display grouping.

    Routes:
      - "REMOVE"       → expired product, must be pulled from shelves
      - "URGENT_ACTION" → critical near-expiry, needs immediate discount approval
      - "DISCOUNT"      → near-expiry, discount recommended
      - "MONITOR"       → not yet near expiry, but AI flagged some risk
      - "OK"            → no action needed
    """
    decision = record.get("decision", {})
    ai_data = record.get("ai_analysis", {})
    days_left = record.get("days_until_expiry", 999)
    risk_score = ai_data.get("risk_score", 1)

    status = decision.get("status", "OK")

    if status == "EXPIRED":
        return "REMOVE"

    if days_left <= CRITICAL_EXPIRY_DAYS and risk_score >= 7:
        return "URGENT_ACTION"

    if decision.get("recommended_discount_pct", 0) > 0:
        return "DISCOUNT"

    if risk_score >= 5 and days_left <= 14:
        return "MONITOR"

    return "OK"

# Helpers

def calculate_days_until_expiry(expiry_date_str):
    """Calculate days between today and the expiry date string (YYYY-MM-DD)."""
    try:
        expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        delta = (expiry - today).days
        return delta
    except (ValueError, TypeError):
        return -1  # Treat unparseable dates as expired


def calculate_savings(record):
    """
    Calculate potential savings if the recommended discount is applied.
    Returns a dict with savings breakdown.
    """
    decision = record.get("decision", {})
    quantity = record.get("quantity", 0)
    original_price = record.get("price", 0)
    discount_pct = decision.get("recommended_discount_pct", 0)
    unsold = decision.get("estimated_unsold_units", 0)
    waste_cost = decision.get("estimated_waste_cost", 0)

    discounted_price = decision.get("final_price", original_price)

    # Revenue from discounted sales (estimated)
    estimated_additional_sales = min(unsold, quantity)
    revenue_with_discount = round(estimated_additional_sales * discounted_price, 2)
    revenue_without_action = 0  # Would be wasted

    return {
        "potential_waste_cost": round(waste_cost, 2),
        "estimated_revenue_with_discount": revenue_with_discount,
        "estimated_savings": round(revenue_with_discount, 2),
        "discount_applied": discount_pct,
        "units_potentially_saved": estimated_additional_sales,
    }


def approve_discount(record):
    """
    Mark a record's discount as approved by staff.
    Returns the updated decision.
    """
    decision = record.get("decision", {})
    decision["discount_approved"] = True
    decision["approved_at"] = datetime.now().isoformat()
    record["decision"] = decision
    return record
