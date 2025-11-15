import frappe

@frappe.whitelist()
def get_received_qty_map(delivery_note_name):
    """
    Return a map of {Delivery Note Item -> total received qty}
    for a given Delivery Note, optimized to use direct parent link.
    """
    result = frappe.db.sql("""
        SELECT 
            pri.custom_delivery_note_detail AS dn_item,
            SUM(pri.qty) AS total_received_qty
        FROM `tabPurchase Receipt Item` pri
        INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
        WHERE pr.docstatus = 1
          AND pr.custom_delivery_note = %s
          AND pri.custom_delivery_note_detail IS NOT NULL
        GROUP BY pri.custom_delivery_note_detail
    """, (delivery_note_name,), as_dict=True)

    # Convert list of dicts → { child_row_name: total_received_qty }
    return {r.dn_item: r.total_received_qty for r in result}
