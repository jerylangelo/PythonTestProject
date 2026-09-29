"""
io_manager.py — Input / Output layer.
ALL print() and input() calls in the entire codebase live here.
Collects structured user input, validates, and returns clean typed dicts.
Also contains all display functions.
"""

from datetime import datetime, timedelta


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
CATEGORIES = [
    "Dairy & Eggs",
    "Bakery",
    "Meat & Seafood",
    "Fruits & Vegetables",
    "Frozen Food",
    "Beverages",
    "Snacks & Confectionery",
    "Canned & Packaged Goods",
    "Other",
]

MENU_OPTIONS = {
    "1": "Add new product for assessment",
    "2": "View all products",
    "3": "View near-expiry products",
    "4": "View expired products",
    "5": "Approve a discount recommendation",
    "6": "Record a sale",
    "7": "View sales history",
    "8": "Search products",
    "9": "Delete a product",
    "0": "Exit",
}

# ──────────────────────────────────────────────
# Colour / formatting helpers (ANSI terminal)
# ──────────────────────────────────────────────
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
DIM = "\033[2m"


def _header(text):
    """Print a styled section header."""
    width = 60
    print()
    print(f"{CYAN}{'═' * width}{RESET}")
    print(f"{CYAN}{BOLD}  {text}{RESET}")
    print(f"{CYAN}{'═' * width}{RESET}")


def _subheader(text):
    print(f"\n{BLUE}{BOLD}── {text} ──{RESET}")


def _success(text):
    print(f"{GREEN}✓ {text}{RESET}")


def _warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")


def _error(text):
    print(f"{RED}✗ {text}{RESET}")


def _info(text):
    print(f"{DIM}  {text}{RESET}")


# ──────────────────────────────────────────────
# Menu / navigation
# ──────────────────────────────────────────────

def display_welcome():
    """Show the application welcome banner."""
    print()
    print(f"{CYAN}{BOLD}{'═' * 60}{RESET}")
    print(f"{CYAN}{BOLD}  🛒  FreshSaver — Smart Expiry & Discount Manager{RESET}")
    print(f"{CYAN}{BOLD}{'═' * 60}{RESET}")
    print(f"{DIM}  Reduce food waste. Maximise revenue. AI-powered decisions.{RESET}")
    print()


def display_menu():
    """Display the main menu and return the user's choice."""
    _subheader("Main Menu")
    for key in sorted(MENU_OPTIONS.keys()):
        label = MENU_OPTIONS[key]
        if key == "0":
            print(f"  {DIM}[{key}] {label}{RESET}")
        else:
            print(f"  {BOLD}[{key}]{RESET} {label}")
    print()

    choice = ""
    while choice not in MENU_OPTIONS:
        choice = input(f"{BOLD}Select an option: {RESET}").strip()
        if choice not in MENU_OPTIONS:
            _error("Invalid choice. Please enter a number from the menu.")

    return choice


# ──────────────────────────────────────────────
# Input collection — returns clean typed dicts
# ──────────────────────────────────────────────

def collect_product_input():
    """
    Prompt the user for all product fields.
    Validates type, range, and required fields — rejects and re-prompts on bad data.
    Returns a clean, typed dict ready for ai_manager.
    """
    _header("Add New Product for Assessment")

    # Product name (required, non-empty)
    product_name = ""
    while not product_name:
        product_name = input(f"  Product name: ").strip()
        if not product_name:
            _error("Product name cannot be empty. Try again.")

    # Category (selection from list)
    print(f"\n  {BOLD}Select a category:{RESET}")
    for i, cat in enumerate(CATEGORIES, 1):
        print(f"    [{i}] {cat}")

    category_idx = 0
    while category_idx < 1 or category_idx > len(CATEGORIES):
        raw = input(f"  Enter category number (1-{len(CATEGORIES)}): ").strip()
        if raw.isdigit():
            category_idx = int(raw)
            if category_idx < 1 or category_idx > len(CATEGORIES):
                _error(f"Choose between 1 and {len(CATEGORIES)}.")
        else:
            _error("Please enter a whole number.")

    category = CATEGORIES[category_idx - 1]

    # Quantity (positive integer)
    quantity = 0
    while quantity <= 0:
        raw = input(f"  Quantity in stock: ").strip()
        if raw.isdigit() and int(raw) > 0:
            quantity = int(raw)
        else:
            _error("Quantity must be a positive whole number.")

    # Price (positive float)
    price = 0.0
    while price <= 0:
        raw = input(f"  Current selling price ($): ").strip()
        try:
            val = float(raw)
            if val > 0:
                price = round(val, 2)
            else:
                _error("Price must be greater than $0.00.")
        except ValueError:
            _error("Please enter a valid number (e.g. 4.99).")

    # Expiry date (YYYY-MM-DD, must be parseable)
    expiry_date = ""
    while not expiry_date:
        raw = input(f"  Expiry date (YYYY-MM-DD): ").strip()
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d")
            expiry_date = raw
        except ValueError:
            _error("Invalid date format. Use YYYY-MM-DD (e.g. 2025-12-31).")

    # Has existing discount?
    has_existing_discount = _ask_yes_no("  Does this product already have a discount? (y/n): ")

    # Is member product?
    is_member = _ask_yes_no("  Is this a membership-eligible product? (y/n): ")

    return {
        "product_name": product_name,
        "category": category,
        "quantity": quantity,
        "price": price,
        "expiry_date": expiry_date,
        "has_existing_discount": has_existing_discount,
        "is_member": is_member,
    }


def collect_search_input():
    """Collect search criteria from user. Returns a dict with search params."""
    _subheader("Search Products")
    print(f"  {BOLD}Search by:{RESET}")
    print(f"    [1] Product name")
    print(f"    [2] Category")
    print(f"    [3] Expiry within N days")

    search_type = ""
    while search_type not in ("1", "2", "3"):
        search_type = input(f"  Choose search type (1-3): ").strip()
        if search_type not in ("1", "2", "3"):
            _error("Enter 1, 2, or 3.")

    if search_type == "1":
        term = ""
        while not term:
            term = input(f"  Enter product name (or partial): ").strip()
            if not term:
                _error("Search term cannot be empty.")
        return {"type": "name", "value": term}

    elif search_type == "2":
        print(f"\n  {BOLD}Categories:{RESET}")
        for i, cat in enumerate(CATEGORIES, 1):
            print(f"    [{i}] {cat}")
        cat_idx = 0
        while cat_idx < 1 or cat_idx > len(CATEGORIES):
            raw = input(f"  Enter category number: ").strip()
            if raw.isdigit():
                cat_idx = int(raw)
            if cat_idx < 1 or cat_idx > len(CATEGORIES):
                _error(f"Choose between 1 and {len(CATEGORIES)}.")
        return {"type": "category", "value": CATEGORIES[cat_idx - 1]}

    else:
        days = 0
        while days <= 0:
            raw = input(f"  Show products expiring within how many days? ").strip()
            if raw.isdigit() and int(raw) > 0:
                days = int(raw)
            else:
                _error("Enter a positive number.")
        return {"type": "expiry_days", "value": days}


def collect_sale_input(records):
    """Collect sale details. Returns a sale dict or None if cancelled."""
    _subheader("Record a Sale")

    if not records:
        _warning("No products in the system to record a sale for.")
        return None

    # Show sellable products
    sellable = [r for r in records if r.get("decision", {}).get("can_sell", False)]
    if not sellable:
        _warning("No sellable products available.")
        return None

    print(f"\n  {'ID':<5} {'Product':<25} {'Price':<10} {'Stock':<8}")
    print(f"  {'─' * 48}")
    for r in sellable:
        pid = r.get("id", "?")
        name = r.get("product_name", "Unknown")[:24]
        decision = r.get("decision", {})
        price = decision.get("final_price", r.get("price", 0))
        qty = r.get("quantity", 0)
        print(f"  {pid:<5} {name:<25} ${price:<9.2f} {qty:<8}")

    # Select product
    product_id = 0
    valid_ids = [r.get("id", 0) for r in sellable]
    while product_id not in valid_ids:
        raw = input(f"\n  Enter product ID to sell: ").strip()
        if raw.isdigit():
            product_id = int(raw)
        if product_id not in valid_ids:
            _error("Invalid product ID. Choose from the list above.")

    # Get the selected product
    selected = None
    for r in sellable:
        if r.get("id") == product_id:
            selected = r
            break

    max_qty = selected.get("quantity", 0)

    # Quantity sold
    qty_sold = 0
    while qty_sold <= 0 or qty_sold > max_qty:
        raw = input(f"  Quantity sold (max {max_qty}): ").strip()
        if raw.isdigit() and 0 < int(raw) <= max_qty:
            qty_sold = int(raw)
        else:
            _error(f"Enter a number between 1 and {max_qty}.")

    decision = selected.get("decision", {})
    sell_price = decision.get("final_price", selected.get("price", 0))

    return {
        "product_id": product_id,
        "product_name": selected.get("product_name", "Unknown"),
        "quantity_sold": qty_sold,
        "unit_price": sell_price,
        "total_revenue": round(qty_sold * sell_price, 2),
        "discount_applied": decision.get("recommended_discount_pct", 0),
        "discount_was_approved": decision.get("discount_approved", False),
    }


def collect_product_id(records, prompt_text="Enter product ID: "):
    """Prompt user for a valid product ID from a list. Returns the ID or None."""
    if not records:
        _warning("No products available.")
        return None

    valid_ids = [r.get("id", 0) for r in records]
    product_id = None
    while product_id not in valid_ids:
        raw = input(f"  {prompt_text}").strip()
        if raw.lower() in ("q", "quit", "cancel"):
            return None
        if raw.isdigit():
            product_id = int(raw)
        if product_id not in valid_ids:
            _error(f"Invalid ID. Valid IDs: {valid_ids}. Enter 'q' to cancel.")

    return product_id


# ──────────────────────────────────────────────
# Display functions
# ──────────────────────────────────────────────

def display_processing():
    """Show a processing indicator."""
    print(f"\n{CYAN}  ⏳ Sending product to AI for analysis...{RESET}")


def display_record(record):
    """Display a single product record with its AI analysis and decision."""
    _subheader(f"Product: {record.get('product_name', 'Unknown')}")

    decision = record.get("decision", {})
    ai_data = record.get("ai_analysis", {})
    route = record.get("route", "OK")

    # Route colour
    route_colours = {
        "REMOVE": RED,
        "URGENT_ACTION": RED,
        "DISCOUNT": YELLOW,
        "MONITOR": BLUE,
        "OK": GREEN,
    }
    route_colour = route_colours.get(route, RESET)

    print(f"  {'ID:':<22} {record.get('id', 'N/A')}")
    print(f"  {'Category:':<22} {record.get('category', 'N/A')}")
    print(f"  {'Quantity:':<22} {record.get('quantity', 'N/A')}")
    print(f"  {'Original Price:':<22} ${record.get('price', 0):.2f}")
    print(f"  {'Expiry Date:':<22} {record.get('expiry_date', 'N/A')}")
    print(f"  {'Days Until Expiry:':<22} {record.get('days_until_expiry', 'N/A')}")
    print(f"  {'Status:':<22} {route_colour}{BOLD}{decision.get('status', 'N/A')}{RESET}")
    print(f"  {'Route:':<22} {route_colour}{route}{RESET}")

    if decision.get("recommended_discount_pct", 0) > 0:
        print(f"\n  {YELLOW}{BOLD}Discount Recommendation:{RESET}")
        print(f"  {'Discount:':<22} {decision.get('recommended_discount_pct', 0)}%")
        print(f"  {'Final Price:':<22} ${decision.get('final_price', 0):.2f}")
        approved = decision.get("discount_approved", False)
        status_text = f"{GREEN}APPROVED{RESET}" if approved else f"{YELLOW}PENDING APPROVAL{RESET}"
        print(f"  {'Approval Status:':<22} {status_text}")

    if decision.get("discount_stacking_blocked"):
        print(f"  {DIM}(Discount stacking blocked — existing promotion active){RESET}")

    if decision.get("membership_points_eligible"):
        print(f"  {'Membership Points:':<22} {decision.get('membership_points_earned', 0):.0f} pts")

    # AI Analysis summary
    if ai_data:
        print(f"\n  {MAGENTA}{BOLD}AI Analysis:{RESET}")
        print(f"  {'Urgency:':<22} {ai_data.get('urgency_level', 'N/A')}")
        print(f"  {'Risk Score:':<22} {ai_data.get('risk_score', 'N/A')}/10")
        print(f"  {'Predicted Demand:':<22} {ai_data.get('predicted_demand_units', 'N/A')} units")
        print(f"  {'Est. Unsold Units:':<22} {decision.get('estimated_unsold_units', 'N/A')}")
        print(f"  {'Est. Waste Cost:':<22} ${decision.get('estimated_waste_cost', 0):.2f}")

    print(f"\n  {BOLD}Action:{RESET} {decision.get('action', 'N/A')}")

    if decision.get("reasoning"):
        print(f"  {DIM}Reasoning: {decision.get('reasoning', '')}{RESET}")


def display_list(records, title="Product List"):
    """Display a formatted table of all products."""
    _header(title)

    if not records:
        _info("No products found.")
        return

    # Table header
    print(f"\n  {BOLD}{'ID':<5} {'Product':<20} {'Cat.':<15} {'Qty':<6} {'Price':<9} "
          f"{'Expiry':<12} {'Days':<6} {'Disc%':<7} {'Status':<12}{RESET}")
    print(f"  {'─' * 92}")

    for r in records:
        decision = r.get("decision", {})
        route = r.get("route", "OK")
        days = r.get("days_until_expiry", "?")

        # Colour by route
        if route == "REMOVE":
            colour = RED
        elif route == "URGENT_ACTION":
            colour = RED
        elif route == "DISCOUNT":
            colour = YELLOW
        elif route == "MONITOR":
            colour = BLUE
        else:
            colour = GREEN

        name = r.get("product_name", "?")[:19]
        cat = r.get("category", "?")[:14]
        disc = decision.get("recommended_discount_pct", 0)
        status = decision.get("status", "?")

        print(f"  {r.get('id', '?'):<5} {name:<20} {cat:<15} "
              f"{r.get('quantity', '?'):<6} ${r.get('price', 0):<8.2f} "
              f"{r.get('expiry_date', '?'):<12} {days:<6} "
              f"{disc:<7} {colour}{status:<12}{RESET}")

    print(f"\n  {DIM}Total: {len(records)} product(s){RESET}")


def display_result(message, is_success=True):
    """Display an operation result message."""
    if is_success:
        _success(message)
    else:
        _error(message)


def display_sales(sales, title="Sales History"):
    """Display sales history table."""
    _header(title)

    if not sales:
        _info("No sales recorded yet.")
        return

    print(f"\n  {BOLD}{'Product':<22} {'Qty':<6} {'Unit $':<9} {'Total $':<10} "
          f"{'Disc%':<7} {'Date':<20}{RESET}")
    print(f"  {'─' * 74}")

    total_revenue = 0
    for s in sales:
        name = s.get("product_name", "?")[:21]
        qty = s.get("quantity_sold", 0)
        unit = s.get("unit_price", 0)
        total = s.get("total_revenue", 0)
        disc = s.get("discount_applied", 0)
        date = s.get("sale_date", "?")[:19]
        total_revenue += total

        print(f"  {name:<22} {qty:<6} ${unit:<8.2f} ${total:<9.2f} {disc:<7} {date:<20}")

    print(f"\n  {GREEN}{BOLD}Total Revenue: ${total_revenue:.2f}{RESET}")


def display_savings_summary(savings):
    """Display potential savings from discount recommendations."""
    _subheader("Savings Estimate")
    print(f"  {'Potential Waste Cost:':<30} ${savings.get('potential_waste_cost', 0):.2f}")
    print(f"  {'Est. Revenue w/ Discount:':<30} ${savings.get('estimated_revenue_with_discount', 0):.2f}")
    print(f"  {'Discount Applied:':<30} {savings.get('discount_applied', 0)}%")
    print(f"  {'Units Potentially Saved:':<30} {savings.get('units_potentially_saved', 0)}")
    print(f"  {GREEN}{BOLD}{'Estimated Savings:':<30} ${savings.get('estimated_savings', 0):.2f}{RESET}")


def display_api_error(error_msg):
    """Display an API error with guidance."""
    _error(f"AI Analysis Failed: {error_msg}")
    _info("Please check your internet connection and GROQ_API_KEY.")
    _info("The product cannot be assessed without AI analysis.")


def display_goodbye():
    """Display exit message."""
    print(f"\n{CYAN}{BOLD}  👋  Thank you for using FreshSaver!{RESET}")
    print(f"{DIM}  Reducing food waste, one product at a time.{RESET}\n")


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _ask_yes_no(prompt_text):
    """Ask a yes/no question, return bool."""
    while True:
        raw = input(prompt_text).strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        _error("Please enter 'y' or 'n'.")