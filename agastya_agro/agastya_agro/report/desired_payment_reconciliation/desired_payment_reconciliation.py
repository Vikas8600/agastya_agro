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
		{'label': 'Sales Invoice', 'fieldname': 'sales_invoice', 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 140},
		{'label': 'Invoice Date', 'fieldname': 'invoice_date', 'fieldtype': 'Date', 'width': 100},
		# {'label': 'Amount', 'fieldname': 'invoice_amount', 'fieldtype': 'Currency', 'width': 120},  # Redundant - same as Debit for invoices
		{'label': 'Allocation Amount', 'fieldname': 'allocation_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Invoice Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'width': 120},
		# {'label': 'Opening Credit Balance', 'fieldname': 'opening_credit_balance', 'fieldtype': 'Currency', 'width': 150},
		# {'label': 'Collection Amount', 'fieldname': 'collection_amount', 'fieldtype': 'Currency', 'width': 130},  # Redundant - same as Credit for payments
		{'label': 'Voucher No', 'fieldname': 'voucher_no', 'fieldtype': 'Dynamic Link', 'options': 'voucher_type', 'width': 150},
		{'label': 'Voucher Type', 'fieldname': 'voucher_type', 'fieldtype': 'Data', 'width': 120},
		{'label': 'Voucher Date', 'fieldname': 'voucher_date', 'fieldtype': 'Date', 'width': 100},
		# {'label': 'Voucher Amount', 'fieldname': 'voucher_amount', 'fieldtype': 'Currency', 'width': 120},  # Redundant - same as Credit for payments
		{'label': 'Debit', 'fieldname': 'debit', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Credit', 'fieldname': 'credit', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Running Balance', 'fieldname': 'running_balance', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Days', 'fieldname': 'days', 'fieldtype': 'Int', 'width': 80},
	]
	return columns

def get_data(filters):
	"""
	Payment Reconciliation - Invoice centric with FIFO allocation

	Shows invoices in date order, with payments allocated against each invoice
	First invoice must be fully cleared before moving to next invoice
	"""
	data = []
	customer = filters.get("customer")
	f_date = filters.get("f_date")
	t_date = filters.get("t_date")
	company = filters.get("company")

	if not customer or not company:
		return data

	customer_name = frappe.get_cached_value("Customer", customer, "customer_name") or customer

	# Get opening balance
	opening_balance = get_opening_balance(customer, company, f_date)

	# Get invoices (debit entries) sorted by date ASC
	invoices = get_invoices(customer, company, f_date, t_date)

	# Get all credit entries (payments, JV credits) sorted by date ASC
	credits = get_credit_entries(customer, company, f_date, t_date)

	# Build report - invoice by invoice with FIFO allocation
	data = build_invoice_centric_report(customer, customer_name, opening_balance, invoices, credits, f_date)

	return data


def get_opening_balance(customer, company, f_date):
	"""Get opening balance for customer before from_date"""
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


def get_invoices(customer, company, f_date, t_date):
	"""
	Get all Sales Invoice debit entries sorted by date ASC
	"""
	conditions = """
		WHERE gl.party_type = 'Customer'
		AND gl.party = %s
		AND gl.company = %s
		AND gl.is_cancelled = 0
		AND gl.voucher_type = 'Sales Invoice'
		AND gl.debit > 0
	"""
	params = [customer, company]

	if f_date and t_date:
		conditions += " AND gl.posting_date BETWEEN %s AND %s"
		params.extend([f_date, t_date])

	invoices = frappe.db.sql("""
		SELECT
			gl.voucher_no as name,
			gl.posting_date as date,
			gl.debit as amount,
			gl.voucher_type
		FROM `tabGL Entry` gl
		{conditions}
		GROUP BY gl.voucher_no
		ORDER BY gl.posting_date ASC, gl.creation ASC
	""".format(conditions=conditions), params, as_dict=True)

	return invoices


def get_credit_entries(customer, company, f_date, t_date):
	"""
	Get all credit entries (Payment Entry, Journal Entry credits) sorted by date ASC
	"""
	conditions = """
		WHERE gl.party_type = 'Customer'
		AND gl.party = %s
		AND gl.company = %s
		AND gl.is_cancelled = 0
		AND gl.voucher_type IN ('Payment Entry', 'Journal Entry')
		AND gl.credit > 0
	"""
	params = [customer, company]

	if f_date and t_date:
		conditions += " AND gl.posting_date BETWEEN %s AND %s"
		params.extend([f_date, t_date])

	credits = frappe.db.sql("""
		SELECT
			gl.voucher_no as name,
			gl.posting_date as date,
			gl.credit as amount,
			gl.voucher_type
		FROM `tabGL Entry` gl
		{conditions}
		GROUP BY gl.voucher_no
		ORDER BY gl.posting_date ASC, gl.creation ASC
	""".format(conditions=conditions), params, as_dict=True)

	return credits


def build_invoice_centric_report(customer, customer_name, opening_balance, invoices, credits, f_date):
	"""
	Build report showing:
	- Invoice 1 (oldest) with debit
	  - Payment allocations against Invoice 1 (until cleared)
	- Invoice 2 (next oldest) with debit
	  - Payment allocations against Invoice 2
	- ... and so on

	Running balance is calculated as: Opening + Debits - Credits
	"""
	data = []
	running_balance = opening_balance

	# Credit queue for FIFO allocation (oldest payment first)
	credit_queue = []
	for c in credits:
		credit_queue.append({
			'name': c['name'],
			'date': c['date'],
			'amount': flt(c['amount']),
			'remaining': flt(c['amount']),
			'voucher_type': c['voucher_type']
		})

	credit_idx = 0  # Current credit for FIFO allocation

	# Opening Balance Row
	if opening_balance != 0:
		row = {
			'customer': customer,
			'customer_name': customer_name,
			'sales_invoice': 'Opening Balance',
			'invoice_date': f_date,
			'invoice_amount': abs(opening_balance),
			'allocation_amount': None,
			'balance': None,
			'collection_amount': None,
			'voucher_no': '',
			'voucher_type': 'Opening',
			'voucher_date': f_date,
			'voucher_amount': abs(opening_balance),
			'debit': opening_balance if opening_balance > 0 else None,
			'credit': abs(opening_balance) if opening_balance < 0 else None,
			'running_balance': running_balance,
			'opening_credit_balance': None,
			'days': None,
		}
		data.append(row)

	# Process each invoice in date order
	for invoice in invoices:
		inv_name = invoice['name']
		inv_date = invoice['date']
		inv_amount = flt(invoice['amount'])
		inv_remaining = inv_amount

		# Update running balance for invoice (debit)
		running_balance = flt(running_balance + inv_amount)

		# Add invoice row
		row = {
			'customer': customer,
			'customer_name': customer_name,
			'sales_invoice': inv_name,
			'invoice_date': inv_date,
			'invoice_amount': inv_amount,
			'allocation_amount': None,
			'balance': inv_remaining,
			'collection_amount': None,
			'voucher_no': inv_name,
			'voucher_type': 'Sales Invoice',
			'voucher_date': inv_date,
			'voucher_amount': inv_amount,
			'debit': inv_amount,
			'credit': None,
			'running_balance': running_balance,
			'opening_credit_balance': None,
			'days': None,
		}
		data.append(row)

		# Allocate credits against this invoice until cleared
		while inv_remaining > 0 and credit_idx < len(credit_queue):
			credit = credit_queue[credit_idx]

			if credit['remaining'] <= 0:
				credit_idx += 1
				continue

			# Allocation amount
			allocation = min(inv_remaining, credit['remaining'])
			inv_remaining = flt(inv_remaining - allocation)
			credit['remaining'] = flt(credit['remaining'] - allocation)

			# Update running balance for credit
			running_balance = flt(running_balance - allocation)

			# Days between invoice and payment
			days = date_diff(credit['date'], inv_date) if credit['date'] and inv_date else None

			# Add allocation row
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': inv_name,
				'invoice_date': inv_date,
				'invoice_amount': None,
				'allocation_amount': allocation,
				'balance': inv_remaining,
				'collection_amount': credit['amount'],
				'voucher_no': credit['name'],
				'voucher_type': credit['voucher_type'],
				'voucher_date': credit['date'],
				'voucher_amount': credit['amount'],
				'debit': None,
				'credit': allocation,
				'running_balance': running_balance,
				'opening_credit_balance': None,
				'days': days,
			}
			data.append(row)

			# Move to next credit if fully used
			if credit['remaining'] <= 0:
				credit_idx += 1

	# Handle any remaining unallocated credits
	while credit_idx < len(credit_queue):
		credit = credit_queue[credit_idx]
		if credit['remaining'] > 0:
			running_balance = flt(running_balance - credit['remaining'])
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': 'Unallocated',
				'invoice_date': None,
				'invoice_amount': None,
				'allocation_amount': credit['remaining'],
				'balance': None,
				'collection_amount': credit['amount'],
				'voucher_no': credit['name'],
				'voucher_type': credit['voucher_type'],
				'voucher_date': credit['date'],
				'voucher_amount': credit['amount'],
				'debit': None,
				'credit': credit['remaining'],
				'running_balance': running_balance,
				'opening_credit_balance': None,
				'days': None,
			}
			data.append(row)
		credit_idx += 1

	return data
