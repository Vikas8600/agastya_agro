import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_all_pr_from_dn(delivery_note):
    pr_list = frappe.get_all(
        "Purchase Receipt",
        filters={"custom_delivery_note": delivery_note, "docstatus": 1},
        fields=["name"],
        order_by="creation asc"
    )
    return [d.name for d in pr_list]



@frappe.whitelist()
def get_remaining_pr_items(pr_list, sales_invoice):
    if isinstance(pr_list, str):
        pr_list = frappe.parse_json(pr_list)

    si_doc = frappe.get_doc("Sales Invoice", sales_invoice)

    pr_items = []
    supplier = None
    company = si_doc.company


    for pr_name in pr_list:
        pr = frappe.get_doc("Purchase Receipt", pr_name)
        supplier = supplier or pr.supplier
        cost_center = pr.cost_center
        supplier_address = pr.supplier_address
        billing_address = pr.billing_address
        for d in pr.items:

            si_row = next((i for i in si_doc.items if i.name == d.custom_delivery_note_detail), None)

            if not si_row:

                si_row = next((i for i in si_doc.items if i.item_code == d.item_code), None)

            if not si_row:
                continue


            billed_qty = flt(frappe.db.get_value(
                "Purchase Invoice Item",
                {"custom_sales_invoice_detail": si_row.name, "docstatus": 1},
                "sum(qty)"
            ) or 0)

            remaining_qty = flt(si_row.qty) - billed_qty

            if remaining_qty > 0:
                pr_items.append({
                    "pr_name": pr_name,
                    "item_code": d.item_code,
                    "item_name": d.item_name,
                    "description": d.description,
                    "uom": d.uom,
                    "rate": d.rate,
                    "warehouse": d.warehouse,
                    "sales_invoice_item": si_row.name,
                    "remaining_qty": remaining_qty
                })

    return {
        "supplier": supplier,
        "company": company,
        "cost_center":cost_center,
        "supplier_address":supplier_address,
        "billing_address":billing_address,
        "items": pr_items
    }


# import frappe

# @frappe.whitelist()
# def get_pr_from_delivery_note(delivery_note):
   
#     pr_list = frappe.get_all(
#         "Purchase Receipt",
#         filters={"custom_delivery_note": delivery_note, "docstatus": 1},
#         fields=["name"],
#         order_by="creation desc",
#         limit=1
#     )

#     return pr_list[0].name if pr_list else None


# @frappe.whitelist()
# def get_pr_items(pr_name):
#     """
#     Returns all items from a Purchase Receipt, optimized.
#     """
#     pr = frappe.get_doc("Purchase Receipt", pr_name)

#     items = []
#     for d in pr.items:
#         items.append({
#             "item_code": d.item_code,
#             "item_name": d.item_name,
#             "description": d.description,
#             "qty": d.qty,
#             "rate": d.rate,
#             "uom": d.uom,
#             # "warehouse": d.warehouse,
#             "custom_delivery_note_detail": d.custom_delivery_note_detail
#         })

#     return {
#         "supplier": pr.supplier,
#         "posting_date": pr.posting_date,
#         "company": pr.company,
#         "items": items
#     }
