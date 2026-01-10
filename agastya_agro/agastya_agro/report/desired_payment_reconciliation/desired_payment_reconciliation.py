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
		{'label': 'Invoice Amount', 'fieldname': 'invoice_amount', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Allocation Amount', 'fieldname': 'allocation_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Invoice Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Collection Balance', 'fieldname': 'collection_balance', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Collection Amount', 'fieldname': 'collection_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Voucher No', 'fieldname': 'voucher_no', 'fieldtype': 'Dynamic Link', 'options': 'voucher_type', 'width': 150},
		{'label': 'Voucher Type', 'fieldname': 'voucher_type', 'fieldtype': 'Data', 'width': 120},
		{'label': 'Voucher Date', 'fieldname': 'voucher_date', 'fieldtype': 'Date', 'width': 100},
		# {'label': 'Voucher Amount', 'fieldname': 'voucher_amount', 'fieldtype': 'Currency', 'width': 120},  # Same as Collection Amount
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
	Supports multiple customers with partition rows between them
	"""
	data = []
	customer_filter = filters.get("customer")
	f_date = filters.get("f_date")
	t_date = filters.get("t_date")
	company = filters.get("company")

	if not company:
		return data

	# Parse customer filter - can be single customer or comma-separated list
	customers = []
	if customer_filter:
		if isinstance(customer_filter, list):
			customers = customer_filter
		elif isinstance(customer_filter, str):
			# Handle comma-separated string from MultiSelectLink
			customers = [c.strip() for c in customer_filter.split(',') if c.strip()]
		else:
			customers = [customer_filter]

	if not customers:
		return data

	# Process each customer
	for idx, customer in enumerate(customers):
		customer_name = frappe.get_cached_value("Customer", customer, "customer_name") or customer

		# Get opening balance
		opening_balance = get_opening_balance(customer, company, f_date)

		# Get all receivables (Sales Invoice + JV debits) sorted by date ASC
		receivables = get_receivables(customer, company, f_date, t_date)

		# Get all credit entries (payments, JV credits) sorted by date ASC
		credits = get_credit_entries(customer, company, f_date, t_date)

		# Build report - receivable by receivable with FIFO allocation
		customer_data = build_invoice_centric_report(customer, customer_name, opening_balance, receivables, credits, f_date)

		# Add customer data to main data
		data.extend(customer_data)

		# Add partition row between customers (not after last customer)
		if idx < len(customers) - 1:
			partition_row = {
				'customer': '',
				'customer_name': '',
				'sales_invoice': '─' * 20,  # Visual separator
				'invoice_date': None,
				'invoice_amount': None,
				'allocation_amount': None,
				'balance': None,
				'collection_balance': None,
				'collection_amount': None,
				'voucher_no': '',
				'voucher_type': '',
				'voucher_date': None,
				'voucher_amount': None,
				'debit': None,
				'credit': None,
				'running_balance': None,
				'opening_credit_balance': None,
				'days': None,
			}
			data.append(partition_row)

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


def get_receivables(customer, company, f_date, t_date):
	"""
	Get all debit entries (Sales Invoice + JV debits) sorted by date ASC
	These are all receivables that need payment allocation
	"""
	conditions = """
		WHERE gl.party_type = 'Customer'
		AND gl.party = %s
		AND gl.company = %s
		AND gl.is_cancelled = 0
		AND gl.voucher_type IN ('Sales Invoice', 'Journal Entry')
		AND gl.debit > 0
	"""
	params = [customer, company]

	if f_date and t_date:
		conditions += " AND gl.posting_date BETWEEN %s AND %s"
		params.extend([f_date, t_date])

	receivables = frappe.db.sql("""
		SELECT
			gl.voucher_no as name,
			gl.posting_date as date,
			gl.debit as amount,
			gl.voucher_type
		FROM `tabGL Entry` gl
		{conditions}
		ORDER BY gl.posting_date ASC, gl.creation ASC
	""".format(conditions=conditions), params, as_dict=True)

	return receivables


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
		ORDER BY gl.posting_date ASC, gl.creation ASC
	""".format(conditions=conditions), params, as_dict=True)

	return credits


def build_invoice_centric_report(customer, customer_name, opening_balance, receivables, credits, f_date):
	"""
	Build report showing:
	1. Opening Balance first - allocate credits until cleared
	2. Then Invoices/JV debits in date order - allocate remaining credits

	Running balance is calculated as: Opening + Debits - Credits
	"""
	data = []
	running_balance = flt(opening_balance)

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

	# ===== STEP 1: Clear Opening Balance First =====
	if opening_balance > 0:
		opening_remaining = flt(opening_balance)

		# First row - Opening Balance with first allocation
		first_allocation_done = False

		while opening_remaining > 0 and credit_idx < len(credit_queue):
			credit = credit_queue[credit_idx]

			if credit['remaining'] <= 0:
				credit_idx += 1
				continue

			# Allocation amount
			allocation = min(opening_remaining, credit['remaining'])
			opening_remaining = flt(opening_remaining - allocation)
			credit['remaining'] = flt(credit['remaining'] - allocation)

			# Update running balance for credit
			running_balance = flt(running_balance - allocation)

			# Days from f_date to payment date
			days = date_diff(credit['date'], f_date) if credit['date'] and f_date else None

			# Add allocation row
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': 'Opening Balance' if not first_allocation_done else '',
				'invoice_date': f_date if not first_allocation_done else None,
				'invoice_amount': opening_balance if not first_allocation_done else None,
				'allocation_amount': allocation,
				'balance': opening_remaining,
				'collection_balance': credit['remaining'],
				'collection_amount': credit['amount'],
				'voucher_no': credit['name'],
				'voucher_type': credit['voucher_type'],
				'voucher_date': credit['date'],
				'voucher_amount': credit['amount'],
				'debit': opening_balance if not first_allocation_done else None,
				'credit': allocation,
				'running_balance': running_balance,
				'opening_credit_balance': None,
				'days': days,
			}
			data.append(row)
			first_allocation_done = True

			# Move to next credit if fully used
			if credit['remaining'] <= 0:
				credit_idx += 1

		# If opening balance not fully cleared (no more credits), show remaining
		if opening_remaining > 0 and not first_allocation_done:
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': 'Opening Balance',
				'invoice_date': f_date,
				'invoice_amount': opening_balance,
				'allocation_amount': None,
				'balance': opening_remaining,
				'collection_balance': None,
				'collection_amount': None,
				'voucher_no': '',
				'voucher_type': 'Opening',
				'voucher_date': f_date,
				'voucher_amount': opening_balance,
				'debit': opening_balance,
				'credit': None,
				'running_balance': running_balance,
				'opening_credit_balance': None,
				'days': None,
			}
			data.append(row)

	elif opening_balance < 0:
		# Negative opening balance (credit balance)
		row = {
			'customer': customer,
			'customer_name': customer_name,
			'sales_invoice': 'Opening Balance',
			'invoice_date': f_date,
			'invoice_amount': abs(opening_balance),
			'allocation_amount': None,
			'balance': None,
			'collection_balance': None,
			'collection_amount': None,
			'voucher_no': '',
			'voucher_type': 'Opening',
			'voucher_date': f_date,
			'voucher_amount': abs(opening_balance),
			'debit': None,
			'credit': abs(opening_balance),
			'running_balance': running_balance,
			'opening_credit_balance': None,
			'days': None,
		}
		data.append(row)

	# ===== STEP 2: Process Invoices/JV Debits in Date Order =====
	for receivable in receivables:
		rec_name = receivable['name']
		rec_date = receivable['date']
		rec_amount = flt(receivable['amount'])
		rec_type = receivable['voucher_type']
		rec_remaining = rec_amount

		# For Sales Invoice, show in sales_invoice column
		# For JV debit, sales_invoice column is empty, show in voucher_no
		is_sales_invoice = rec_type == 'Sales Invoice'

		# Update running balance for receivable (debit)
		running_balance = flt(running_balance + rec_amount)

		# Track if first allocation row for this receivable
		first_allocation_done = False

		# For JV debit: First show the debit row, then allocations
		if not is_sales_invoice:
			# JV Debit - Show debit row first with JV in Voucher No column
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': '',  # Empty for JV
				'invoice_date': rec_date,
				'invoice_amount': rec_amount,
				'allocation_amount': None,
				'balance': rec_remaining,
				'collection_balance': None,
				'collection_amount': None,
				'voucher_no': rec_name,  # JV name in Voucher No
				'voucher_type': rec_type,  # Journal Entry
				'voucher_date': rec_date,
				'voucher_amount': rec_amount,
				'debit': rec_amount,
				'credit': None,
				'running_balance': running_balance,
				'opening_credit_balance': None,
				'days': None,
			}
			data.append(row)
			first_allocation_done = True  # Debit row is done

			# Now allocate credits against this JV debit
			while rec_remaining > 0 and credit_idx < len(credit_queue):
				credit = credit_queue[credit_idx]

				if credit['remaining'] <= 0:
					credit_idx += 1
					continue

				allocation = min(rec_remaining, credit['remaining'])
				rec_remaining = flt(rec_remaining - allocation)
				credit['remaining'] = flt(credit['remaining'] - allocation)
				running_balance = flt(running_balance - allocation)

				days = date_diff(credit['date'], rec_date) if credit['date'] and rec_date else None

				row = {
					'customer': customer,
					'customer_name': customer_name,
					'sales_invoice': '',  # Empty for JV allocation rows
					'invoice_date': None,
					'invoice_amount': None,
					'allocation_amount': allocation,
					'balance': rec_remaining,
					'collection_balance': credit['remaining'],
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

				if credit['remaining'] <= 0:
					credit_idx += 1

		else:
			# Sales Invoice - Show SI name in sales_invoice column with allocations
			while rec_remaining > 0 and credit_idx < len(credit_queue):
				credit = credit_queue[credit_idx]

				if credit['remaining'] <= 0:
					credit_idx += 1
					continue

				allocation = min(rec_remaining, credit['remaining'])
				rec_remaining = flt(rec_remaining - allocation)
				credit['remaining'] = flt(credit['remaining'] - allocation)
				running_balance = flt(running_balance - allocation)

				days = date_diff(credit['date'], rec_date) if credit['date'] and rec_date else None

				row = {
					'customer': customer,
					'customer_name': customer_name,
					'sales_invoice': rec_name if not first_allocation_done else '',
					'invoice_date': rec_date if not first_allocation_done else None,
					'invoice_amount': rec_amount if not first_allocation_done else None,
					'allocation_amount': allocation,
					'balance': rec_remaining,
					'collection_balance': credit['remaining'],
					'collection_amount': credit['amount'],
					'voucher_no': credit['name'],
					'voucher_type': credit['voucher_type'],
					'voucher_date': credit['date'],
					'voucher_amount': credit['amount'],
					'debit': rec_amount if not first_allocation_done else None,
					'credit': allocation,
					'running_balance': running_balance,
					'opening_credit_balance': None,
					'days': days,
				}
				data.append(row)
				first_allocation_done = True

				if credit['remaining'] <= 0:
					credit_idx += 1

			# If SI not fully cleared (no more credits), show remaining balance
			if rec_remaining > 0 and not first_allocation_done:
				row = {
					'customer': customer,
					'customer_name': customer_name,
					'sales_invoice': rec_name,
					'invoice_date': rec_date,
					'invoice_amount': rec_amount,
					'allocation_amount': 0,
					'balance': rec_remaining,
					'collection_balance': None,
					'collection_amount': None,
					'voucher_no': '',
					'voucher_type': rec_type,
					'voucher_date': rec_date,
					'voucher_amount': rec_amount,
					'debit': rec_amount,
					'credit': None,
					'running_balance': running_balance,
					'opening_credit_balance': None,
					'days': None,
				}
				data.append(row)

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
				'collection_balance': 0,
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
