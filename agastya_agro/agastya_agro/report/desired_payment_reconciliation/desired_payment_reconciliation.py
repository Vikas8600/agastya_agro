# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate, date_diff

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	"""
	Columns with Debit/Credit like General Ledger for easy matching
	"""
	columns = [
		{'label': 'Customer', 'fieldname': 'customer', 'fieldtype': 'Link', 'options': 'Customer', 'width': 100},
		{'label': 'Customer Name', 'fieldname': 'customer_name', 'fieldtype': 'Data', 'width': 150},
		{'label': 'Posting Date', 'fieldname': 'posting_date', 'fieldtype': 'Date', 'width': 100},
		{'label': 'Voucher Type', 'fieldname': 'voucher_type', 'fieldtype': 'Data', 'width': 120},
		{'label': 'Voucher No', 'fieldname': 'voucher_no', 'fieldtype': 'Dynamic Link', 'options': 'voucher_type', 'width': 150},
		{'label': 'Debit', 'fieldname': 'debit', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Credit', 'fieldname': 'credit', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Against Invoice', 'fieldname': 'against_invoice', 'fieldtype': 'Data', 'width': 140},
		{'label': 'Allocation Amount', 'fieldname': 'allocation_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Days', 'fieldname': 'days', 'fieldtype': 'Int', 'width': 80},
	]
	return columns

def get_data(filters):
	"""
	Payment Reconciliation with GL-style Debit/Credit display

	Logic:
	1. Get opening balance for the customer before the from_date
	2. Get all GL entries (Sales Invoice, Payment Entry, Journal Entry) within date range
	3. Display chronologically with Debit/Credit columns like GL
	4. Show FIFO allocation of payments against Sales Invoices
	"""
	data = []
	customer = filters.get("customer")
	f_date = filters.get("f_date")
	t_date = filters.get("t_date")
	company = filters.get("company")

	if not customer or not company:
		return data

	# Get customer name
	customer_name = frappe.get_cached_value("Customer", customer, "customer_name") or customer

	# =========================================================================
	# STEP 1: Get Opening Balance
	# =========================================================================
	opening_balance = get_opening_balance(customer, company, f_date)

	# =========================================================================
	# STEP 2: Get all GL entries chronologically
	# =========================================================================
	gl_entries = get_all_gl_entries(customer, company, f_date, t_date)

	# =========================================================================
	# STEP 3: Build report with FIFO allocation and running balance
	# =========================================================================
	data = build_report_data(customer, customer_name, opening_balance, gl_entries, f_date)

	return data


def get_opening_balance(customer, company, f_date):
	"""
	Get opening balance for customer before from_date
	Opening = Sum of all debits - Sum of all credits before f_date
	Positive = customer owes money
	Negative = customer has credit/advance
	"""
	if not f_date:
		return 0

	result = frappe.db.sql("""
		SELECT
			COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) as opening
		FROM `tabGL Entry`
		WHERE party_type = 'Customer'
		AND party = %s
		AND company = %s
		AND posting_date < %s
		AND is_cancelled = 0
	""", (customer, company, f_date), as_dict=True)

	return flt(result[0].opening) if result else 0


def get_all_gl_entries(customer, company, f_date, t_date):
	"""
	Get all GL entries for the customer chronologically
	Includes: Sales Invoice, Payment Entry, Journal Entry
	Returns list sorted by date (like General Ledger)
	"""
	conditions = """
		WHERE gl.party_type = 'Customer'
		AND gl.party = %s
		AND gl.company = %s
		AND gl.is_cancelled = 0
		AND gl.voucher_type IN ('Sales Invoice', 'Payment Entry', 'Journal Entry')
	"""
	params = [customer, company]

	if f_date and t_date:
		conditions += " AND gl.posting_date BETWEEN %s AND %s"
		params.extend([f_date, t_date])

	gl_entries = frappe.db.sql("""
		SELECT
			gl.voucher_no as name,
			gl.posting_date as date,
			gl.debit,
			gl.credit,
			gl.voucher_type
		FROM `tabGL Entry` gl
		{conditions}
		ORDER BY gl.posting_date ASC, gl.creation ASC
	""".format(conditions=conditions), params, as_dict=True)

	return gl_entries


def build_report_data(customer, customer_name, opening_balance, gl_entries, f_date):
	"""
	Build report data with GL-style display (Debit/Credit columns) and FIFO allocation

	Shows entries chronologically like General Ledger with:
	- Debit column for Sales Invoice and JV debits
	- Credit column for Payment Entry and JV credits
	- Running balance
	- FIFO allocation of payments against Sales Invoices
	"""
	data = []
	running_balance = opening_balance

	# Separate Sales Invoices for FIFO allocation tracking
	sales_invoices = []
	for entry in gl_entries:
		if entry['voucher_type'] == 'Sales Invoice' and flt(entry['debit']) > 0:
			sales_invoices.append({
				'name': entry['name'],
				'date': entry['date'],
				'amount': flt(entry['debit']),
				'remaining': flt(entry['debit'])
			})

	# Track current invoice index for FIFO allocation
	invoice_idx = 0

	# =========================================================================
	# Opening Balance Row
	# =========================================================================
	if opening_balance != 0:
		row = {
			'customer': customer,
			'customer_name': customer_name,
			'posting_date': f_date,
			'voucher_type': 'Opening',
			'voucher_no': '',
			'debit': opening_balance if opening_balance > 0 else 0,
			'credit': abs(opening_balance) if opening_balance < 0 else 0,
			'balance': running_balance,
			'against_invoice': '',
			'allocation_amount': None,
			'days': None,
		}
		data.append(row)

	# =========================================================================
	# Process each GL entry chronologically
	# =========================================================================
	for entry in gl_entries:
		debit = flt(entry['debit'])
		credit = flt(entry['credit'])

		# Update running balance
		running_balance = flt(running_balance + debit - credit)

		# Determine allocation for credit entries (payments)
		against_invoice = ''
		allocation_amount = None
		days = None

		if credit > 0 and entry['voucher_type'] in ('Payment Entry', 'Journal Entry'):
			# FIFO allocation against Sales Invoices
			remaining_credit = credit
			allocated_invoices = []

			while remaining_credit > 0 and invoice_idx < len(sales_invoices):
				inv = sales_invoices[invoice_idx]

				if inv['remaining'] <= 0:
					invoice_idx += 1
					continue

				# Allocate
				allocation = min(remaining_credit, inv['remaining'])
				inv['remaining'] = flt(inv['remaining'] - allocation)
				remaining_credit = flt(remaining_credit - allocation)

				allocated_invoices.append(inv['name'])

				# Calculate days from invoice date to payment date
				if inv['date'] and entry['date']:
					days = date_diff(entry['date'], inv['date'])

				# Move to next invoice if current is fully paid
				if inv['remaining'] <= 0:
					invoice_idx += 1

			if allocated_invoices:
				against_invoice = ', '.join(allocated_invoices)
				allocation_amount = credit - remaining_credit  # Amount actually allocated

		# Build row
		row = {
			'customer': customer,
			'customer_name': customer_name,
			'posting_date': entry['date'],
			'voucher_type': entry['voucher_type'],
			'voucher_no': entry['name'],
			'debit': debit if debit > 0 else None,
			'credit': credit if credit > 0 else None,
			'balance': running_balance,
			'against_invoice': against_invoice,
			'allocation_amount': allocation_amount,
			'days': days,
		}
		data.append(row)

	# =========================================================================
	# Closing/Total Row
	# =========================================================================
	total_debit = sum(flt(e['debit']) for e in gl_entries)
	total_credit = sum(flt(e['credit']) for e in gl_entries)

	row = {
		'customer': customer,
		'customer_name': customer_name,
		'posting_date': None,
		'voucher_type': 'Closing',
		'voucher_no': '',
		'debit': total_debit + (opening_balance if opening_balance > 0 else 0),
		'credit': total_credit + (abs(opening_balance) if opening_balance < 0 else 0),
		'balance': running_balance,
		'against_invoice': '',
		'allocation_amount': None,
		'days': None,
	}
	data.append(row)

	return data
