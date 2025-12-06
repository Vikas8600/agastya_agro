import frappe

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

        # Get DN items that were used to create this PR
        # by matching dn_detail from PR items
        pr_items = frappe.get_all("Purchase Receipt Item",
            filters={"parent": pr_name},
            fields=["custom_delivery_note_detail"]
        )
        # frappe.throw(str(pr_items))
        dn_detail_list = [item.custom_delivery_note_detail for item in pr_items if item.custom_delivery_note_detail]

        if not dn_detail_list:
            return
        # Find Sales Invoice Items that reference the same DN items
        # SI Item has delivery_note and dn_detail fields
        si_item = frappe.get_value("Sales Invoice Item", {
            "delivery_note": dn,
            "dn_detail": ["in", dn_detail_list]
        }, "parent")

        if si_item:
            doc.custom_sales_invoice = si_item
            doc.write_off_amount = doc.rounded_total
            doc.write_off_account = "Stock Transfer Write Off - AAL"
            doc.write_off_cost_center = doc.cost_center