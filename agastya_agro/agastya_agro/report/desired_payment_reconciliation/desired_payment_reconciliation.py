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
	Previous structure with Debit/Credit columns added for GL matching
	"""
	columns = [
		{'label': 'Customer', 'fieldname': 'customer', 'fieldtype': 'Link', 'options': 'Customer', 'width': 100},
		{'label': 'Customer Name', 'fieldname': 'customer_name', 'fieldtype': 'Data', 'width': 150},
		{'label': 'Sales Invoice', 'fieldname': 'sales_invoice', 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 140},
		{'label': 'Date', 'fieldname': 'invoice_date', 'fieldtype': 'Date', 'width': 100},
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
	FIFO Payment Reconciliation using GL Entry data

	Logic:
	1. Get opening balance for the customer before the from_date
	2. Get all Sales Invoices (Debits) - sorted by date FIFO
	3. Get all Payments/Credits (Payment Entries + Journal Entries)
	4. Get all JV Debit entries separately
	5. Allocate credits (payments) against debits (invoices) in FIFO order by date
	6. Show Debit/Credit columns like GL for easy matching
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
	# STEP 2: Get all Sales Invoices (Debits) - sorted by date FIFO
	# =========================================================================
	invoices = get_invoices(customer, company, f_date, t_date)

	# =========================================================================
	# STEP 3: Get all Payments/Credits (Payment Entries + Journal Entries with credit)
	# =========================================================================
	payments = get_payments(customer, company, f_date, t_date)

	# =========================================================================
	# STEP 4: Get all JV Debit entries (these increase receivable)
	# =========================================================================
	jv_debits = get_jv_debits(customer, company, f_date, t_date)

	# =========================================================================
	# STEP 5: FIFO Allocation with Debit/Credit columns
	# =========================================================================
	data = allocate_fifo(customer, customer_name, opening_balance, invoices, payments, jv_debits, f_date)

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


def get_invoices(customer, company, f_date, t_date):
	"""
	Get all Sales Invoices (debit entries) for the customer
	Returns list of invoices sorted by date (FIFO)
	"""
	conditions = """
		WHERE gl.party_type = 'Customer'
		AND gl.party = %s
		AND gl.company = %s
		AND gl.debit > 0
		AND gl.is_cancelled = 0
		AND gl.voucher_type = 'Sales Invoice'
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
		ORDER BY gl.posting_date ASC, gl.voucher_no ASC
	""".format(conditions=conditions), params, as_dict=True)

	# Add remaining balance to each invoice
	for inv in invoices:
		inv['remaining'] = flt(inv['amount'])

	return invoices


def get_payments(customer, company, f_date, t_date):
	"""
	Get all Payments (credit entries) for the customer
	Includes: Payment Entry, Journal Entry with credit
	Returns list of payments sorted by date (FIFO)
	"""
	conditions = """
		WHERE gl.party_type = 'Customer'
		AND gl.party = %s
		AND gl.company = %s
		AND gl.credit > 0
		AND gl.is_cancelled = 0
		AND gl.voucher_type IN ('Payment Entry', 'Journal Entry')
	"""
	params = [customer, company]

	if f_date and t_date:
		conditions += " AND gl.posting_date BETWEEN %s AND %s"
		params.extend([f_date, t_date])

	payments = frappe.db.sql("""
		SELECT
			gl.voucher_no as name,
			gl.posting_date as date,
			gl.credit as amount,
			gl.voucher_type,
			gl.against as against_account
		FROM `tabGL Entry` gl
		{conditions}
		ORDER BY gl.posting_date ASC, gl.voucher_no ASC
	""".format(conditions=conditions), params, as_dict=True)

	# Add remaining balance to each payment
	for pmt in payments:
		pmt['remaining'] = flt(pmt['amount'])

	return payments


def get_jv_debits(customer, company, f_date, t_date):
	"""
	Get all Journal Entry debit entries for the customer
	These increase what customer owes (like additional charges, reversals)
	Returns list sorted by date
	"""
	conditions = """
		WHERE gl.party_type = 'Customer'
		AND gl.party = %s
		AND gl.company = %s
		AND gl.debit > 0
		AND gl.is_cancelled = 0
		AND gl.voucher_type = 'Journal Entry'
	"""
	params = [customer, company]

	if f_date and t_date:
		conditions += " AND gl.posting_date BETWEEN %s AND %s"
		params.extend([f_date, t_date])

	jv_debits = frappe.db.sql("""
		SELECT
			gl.voucher_no as name,
			gl.posting_date as date,
			gl.debit as amount,
			gl.voucher_type
		FROM `tabGL Entry` gl
		{conditions}
		ORDER BY gl.posting_date ASC, gl.voucher_no ASC
	""".format(conditions=conditions), params, as_dict=True)

	return jv_debits


def allocate_fifo(customer, customer_name, opening_balance, invoices, payments, jv_debits, f_date):
	"""
	Allocate payments against invoices in FIFO order
	Shows Debit/Credit columns like GL for easy matching

	Running Balance = Opening + Sum(Debits) - Sum(Credits)
	- Debits (Sales Invoice, JV Debit) increase running balance
	- Credits (Payment Entry, JV Credit) decrease running balance
	"""
	data = []
	payment_idx = 0
	jv_debit_idx = 0
	running_balance = opening_balance

	# Track which payments have been added to running_balance (to avoid double counting)
	payments_added_to_balance = set()

	# Track available credit from opening balance (if negative)
	available_credit = abs(opening_balance) if opening_balance < 0 else 0
	original_opening_credit = available_credit

	# =========================================================================
	# Handle Positive Opening Balance (Customer owes money from before)
	# =========================================================================
	if opening_balance > 0:
		opening_remaining = opening_balance
		first_opening_row = True

		while opening_remaining > 0 and payment_idx < len(payments):
			pmt = payments[payment_idx]

			if pmt['remaining'] <= 0:
				payment_idx += 1
				continue

			# Calculate allocation
			allocation = min(opening_remaining, pmt['remaining'])
			opening_remaining = flt(opening_remaining - allocation)
			pmt['remaining'] = flt(pmt['remaining'] - allocation)

			# Update running balance with FULL credit amount (only once per payment)
			if pmt['name'] not in payments_added_to_balance:
				running_balance = flt(running_balance - pmt['amount'])
				payments_added_to_balance.add(pmt['name'])

			# Calculate days
			days = date_diff(pmt['date'], f_date) if f_date and pmt['date'] else None

			# Add row
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': 'Opening Balance' if first_opening_row else '',
				'invoice_date': f_date if first_opening_row else None,
				'invoice_amount': opening_balance if first_opening_row else None,
				'allocation_amount': allocation,
				'balance': opening_remaining,
				'collection_amount': pmt['amount'],
				'voucher_no': pmt['name'],
				'voucher_type': pmt['voucher_type'],
				'voucher_date': pmt['date'],
				'voucher_amount': pmt['amount'],
				'debit': None,
				'credit': pmt['amount'],
				'running_balance': running_balance,
				'opening_credit_balance': None,
				'days': days,
			}
			data.append(row)
			first_opening_row = False

			if pmt['remaining'] <= 0:
				payment_idx += 1

		# If opening balance still has remaining
		if opening_remaining > 0 and first_opening_row:
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': 'Opening Balance',
				'invoice_date': f_date,
				'invoice_amount': opening_balance,
				'allocation_amount': 0,
				'balance': opening_remaining,
				'collection_amount': 0,
				'voucher_no': '',
				'voucher_type': '',
				'voucher_date': None,
				'voucher_amount': 0,
				'debit': opening_balance,
				'credit': None,
				'running_balance': running_balance,
				'opening_credit_balance': None,
				'days': None,
			}
			data.append(row)

	# =========================================================================
	# Allocate against Invoices in FIFO order
	# =========================================================================
	# Track which invoices have been added to running_balance
	invoices_added_to_balance = set()

	for inv in invoices:
		inv_remaining = inv['remaining']
		first_invoice_row = True

		# Add invoice debit to running balance (only once)
		if inv['name'] not in invoices_added_to_balance:
			running_balance = flt(running_balance + inv['amount'])
			invoices_added_to_balance.add(inv['name'])

		# Check for JV debits that occurred on or before this invoice date
		while jv_debit_idx < len(jv_debits):
			jv = jv_debits[jv_debit_idx]
			if jv['date'] <= inv['date']:
				# Show JV debit entry
				running_balance = flt(running_balance + jv['amount'])
				row = {
					'customer': customer,
					'customer_name': customer_name,
					'sales_invoice': '',
					'invoice_date': None,
					'invoice_amount': None,
					'allocation_amount': None,
					'balance': None,
					'collection_amount': None,
					'voucher_no': jv['name'],
					'voucher_type': jv['voucher_type'],
					'voucher_date': jv['date'],
					'voucher_amount': jv['amount'],
					'debit': jv['amount'],
					'credit': None,
					'running_balance': running_balance,
					'opening_credit_balance': None,
					'days': None,
				}
				data.append(row)
				jv_debit_idx += 1
			else:
				break

		# First, use available credit from negative opening balance
		if available_credit > 0 and inv_remaining > 0:
			allocation = min(inv_remaining, available_credit)
			inv_remaining = flt(inv_remaining - allocation)
			available_credit = flt(available_credit - allocation)

			days = date_diff(f_date, inv['date']) if f_date and inv['date'] else None

			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': inv['name'],
				'invoice_date': inv['date'],
				'invoice_amount': inv['amount'],
				'allocation_amount': allocation,
				'balance': inv_remaining,
				'collection_amount': original_opening_credit,
				'voucher_no': 'Opening Credit',
				'voucher_type': 'Opening Balance',
				'voucher_date': f_date,
				'voucher_amount': original_opening_credit,
				'debit': inv['amount'],
				'credit': allocation,
				'running_balance': running_balance,
				'opening_credit_balance': available_credit,
				'days': days,
			}
			data.append(row)
			first_invoice_row = False

		# Then allocate from payments
		while inv_remaining > 0 and payment_idx < len(payments):
			pmt = payments[payment_idx]

			if pmt['remaining'] <= 0:
				payment_idx += 1
				continue

			# Check for JV debits between current position and payment date
			while jv_debit_idx < len(jv_debits):
				jv = jv_debits[jv_debit_idx]
				if jv['date'] <= pmt['date']:
					running_balance = flt(running_balance + jv['amount'])
					row = {
						'customer': customer,
						'customer_name': customer_name,
						'sales_invoice': '',
						'invoice_date': None,
						'invoice_amount': None,
						'allocation_amount': None,
						'balance': None,
						'collection_amount': None,
						'voucher_no': jv['name'],
						'voucher_type': jv['voucher_type'],
						'voucher_date': jv['date'],
						'voucher_amount': jv['amount'],
						'debit': jv['amount'],
						'credit': None,
						'running_balance': running_balance,
						'opening_credit_balance': None,
						'days': None,
					}
					data.append(row)
					jv_debit_idx += 1
				else:
					break

			# Calculate allocation
			allocation = min(inv_remaining, pmt['remaining'])
			inv_remaining = flt(inv_remaining - allocation)
			pmt['remaining'] = flt(pmt['remaining'] - allocation)

			# Update running balance with FULL credit amount (only once per payment)
			if pmt['name'] not in payments_added_to_balance:
				running_balance = flt(running_balance - pmt['amount'])
				payments_added_to_balance.add(pmt['name'])

			if inv_remaining > 0:
				balance_to_show = inv_remaining
			elif pmt['remaining'] > 0:
				balance_to_show = -pmt['remaining']
			else:
				balance_to_show = 0

			days = date_diff(pmt['date'], inv['date']) if pmt['date'] and inv['date'] else None

			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': inv['name'] if first_invoice_row else '',
				'invoice_date': inv['date'] if first_invoice_row else None,
				'invoice_amount': inv['amount'] if first_invoice_row else None,
				'allocation_amount': allocation,
				'balance': balance_to_show,
				'collection_amount': pmt['amount'],
				'voucher_no': pmt['name'],
				'voucher_type': pmt['voucher_type'],
				'voucher_date': pmt['date'],
				'voucher_amount': pmt['amount'],
				'debit': inv['amount'] if first_invoice_row else None,
				'credit': pmt['amount'],
				'running_balance': running_balance,
				'opening_credit_balance': available_credit if original_opening_credit > 0 else None,
				'days': days,
			}
			data.append(row)
			first_invoice_row = False

			if pmt['remaining'] <= 0:
				payment_idx += 1

		# If invoice has no allocation at all (unpaid)
		if first_invoice_row:
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': inv['name'],
				'invoice_date': inv['date'],
				'invoice_amount': inv['amount'],
				'allocation_amount': 0,
				'balance': inv['amount'],
				'collection_amount': 0,
				'voucher_no': '',
				'voucher_type': '',
				'voucher_date': None,
				'voucher_amount': 0,
				'debit': inv['amount'],
				'credit': None,
				'running_balance': running_balance,
				'opening_credit_balance': available_credit if original_opening_credit > 0 else None,
				'days': None,
			}
			data.append(row)

	# =========================================================================
	# Show remaining JV debits
	# =========================================================================
	while jv_debit_idx < len(jv_debits):
		jv = jv_debits[jv_debit_idx]
		running_balance = flt(running_balance + jv['amount'])
		row = {
			'customer': customer,
			'customer_name': customer_name,
			'sales_invoice': '',
			'invoice_date': None,
			'invoice_amount': None,
			'allocation_amount': None,
			'balance': None,
			'collection_amount': None,
			'voucher_no': jv['name'],
			'voucher_type': jv['voucher_type'],
			'voucher_date': jv['date'],
			'voucher_amount': jv['amount'],
			'debit': jv['amount'],
			'credit': None,
			'running_balance': running_balance,
			'opening_credit_balance': None,
			'days': None,
		}
		data.append(row)
		jv_debit_idx += 1

	# =========================================================================
	# Show remaining unallocated payments (those not yet added to running_balance)
	# =========================================================================
	for pmt in payments:
		if pmt['remaining'] > 0 and pmt['name'] not in payments_added_to_balance:
			# This payment was never used, subtract full amount
			running_balance = flt(running_balance - pmt['amount'])
			payments_added_to_balance.add(pmt['name'])
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': 'Unallocated Payment',
				'invoice_date': None,
				'invoice_amount': None,
				'allocation_amount': 0,
				'balance': None,
				'collection_amount': pmt['amount'],
				'voucher_no': pmt['name'],
				'voucher_type': pmt['voucher_type'],
				'voucher_date': pmt['date'],
				'voucher_amount': pmt['amount'],
				'debit': None,
				'credit': pmt['amount'],
				'running_balance': running_balance,
				'opening_credit_balance': available_credit if original_opening_credit > 0 else None,
				'days': None,
			}
			data.append(row)

	return data
