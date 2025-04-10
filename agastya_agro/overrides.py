import frappe
from frappe import _, bold, throw
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from frappe.utils import cint, flt
from erpnext.stock.utils import get_incoming_rate
class CustomDeliveryNote(DeliveryNote):
    def set_incoming_rate(self):
        if frappe.db.get_value("Supplier",self.customer,'is_internal_supplier') == 0:
            if self.doctype not in ("Delivery Note", "Sales Invoice"):
                return

            items = self.get("items") + (self.get("packed_items") or [])
            for d in items:
                if not self.get("return_against"):
                    # Get incoming rate based on original item cost based on valuation method
                    qty = flt(d.get('stock_qty') or d.get('actual_qty'))

                    if not d.incoming_rate:
                        d.incoming_rate = get_incoming_rate({
                            "item_code": d.item_code,
                            "warehouse": d.warehouse,
                            "posting_date": self.get('posting_date') or self.get('transaction_date'),
                            "posting_time": self.get('posting_time') or nowtime(),
                            "qty": qty if cint(self.get("is_return")) else (-1 * qty),
                            "serial_no": d.get('serial_no'),
                            "company": self.company,
                            "voucher_type": self.doctype,
                            "voucher_no": self.name,
                            "allow_zero_valuation": d.get("allow_zero_valuation")
                        }, raise_error_if_no_rate=False)

                    # For internal transfers use incoming rate as the valuation rate
                    if self.is_internal_transfer():
                        if d.doctype == "Packed Item":
                            incoming_rate = flt(d.incoming_rate * d.conversion_factor, d.precision('incoming_rate'))
                            if d.incoming_rate != incoming_rate:
                                d.incoming_rate = incoming_rate
                        else:
                            rate = flt(d.incoming_rate * d.conversion_factor, d.precision('rate'))
                            if d.rate != rate:
                                d.rate = rate

                            d.discount_percentage = 0
                            d.discount_amount = 0
                            frappe.msgprint(_("Row {0}: Item rate has been updated as per valuation rate since its an internal stock 111")
                                .format(d.idx), alert=1)

                elif self.get("return_against"):
                    # Get incoming rate of return entry from reference document
                    # based on original item cost as per valuation method
                    d.incoming_rate = get_rate_for_return(self.doctype, self.name, d.item_code, self.return_against, item_row=d)

    def validate_with_previous_doc(self):
        if frappe.db.get_value("Supplier",self.customer,'is_internal_supplier') == 0:
            super(DeliveryNote, self).validate_with_previous_doc({
                "Sales Order": {
                    "ref_dn_field": "against_sales_order",
                    "compare_fields": [["customer", "="], ["company", "="], ["project", "="], ["currency", "="]]
                },
                "Sales Order Item": {
                    "ref_dn_field": "so_detail",
                    "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
                    "is_child_table": True,
                    "allow_duplicate_prev_row_id": True
                },
                "Sales Invoice": {
                    "ref_dn_field": "against_sales_invoice",
                    "compare_fields": [["customer", "="], ["company", "="], ["project", "="], ["currency", "="]]
                },
                "Sales Invoice Item": {
                    "ref_dn_field": "si_detail",
                    "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
                    "is_child_table": True,
                    "allow_duplicate_prev_row_id": True
                },
            })
            
            if cint(frappe.db.get_single_value('Selling Settings', 'maintain_same_sales_rate')) and not self.is_return:
                self.validate_rate_with_reference_doc([["Sales Order", "against_sales_order", "so_detail"],
                    ["Sales Invoice", "against_sales_invoice", "si_detail"]])

class CustomSalesInvoice(SalesInvoice):
    def set_incoming_rate(self):
        if frappe.db.get_value("Customer",self.customer,'is_internal_customer') == 0:
            if self.doctype not in ("Delivery Note", "Sales Invoice"):
                return

            items = self.get("items") + (self.get("packed_items") or [])
            for d in items:
                if not self.get("return_against"):
                    # Get incoming rate based on original item cost based on valuation method
                    qty = flt(d.get('stock_qty') or d.get('actual_qty'))

                    if not d.incoming_rate:
                        d.incoming_rate = get_incoming_rate({
                            "item_code": d.item_code,
                            "warehouse": d.warehouse,
                            "posting_date": self.get('posting_date') or self.get('transaction_date'),
                            "posting_time": self.get('posting_time') or nowtime(),
                            "qty": qty if cint(self.get("is_return")) else (-1 * qty),
                            "serial_no": d.get('serial_no'),
                            "company": self.company,
                            "voucher_type": self.doctype,
                            "voucher_no": self.name,
                            "allow_zero_valuation": d.get("allow_zero_valuation")
                        }, raise_error_if_no_rate=False)

                    # For internal transfers use incoming rate as the valuation rate
                    if self.is_internal_transfer():
                        if d.doctype == "Packed Item":
                            incoming_rate = flt(d.incoming_rate * d.conversion_factor, d.precision('incoming_rate'))
                            if d.incoming_rate != incoming_rate:
                                d.incoming_rate = incoming_rate
                        else:
                            rate = flt(d.incoming_rate * d.conversion_factor, d.precision('rate'))
                            if d.rate != rate:
                                d.rate = rate

                            d.discount_percentage = 0
                            d.discount_amount = 0
                            frappe.msgprint(_("Row {0}: Item rate has been updated as per valuation rate since its an internal stock 111")
                                .format(d.idx), alert=1)

                elif self.get("return_against"):
                    # Get incoming rate of return entry from reference document
                    # based on original item cost as per valuation method
                    d.incoming_rate = get_rate_for_return(self.doctype, self.name, d.item_code, self.return_against, item_row=d)

    def validate_with_previous_doc(self):
        if frappe.db.get_value("Customer",self.customer,'is_internal_customer') == 0:
            super(DeliveryNote, self).validate_with_previous_doc({
                "Sales Order": {
                    "ref_dn_field": "against_sales_order",
                    "compare_fields": [["customer", "="], ["company", "="], ["project", "="], ["currency", "="]]
                },
                "Sales Order Item": {
                    "ref_dn_field": "so_detail",
                    "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
                    "is_child_table": True,
                    "allow_duplicate_prev_row_id": True
                },
                "Sales Invoice": {
                    "ref_dn_field": "against_sales_invoice",
                    "compare_fields": [["customer", "="], ["company", "="], ["project", "="], ["currency", "="]]
                },
                "Sales Invoice Item": {
                    "ref_dn_field": "si_detail",
                    "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
                    "is_child_table": True,
                    "allow_duplicate_prev_row_id": True
                },
            })
            
            if cint(frappe.db.get_single_value('Selling Settings', 'maintain_same_sales_rate')) and not self.is_return:
                self.validate_rate_with_reference_doc([["Sales Order", "against_sales_order", "so_detail"],
                    ["Sales Invoice", "against_sales_invoice", "si_detail"]])
