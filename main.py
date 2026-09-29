"""
main.py: Application entry point
Orchestrates the four-module pipeline:
  io_manager → ai_manager → logic_manager → data_manager
  
No class definitions as per 100% procedural requirement.
I tell you first before AI tells you:
 - Python has a library called pydantic that allows you to force the AI model to respond to a specific schema (like the JSON requirement here). Don't use it though, your professor will instant fail you cus it fails the '100% procedural' rule 😄
"""

import io_manager
import ai_manager
import logic_manager
import data_manager


def process_new_product(product_data):
    """
    Full pipeline for a new product:
    1. Calculate days until expiry (logic_manager)
    2. Send to AI for analysis (ai_manager) - must fail if A
    4. Route the record (logic_manager)I returns invalid/not present
    3. Apply business rules (logic_manager)
    5. Score the record (logic_manager)
    6. Save to file (data_manager)
    """
    
    # This was auto-generated - pretty sure not a requirement 
    product_data["days_until_expiry"] = logic_manager.calculate_days_until_expiry(
        product_data["expiry_date"]
    )
     
    io_manager.display_processing()
    success, ai_result = ai_manager.process_record(product_data)

    if not success:
        io_manager.display_api_error(ai_result)
        return None

    # Attach AI analysis to the record
    product_data["ai_analysis"] = ai_result

    # ── Business rules ──
    decision = logic_manager.evaluate(product_data)
    product_data["decision"] = decision

    # ── Route ──
    product_data["route"] = logic_manager.route(product_data)

    # ── Score ──
    product_data["priority_score"] = logic_manager.score(product_data)

    # ── Persist ──
    saved = data_manager.save(product_data)

    return saved


def handle_add_product():
    """Menu option 1: collect input, process, display result."""
    product_data = io_manager.collect_product_input()
    result = process_new_product(product_data)

    if result:
        io_manager.display_result("Product assessed and saved successfully!")
        io_manager.display_record(result)
        savings = logic_manager.calculate_savings(result)
        io_manager.display_savings_summary(savings)
    else:
        io_manager.display_result("Failed to process product. See error above.", is_success=False)


def handle_view_all():
    """Menu option 2: display all products."""
    records = data_manager.load()
    # Re-calculate days for display (they may have changed since last run)
    for r in records:
        r["days_until_expiry"] = logic_manager.calculate_days_until_expiry(
            r.get("expiry_date", "")
        )
    # Sort by priority score (highest first)
    records.sort(key=lambda r: r.get("priority_score", 0), reverse=True)
    io_manager.display_list(records, "All Products")


def handle_view_near_expiry():
    """Menu option 3: display products expiring within 7 days."""
    records = data_manager.query(
        lambda r: 0 < logic_manager.calculate_days_until_expiry(
            r.get("expiry_date", "")
        ) <= logic_manager.NEAR_EXPIRY_DAYS
    )
    for r in records:
        r["days_until_expiry"] = logic_manager.calculate_days_until_expiry(
            r.get("expiry_date", "")
        )
    records.sort(key=lambda r: r.get("days_until_expiry", 999))
    io_manager.display_list(records, "Near-Expiry Products (≤ 7 days)")

    # Also show detailed view for each
    for r in records:
        io_manager.display_record(r)


def handle_view_expired():
    """Menu option 4: display expired products."""
    records = data_manager.query(
        lambda r: logic_manager.calculate_days_until_expiry(
            r.get("expiry_date", "")
        ) <= 0
    )
    for r in records:
        r["days_until_expiry"] = logic_manager.calculate_days_until_expiry(
            r.get("expiry_date", "")
        )
    io_manager.display_list(records, "Expired Products")


def handle_approve_discount():
    """Menu option 5: approve a pending discount recommendation."""
    # Find products with pending (unapproved) discounts
    records = data_manager.query(
        lambda r: (
            r.get("decision", {}).get("recommended_discount_pct", 0) > 0
            and not r.get("decision", {}).get("discount_approved", False)
        )
    )

    if not records:
        io_manager.display_result("No pending discount approvals.", is_success=True)
        return

    io_manager.display_list(records, "Products with Pending Discount Approval")

    product_id = io_manager.collect_product_id(records, "Enter product ID to approve discount: ")
    if product_id is None:
        return

    # Find and approve
    for r in records:
        if r.get("id") == product_id:
            updated = logic_manager.approve_discount(r)
            data_manager.update(product_id, {"decision": updated["decision"]})
            io_manager.display_result(
                f"Discount of {updated['decision']['recommended_discount_pct']}% "
                f"approved for '{r.get('product_name')}'!"
            )
            io_manager.display_record(r)
            return

    io_manager.display_result("Product not found.", is_success=False)


def handle_record_sale():
    """Menu option 6: record a sale transaction."""
    records = data_manager.load()
    # Refresh days
    for r in records:
        r["days_until_expiry"] = logic_manager.calculate_days_until_expiry(
            r.get("expiry_date", "")
        )

    sale_data = io_manager.collect_sale_input(records)
    if sale_data is None:
        return

    # Update stock quantity
    product_id = sale_data["product_id"]
    for r in records:
        if r.get("id") == product_id:
            new_qty = r.get("quantity", 0) - sale_data["quantity_sold"]
            data_manager.update(product_id, {"quantity": max(new_qty, 0)})
            break

    # Save sale record
    data_manager.save_sale(sale_data)
    io_manager.display_result(
        f"Sale recorded: {sale_data['quantity_sold']}x {sale_data['product_name']} "
        f"= ${sale_data['total_revenue']:.2f}"
    )


def handle_view_sales():
    """Menu option 7: view sales history."""
    sales = data_manager.load_sales()
    io_manager.display_sales(sales)


def handle_search():
    """Menu option 8: search products by criteria."""
    search = io_manager.collect_search_input()

    if search["type"] == "name":
        results = data_manager.query(
            lambda r: search["value"].lower() in r.get("product_name", "").lower()
        )
    elif search["type"] == "category":
        results = data_manager.query(
            lambda r: r.get("category", "") == search["value"]
        )
    else:  # expiry_days
        results = data_manager.query(
            lambda r: 0 < logic_manager.calculate_days_until_expiry(
                r.get("expiry_date", "")
            ) <= search["value"]
        )

    for r in results:
        r["days_until_expiry"] = logic_manager.calculate_days_until_expiry(
            r.get("expiry_date", "")
        )

    io_manager.display_list(results, f"Search Results ({len(results)} found)")


def handle_delete():
    """Menu option 9: delete a product record."""
    records = data_manager.load()
    if not records:
        io_manager.display_result("No products to delete.", is_success=True)
        return

    io_manager.display_list(records, "Select a Product to Delete")
    product_id = io_manager.collect_product_id(records, "Enter product ID to delete: ")
    if product_id is None:
        return

    deleted = data_manager.delete(product_id)
    if deleted:
        io_manager.display_result(f"Product ID {product_id} deleted.")
    else:
        io_manager.display_result("Product not found.", is_success=False)


# ──────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────

def main():
    """Application entry point — main menu loop."""
    io_manager.display_welcome()

    handlers = {
        "1": handle_add_product,
        "2": handle_view_all,
        "3": handle_view_near_expiry,
        "4": handle_view_expired,
        "5": handle_approve_discount,
        "6": handle_record_sale,
        "7": handle_view_sales,
        "8": handle_search,
        "9": handle_delete,
    }

    while True:
        choice = io_manager.display_menu()

        if choice == "0":
            io_manager.display_goodbye()
            break

        handler = handlers.get(choice)
        if handler:
            handler()


if __name__ == "__main__":
    main()
