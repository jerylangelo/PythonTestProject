"""
test_logic.py — Automated test script.
Verifies core logic_manager functions independently of the live API.
Uses hardcoded sample AI responses.
Runs without a live API connection.
Must pass cleanly inside the Docker container.
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logic_manager


# ──────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────
_pass_count = 0
_fail_count = 0


def _run_test(name, test_fn):
    """Run a test function and track pass/fail."""
    global _pass_count, _fail_count
    try:
        test_fn()
        _pass_count += 1
        print(f"  [PASS] {name}")
    except AssertionError as e:
        _fail_count += 1
        print(f"  [FAIL] {name} -- {e}")
    except Exception as e:
        _fail_count += 1
        print(f"  [ERROR] {name} -- {type(e).__name__}: {e}")


# ──────────────────────────────────────────────
# Sample AI responses (hardcoded — no API needed)
# ──────────────────────────────────────────────
SAMPLE_AI_RESPONSE_HIGH_RISK = {
    "urgency_level": "critical",
    "recommended_discount_pct": 55,
    "predicted_demand_units": 5,
    "estimated_unsold_units": 45,
    "estimated_waste_cost": 225.0,
    "risk_score": 9,
    "action_plan": "Apply 55% discount immediately and move to front display.",
    "reasoning": "Product expires in 1 day with 50 units remaining."
}

SAMPLE_AI_RESPONSE_LOW_RISK = {
    "urgency_level": "low",
    "recommended_discount_pct": 10,
    "predicted_demand_units": 80,
    "estimated_unsold_units": 20,
    "estimated_waste_cost": 40.0,
    "risk_score": 3,
    "action_plan": "Apply 10% discount as a precaution.",
    "reasoning": "Product has 5 days left with reasonable demand."
}

SAMPLE_AI_RESPONSE_MEDIUM = {
    "urgency_level": "medium",
    "recommended_discount_pct": 25,
    "predicted_demand_units": 30,
    "estimated_unsold_units": 20,
    "estimated_waste_cost": 100.0,
    "risk_score": 5,
    "action_plan": "Consider promotional placement with discount.",
    "reasoning": "Moderate risk — may sell but discount would help."
}


# ──────────────────────────────────────────────
# Tests: calculate_days_until_expiry
# ──────────────────────────────────────────────

def test_days_until_expiry_future():
    """A date far in the future should return a positive number."""
    result = logic_manager.calculate_days_until_expiry("2099-12-31")
    assert result > 0, f"Expected positive days, got {result}"


def test_days_until_expiry_past():
    """A past date should return a negative number."""
    result = logic_manager.calculate_days_until_expiry("2000-01-01")
    assert result < 0, f"Expected negative days, got {result}"


def test_days_until_expiry_invalid():
    """Invalid date string should return -1."""
    result = logic_manager.calculate_days_until_expiry("not-a-date")
    assert result == -1, f"Expected -1 for invalid date, got {result}"


def test_days_until_expiry_empty():
    """Empty string should return -1."""
    result = logic_manager.calculate_days_until_expiry("")
    assert result == -1, f"Expected -1 for empty string, got {result}"


# ──────────────────────────────────────────────
# Tests: evaluate — expired product
# ──────────────────────────────────────────────

def test_evaluate_expired_product():
    """Expired product must not be sold and gets no discount."""
    record = {
        "product_name": "Expired Milk",
        "quantity": 10,
        "price": 5.00,
        "expiry_date": "2000-01-01",
        "days_until_expiry": -10,
        "has_existing_discount": False,
        "is_member": False,
        "ai_analysis": SAMPLE_AI_RESPONSE_HIGH_RISK,
    }
    decision = logic_manager.evaluate(record)
    assert decision["status"] == "EXPIRED", f"Expected EXPIRED, got {decision['status']}"
    assert decision["can_sell"] is False, "Expired products must not be sellable"
    assert decision["recommended_discount_pct"] == 0, "No discount for expired products"


# ──────────────────────────────────────────────
# Tests: evaluate — product NOT near expiry
# ──────────────────────────────────────────────

def test_evaluate_not_near_expiry():
    """Product with >7 days until expiry gets no discount."""
    record = {
        "product_name": "Fresh Bread",
        "quantity": 100,
        "price": 3.50,
        "expiry_date": "2099-12-31",
        "days_until_expiry": 30,
        "has_existing_discount": False,
        "is_member": False,
        "ai_analysis": SAMPLE_AI_RESPONSE_LOW_RISK,
    }
    decision = logic_manager.evaluate(record)
    assert decision["status"] == "OK", f"Expected OK, got {decision['status']}"
    assert decision["recommended_discount_pct"] == 0, "No discount when not near expiry"
    assert decision["final_price"] == 3.50, f"Price should be unchanged, got {decision['final_price']}"


# ──────────────────────────────────────────────
# Tests: evaluate — near-expiry with AI discount
# ──────────────────────────────────────────────

def test_evaluate_near_expiry_discount():
    """Near-expiry product should get AI-recommended discount, capped at MAX."""
    record = {
        "product_name": "Yogurt",
        "quantity": 50,
        "price": 5.00,
        "expiry_date": "2025-01-02",
        "days_until_expiry": 5,
        "has_existing_discount": False,
        "is_member": False,
        "ai_analysis": SAMPLE_AI_RESPONSE_MEDIUM,
    }
    decision = logic_manager.evaluate(record)
    assert decision["status"] == "NEAR_EXPIRY"
    assert 0 < decision["recommended_discount_pct"] <= logic_manager.MAX_DISCOUNT_PCT, \
        f"Discount {decision['recommended_discount_pct']}% should be 1-{logic_manager.MAX_DISCOUNT_PCT}"
    assert decision["final_price"] < 5.00, "Final price should be less than original"
    assert decision["final_price"] > 0, "Final price must be > 0"


def test_evaluate_critical_expiry_high_urgency():
    """Critical expiry + high urgency should get at least 50% discount."""
    record = {
        "product_name": "Chicken Breast",
        "quantity": 50,
        "price": 10.00,
        "expiry_date": "2025-01-01",
        "days_until_expiry": 1,
        "has_existing_discount": False,
        "is_member": False,
        "ai_analysis": SAMPLE_AI_RESPONSE_HIGH_RISK,
    }
    decision = logic_manager.evaluate(record)
    assert decision["recommended_discount_pct"] >= 50, \
        f"Critical + high urgency should get ≥50%, got {decision['recommended_discount_pct']}%"


# ──────────────────────────────────────────────
# Tests: evaluate — discount stacking prevention
# ──────────────────────────────────────────────

def test_evaluate_no_stacking():
    """Product with existing discount must NOT get an additional discount."""
    record = {
        "product_name": "Sale Cheese",
        "quantity": 20,
        "price": 8.00,
        "expiry_date": "2025-01-03",
        "days_until_expiry": 3,
        "has_existing_discount": True,
        "is_member": False,
        "ai_analysis": SAMPLE_AI_RESPONSE_HIGH_RISK,
    }
    decision = logic_manager.evaluate(record)
    assert decision["recommended_discount_pct"] == 0, \
        f"Stacking should be blocked, got {decision['recommended_discount_pct']}%"
    assert decision.get("discount_stacking_blocked") is True, "Should flag stacking blocked"


# ──────────────────────────────────────────────
# Tests: evaluate — membership rules
# ──────────────────────────────────────────────

def test_evaluate_membership_points():
    """Member product should earn points but not additional discount."""
    record = {
        "product_name": "Premium Butter",
        "quantity": 15,
        "price": 6.00,
        "expiry_date": "2025-01-03",
        "days_until_expiry": 3,
        "has_existing_discount": False,
        "is_member": True,
        "ai_analysis": SAMPLE_AI_RESPONSE_MEDIUM,
    }
    decision = logic_manager.evaluate(record)
    assert decision["membership_points_eligible"] is True, "Member should earn points"
    assert decision.get("membership_discount_applied") is False, "No membership discount stacking"
    assert decision.get("membership_points_earned", 0) > 0, "Should earn some points"


def test_evaluate_membership_with_existing_discount():
    """Member + existing discount: earn points but no discount at all."""
    record = {
        "product_name": "Promo Eggs",
        "quantity": 30,
        "price": 4.00,
        "expiry_date": "2025-01-05",
        "days_until_expiry": 5,
        "has_existing_discount": True,
        "is_member": True,
        "ai_analysis": SAMPLE_AI_RESPONSE_LOW_RISK,
    }
    decision = logic_manager.evaluate(record)
    assert decision["recommended_discount_pct"] == 0, "No discount when already discounted"
    assert decision["membership_points_eligible"] is True, "Should still earn points"


# ──────────────────────────────────────────────
# Tests: evaluate — max discount cap
# ──────────────────────────────────────────────

def test_evaluate_discount_never_100():
    """Discount must never reach 100%."""
    record = {
        "product_name": "Last Day Sausages",
        "quantity": 100,
        "price": 12.00,
        "expiry_date": "2025-01-01",
        "days_until_expiry": 1,
        "has_existing_discount": False,
        "is_member": False,
        "ai_analysis": {
            **SAMPLE_AI_RESPONSE_HIGH_RISK,
            "recommended_discount_pct": 95,  # AI tries 95%
        },
    }
    decision = logic_manager.evaluate(record)
    assert decision["recommended_discount_pct"] <= logic_manager.MAX_DISCOUNT_PCT, \
        f"Discount {decision['recommended_discount_pct']}% exceeds max {logic_manager.MAX_DISCOUNT_PCT}%"
    assert decision["final_price"] > 0, "Price must always be > 0"


# ──────────────────────────────────────────────
# Tests: score
# ──────────────────────────────────────────────

def test_score_high_risk():
    """High-risk product should score higher than low-risk."""
    high_risk = {
        "days_until_expiry": 1,
        "quantity": 50,
        "ai_analysis": SAMPLE_AI_RESPONSE_HIGH_RISK,
    }
    low_risk = {
        "days_until_expiry": 30,
        "quantity": 10,
        "ai_analysis": SAMPLE_AI_RESPONSE_LOW_RISK,
    }
    high_score = logic_manager.score(high_risk)
    low_score = logic_manager.score(low_risk)
    assert high_score > low_score, \
        f"High risk ({high_score}) should score higher than low risk ({low_score})"


def test_score_capped_at_100():
    """Score should never exceed 100."""
    extreme = {
        "days_until_expiry": 0,
        "quantity": 1000,
        "ai_analysis": {
            **SAMPLE_AI_RESPONSE_HIGH_RISK,
            "risk_score": 10,
            "urgency_level": "critical",
            "estimated_unsold_units": 1000,
        },
    }
    result = logic_manager.score(extreme)
    assert result <= 100, f"Score {result} exceeds cap of 100"


def test_score_minimum():
    """Even low-risk products should have a score ≥ 0."""
    minimal = {
        "days_until_expiry": 365,
        "quantity": 1,
        "ai_analysis": {
            "risk_score": 1,
            "urgency_level": "low",
            "estimated_unsold_units": 0,
        },
    }
    result = logic_manager.score(minimal)
    assert result >= 0, f"Score {result} should not be negative"


# ──────────────────────────────────────────────
# Tests: route
# ──────────────────────────────────────────────

def test_route_expired():
    """Expired product should route to REMOVE."""
    record = {
        "days_until_expiry": -1,
        "ai_analysis": SAMPLE_AI_RESPONSE_HIGH_RISK,
        "decision": {"status": "EXPIRED", "recommended_discount_pct": 0},
    }
    assert logic_manager.route(record) == "REMOVE"


def test_route_urgent():
    """Critical expiry + high risk → URGENT_ACTION."""
    record = {
        "days_until_expiry": 1,
        "ai_analysis": {"risk_score": 9, "urgency_level": "critical"},
        "decision": {"status": "NEAR_EXPIRY", "recommended_discount_pct": 50},
    }
    assert logic_manager.route(record) == "URGENT_ACTION"


def test_route_discount():
    """Near-expiry with moderate risk and discount → DISCOUNT."""
    record = {
        "days_until_expiry": 5,
        "ai_analysis": {"risk_score": 5, "urgency_level": "medium"},
        "decision": {"status": "NEAR_EXPIRY", "recommended_discount_pct": 25},
    }
    assert logic_manager.route(record) == "DISCOUNT"


def test_route_ok():
    """Product with no issues → OK."""
    record = {
        "days_until_expiry": 30,
        "ai_analysis": {"risk_score": 2, "urgency_level": "low"},
        "decision": {"status": "OK", "recommended_discount_pct": 0},
    }
    assert logic_manager.route(record) == "OK"


# ──────────────────────────────────────────────
# Tests: calculate_savings
# ──────────────────────────────────────────────

def test_calculate_savings():
    """Savings calculation should return sensible values."""
    record = {
        "quantity": 50,
        "price": 10.00,
        "decision": {
            "recommended_discount_pct": 30,
            "final_price": 7.00,
            "estimated_unsold_units": 30,
            "estimated_waste_cost": 300.0,
        },
    }
    savings = logic_manager.calculate_savings(record)
    assert savings["potential_waste_cost"] == 300.0
    assert savings["estimated_revenue_with_discount"] > 0
    assert savings["discount_applied"] == 30
    assert savings["units_potentially_saved"] == 30


# ──────────────────────────────────────────────
# Tests: approve_discount
# ──────────────────────────────────────────────

def test_approve_discount():
    """Approving a discount should set the flag and timestamp."""
    record = {
        "decision": {
            "recommended_discount_pct": 30,
            "discount_approved": False,
        }
    }
    updated = logic_manager.approve_discount(record)
    assert updated["decision"]["discount_approved"] is True
    assert "approved_at" in updated["decision"]


# ──────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────

def run_all_tests():
    """Execute all test functions and report results."""
    print("\n" + "=" * 60)
    print("  FreshSaver — Logic Manager Test Suite")
    print("=" * 60 + "\n")

    tests = [
        # calculate_days_until_expiry
        ("Days until expiry - future date", test_days_until_expiry_future),
        ("Days until expiry - past date", test_days_until_expiry_past),
        ("Days until expiry - invalid date", test_days_until_expiry_invalid),
        ("Days until expiry - empty string", test_days_until_expiry_empty),
        # evaluate
        ("Evaluate - expired product", test_evaluate_expired_product),
        ("Evaluate - not near expiry", test_evaluate_not_near_expiry),
        ("Evaluate - near-expiry discount", test_evaluate_near_expiry_discount),
        ("Evaluate - critical expiry + high urgency", test_evaluate_critical_expiry_high_urgency),
        ("Evaluate - no discount stacking", test_evaluate_no_stacking),
        ("Evaluate - membership points", test_evaluate_membership_points),
        ("Evaluate - membership with existing discount", test_evaluate_membership_with_existing_discount),
        ("Evaluate - discount never 100%", test_evaluate_discount_never_100),
        # score
        ("Score - high risk > low risk", test_score_high_risk),
        ("Score - capped at 100", test_score_capped_at_100),
        ("Score - minimum >= 0", test_score_minimum),
        # route
        ("Route - expired -> REMOVE", test_route_expired),
        ("Route - critical -> URGENT_ACTION", test_route_urgent),
        ("Route - discount", test_route_discount),
        ("Route - OK", test_route_ok),
        # calculate_savings
        ("Calculate savings", test_calculate_savings),
        # approve_discount
        ("Approve discount", test_approve_discount),
    ]

    for name, fn in tests:
        _run_test(name, fn)

    print("\n" + "-" * 60)
    total = _pass_count + _fail_count
    print(f"  Results: {_pass_count} passed, {_fail_count} failed, {total} total")
    print("-" * 60)

    if _fail_count > 0:
        print("\n  SOME TESTS FAILED\n")
        sys.exit(1)
    else:
        print("\n  ALL TESTS PASSED\n")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
