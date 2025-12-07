import frappe
from frappe.utils import flt

def validate(doc, method):
    customer_name = frappe.db.get_value("Customer", {
        "custom_supplier": doc.supplier,
        "custom_is_internal_transfer": 1
    }, "name")

    is_internal_stock_transfer = customer_name is not None

    if is_internal_stock_transfer and doc.items and doc.items[0].purchase_receipt:
        # Get Purchase Receipt linked to this Purchase Invoice
        pr_name = doc.items[0].purchase_receipt

        # Get Delivery Note linked to this Purchase Receipt
        dn = frappe.get_value("Purchase Receipt", pr_name, "custom_delivery_note")
        if not dn:
            return

        # Get PR items with their DN detail mapping
        pr_items = frappe.get_all("Purchase Receipt Item",
            filters={"parent": pr_name},
            fields=["name", "item_code", "qty", "custom_delivery_note_detail"]
        )

        dn_detail_list = [item.custom_delivery_note_detail for item in pr_items if item.custom_delivery_note_detail]

        if not dn_detail_list:
            return

        # Find ALL Sales Invoice Items that reference the same DN items
        si_items = frappe.get_all("Sales Invoice Item",
            filters={
                "delivery_note": dn,
                "dn_detail": ["in", dn_detail_list],
                "docstatus": 1
            },
            fields=["name", "parent", "qty", "item_code", "dn_detail"],
            order_by="creation asc"
        )

        if not si_items:
            return

        # Build a map of dn_detail -> list of SI items (for items with same dn_detail)
        dn_detail_to_si_items = {}
        for si_item in si_items:
            if si_item.dn_detail not in dn_detail_to_si_items:
                dn_detail_to_si_items[si_item.dn_detail] = []
            dn_detail_to_si_items[si_item.dn_detail].append(si_item)

        # For each PI item, find the correct SI item and set custom_sales_invoice_detail
        selected_si = None
        for pi_item in doc.items:
            # Find the corresponding PR item to get the dn_detail
            pr_item = next((p for p in pr_items if p.item_code == pi_item.item_code), None)
            if not pr_item or not pr_item.custom_delivery_note_detail:
                continue

            dn_detail = pr_item.custom_delivery_note_detail
            matching_si_items = dn_detail_to_si_items.get(dn_detail, [])

            # Find SI item with remaining qty to bill
            for si_item in matching_si_items:
                # Get already billed qty for this SI item from other submitted Purchase Invoices
                billed_qty = flt(frappe.db.get_value(
                    "Purchase Invoice Item",
                    {
                        "custom_sales_invoice_detail": si_item.name,
                        "docstatus": 1
                    },
                    "sum(qty)"
                ) or 0)

                remaining_qty = flt(si_item.qty) - billed_qty

                # If this SI item has remaining qty, use it
                if remaining_qty >= flt(pi_item.qty):
                    pi_item.custom_sales_invoice_detail = si_item.name
                    selected_si = si_item.parent
                    break

        if selected_si:
            doc.custom_sales_invoice = selected_si
            doc.write_off_amount = doc.rounded_total
            doc.write_off_account = "Stock Transfer Write Off - AAL"
            doc.write_off_cost_center = doc.cost_center
