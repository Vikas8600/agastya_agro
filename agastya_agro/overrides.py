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






# from bs4 import BeautifulSoup
# from frappe.core.doctype.access_log.access_log import make_access_log
# from frappe.utils.pdf import get_pdf
# import frappe


# @frappe.whitelist()
# def report_to_pdf(html, orientation="Landscape"):
#     soup = BeautifulSoup(html, "html.parser")

#     filter_rows = soup.select("div.filter-row")

#     party_type = None
#     party_value = None
#     for row in filter_rows:
#         label = row.find("b")
#         if label:
#             label_text = label.text.strip(":").lower()
#             if label_text == "party type":
#                 party_type = row.get_text(strip=True).replace("Party Type:", "").strip()
#             elif label_text == "party":
#                 party_value = row.get_text(strip=True).replace("Party:", "").strip()

#     if party_type and party_type.lower() == "customer" and party_value:
#         table = soup.find("table")
#         if table:
#             rows = table.find_all("tr")

#             # Find the header row to get column indices
#             if rows:
#                 header_row = rows[0]
#                 headers = header_row.find_all("th")

#                 # Find indices of Debit and Credit columns
#                 debit_index = None
#                 credit_index = None

#                 for idx, header in enumerate(headers):
#                     header_text = header.get_text(strip=True).lower()
#                     if "debit" in header_text:
#                         debit_index = idx
#                     elif "credit" in header_text:
#                         credit_index = idx

#                 # Clear first data row (rows[1]) Debit and Credit values
#                 if len(rows) > 1:
#                     first_data_row = rows[1]
#                     cells = first_data_row.find_all(["td", "th"])
#                     if debit_index is not None and debit_index < len(cells):
#                         cells[debit_index].string = ""
#                     if credit_index is not None and credit_index < len(cells):
#                         cells[credit_index].string = ""

#                 # Clear last data row Debit and Credit values
#                 # Ensure there is at least 2 data rows (header + at least 2 rows)
#                 if len(rows) > 2:
#                     last_data_row = rows[-1]
#                     cells = last_data_row.find_all(["td", "th"])
#                     if debit_index is not None and debit_index < len(cells):
#                         cells[debit_index].string = ""
#                     if credit_index is not None and credit_index < len(cells):
#                         cells[credit_index].string = ""

#         city = frappe.db.get_value("Customer", party_value, "city")
#         if city:
#             city_html = f'<div class="filter-row"><b>City:</b> {city}</div>'

#             if filter_rows:
#                 last_filter = filter_rows[-1]
#                 city_div = BeautifulSoup(city_html, "html.parser")
#                 last_filter.insert_after(city_div)
#             else:
#                 gutter_div = soup.find("div", class_="print-format-gutter")
#                 if gutter_div:
#                     gutter_div.insert(0, BeautifulSoup(city_html, "html.parser"))

#             html = str(soup)
#         else:
#             html = str(soup)
#     else:
#         html = str(soup)

#     make_access_log(file_type="PDF", method="PDF", page=html)
#     frappe.local.response.filename = "report.pdf"
#     frappe.local.response.filecontent = get_pdf(html, {"orientation": orientation})
#     frappe.local.response.type = "pdf"

# from bs4 import BeautifulSoup
# from frappe.core.doctype.access_log.access_log import make_access_log
# from frappe.utils.pdf import get_pdf
# import frappe


# @frappe.whitelist()
# def report_to_pdf(html, orientation="Landscape"):
#     soup = BeautifulSoup(html, "html.parser")

#     filter_rows = soup.select("div.filter-row")

#     party_type = None
#     party_value_raw = None
#     party_values = []
#     party_row = None

#     for row in filter_rows:
#         label = row.find("b")
#         if label:
#             label_text = label.text.strip(":").lower()
#             if label_text == "party type":
#                 party_type = row.get_text(strip=True).replace("Party Type:", "").strip()
#             elif label_text == "party":
#                 party_row = row
#                 party_value_raw = row.get_text(strip=True).replace("Party:", "").strip()

#     if party_value_raw:
#         party_values = [p.strip() for p in party_value_raw.split(",") if p.strip()]

#     first_party = party_values[0] if party_values else None

#     if party_type and party_type.lower() == "customer" and first_party:
#         table = soup.find("table")
#         if table:
#             rows = table.find_all("tr")

#             if rows:
#                 header_row = rows[0]
#                 headers = header_row.find_all("th")

#                 debit_index = None
#                 credit_index = None

#                 for idx, header in enumerate(headers):
#                     header_text = header.get_text(strip=True).lower()
#                     if "debit" in header_text:
#                         debit_index = idx
#                     elif "credit" in header_text:
#                         credit_index = idx

#                 if len(rows) > 1:
#                     first_data_row = rows[1]
#                     cells = first_data_row.find_all(["td", "th"])
#                     if debit_index is not None and debit_index < len(cells):
#                         cells[debit_index].string = ""
#                     if credit_index is not None and credit_index < len(cells):
#                         cells[credit_index].string = ""

#                 if len(rows) > 2:
#                     last_data_row = rows[-1]
#                     cells = last_data_row.find_all(["td", "th"])
#                     if debit_index is not None and debit_index < len(cells):
#                         cells[debit_index].string = ""
#                     if credit_index is not None and credit_index < len(cells):
#                         cells[credit_index].string = ""

#     if party_row and party_values:
#         parent = party_row.parent  
#         siblings = list(parent.children)
#         tag_siblings = [child for child in siblings if getattr(child, "name", None)]
#         try:
#             idx = tag_siblings.index(party_row)
#         except ValueError:
#             idx = -1

#         insert_pos = idx + 1 if idx >= 0 else len(tag_siblings)

#         for pv in party_values:
#             city = frappe.db.get_value("Customer", pv, "city")
#             if city:
#                 city_div = soup.new_tag("div", **{"class": "filter-row"})
#                 b_tag = soup.new_tag("b")
#                 b_tag.string = "City:"
#                 city_div.append(b_tag)
#                 city_div.append(" " + city)

#                 # Insert into parent at the current insert_pos
#                 parent.insert(insert_pos, city_div)
#                 insert_pos += 1

#         html = str(soup)
#     else:
#         html = str(soup)

#     make_access_log(file_type="PDF", method="PDF", page=html)
#     frappe.local.response.filename = "report.pdf"
#     frappe.local.response.filecontent = get_pdf(html, {"orientation": orientation})
#     frappe.local.response.type = "pdf"



from bs4 import BeautifulSoup
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.utils.pdf import get_pdf
import frappe


@frappe.whitelist()
def report_to_pdf(html, orientation="Landscape"):
    soup = BeautifulSoup(html, "html.parser")

    filter_rows = soup.select("div.filter-row")

    party_type = None
    party_value_raw = None
    party_values = []
    party_row = None

    # Extract Party Type and Party (may contain multiple)
    for row in filter_rows:
        label = row.find("b")
        if label:
            label_text = label.text.strip(":").lower()
            if label_text == "party type":
                party_type = row.get_text(strip=True).replace("Party Type:", "").strip()
            elif label_text == "party":
                party_row = row
                party_value_raw = row.get_text(strip=True).replace("Party:", "").strip()

    # Split multiple parties: "2AD140,2AD281" -> ["2AD140", "2AD281"]
    if party_value_raw:
        party_values = [p.strip() for p in party_value_raw.split(",") if p.strip()]

    # Use first party for debit/credit hide logic
    first_party = party_values[0] if party_values else None

    if party_type and party_type.lower() == "customer" and first_party:
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")

            # Find the header row to get column indices
            if rows:
                header_row = rows[0]
                headers = header_row.find_all("th")

                debit_index = None
                credit_index = None

                for idx, header in enumerate(headers):
                    header_text = header.get_text(strip=True).lower()
                    if "debit" in header_text:
                        debit_index = idx
                    elif "credit" in header_text:
                        credit_index = idx

                # Clear Debit and Credit in first data row
                if len(rows) > 1:
                    first_data_row = rows[1]
                    cells = first_data_row.find_all(["td", "th"])
                    if debit_index is not None and debit_index < len(cells):
                        cells[debit_index].string = ""
                    if credit_index is not None and credit_index < len(cells):
                        cells[credit_index].string = ""

                # Clear Debit and Credit in last data row
                if len(rows) > 2:
                    last_data_row = rows[-1]
                    cells = last_data_row.find_all(["td", "th"])
                    if debit_index is not None and debit_index < len(cells):
                        cells[debit_index].string = ""
                    if credit_index is not None and credit_index < len(cells):
                        cells[credit_index].string = ""

    # Insert City div(s) immediately after Party row
    if party_row and party_values:
        parent = party_row.parent
        siblings = list(parent.children)
        tag_siblings = [child for child in siblings if getattr(child, "name", None)]
        try:
            idx = tag_siblings.index(party_row)
        except ValueError:
            idx = -1

        insert_pos = idx + 1 if idx >= 0 else len(tag_siblings)

        for pv in party_values:
            city = frappe.db.get_value("Customer", pv, "city")
            if city:
                city_div = soup.new_tag("div", **{"class": "filter-row"})
                b_tag = soup.new_tag("b")
                b_tag.string = "City:"
                city_div.append(b_tag)
                city_div.append(" " + city)
                parent.insert(insert_pos, city_div)
                insert_pos += 1

        html = str(soup)
    else:
        html = str(soup)

    make_access_log(file_type="PDF", method="PDF", page=html)
    frappe.local.response.filename = "report.pdf"
    frappe.local.response.filecontent = get_pdf(html, {"orientation": orientation})
    frappe.local.response.type = "pdf"
