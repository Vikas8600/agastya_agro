# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	"""
	Columns matching the client's format:
	Sales Invoice | Date | Amount | Allocation Amount | Balance | Collection Amount | (gap) | Voucher No | Voucher Type | Date | Amount
	"""
	columns = [
		{'label': 'Customer', 'fieldname': 'customer', 'fieldtype': 'Link', 'options': 'Customer', 'width': 100},
		{'label': 'Customer Name', 'fieldname': 'customer_name', 'fieldtype': 'Data', 'width': 150},
		{'label': 'Sales Invoice', 'fieldname': 'sales_invoice', 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 140},
		{'label': 'Date', 'fieldname': 'invoice_date', 'fieldtype': 'Date', 'width': 100},
		{'label': 'Amount', 'fieldname': 'invoice_amount', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Allocation Amount', 'fieldname': 'allocation_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Collection Amount', 'fieldname': 'collection_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': '', 'fieldname': 'blank', 'fieldtype': 'Data', 'width': 30},
		{'label': 'Voucher No', 'fieldname': 'voucher_no', 'fieldtype': 'Dynamic Link', 'options': 'voucher_type', 'width': 150},
		{'label': 'Voucher Type', 'fieldname': 'voucher_type', 'fieldtype': 'Data', 'width': 120},
		{'label': 'Voucher Date', 'fieldname': 'voucher_date', 'fieldtype': 'Date', 'width': 100},
		{'label': 'Voucher Amount', 'fieldname': 'voucher_amount', 'fieldtype': 'Currency', 'width': 120},
	]
	return columns

def get_data(filters):
	"""
	FIFO Payment Reconciliation using GL Entry data

	Logic:
	1. Get opening balance for the customer before the from_date
	   - Positive = customer owes money (debit balance)
	   - Negative = customer has advance/credit balance
	2. Get all GL entries (debits = invoices, credits = payments) within date range
	3. Allocate credits (payments) against debits (invoices) in FIFO order by date
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
	# Positive = Debit balance (customer owes)
	# Negative = Credit balance (advance payment)
	# =========================================================================
	opening_balance = get_opening_balance(customer, company, f_date)

	# =========================================================================
	# STEP 2: Get all Sales Invoices (Debits) - sorted by date FIFO
	# =========================================================================
	invoices = get_invoices(customer, company, f_date, t_date)

	# =========================================================================
	# STEP 3: Get all Payments/Credits (Payment Entries + Journal Entries)
	# =========================================================================
	payments = get_payments(customer, company, f_date, t_date)

	# =========================================================================
	# STEP 4: FIFO Allocation
	# =========================================================================
	data = allocate_fifo(customer, customer_name, opening_balance, invoices, payments, f_date)

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
	Includes: Payment Entry, Journal Entry (non-system-generated)
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

	# Filter out system-generated Journal Entries
	filtered_payments = []
	for pmt in payments:
		if pmt['voucher_type'] == 'Journal Entry':
			is_system_generated = frappe.get_cached_value("Journal Entry", pmt['name'], "is_system_generated")
			if is_system_generated:
				continue
		pmt['remaining'] = flt(pmt['amount'])
		filtered_payments.append(pmt)

	return filtered_payments


def allocate_fifo(customer, customer_name, opening_balance, invoices, payments, f_date):
	"""
	Allocate payments against invoices in FIFO order

	Logic:
	1. If opening balance is positive (customer owes), first allocate payments against it
	2. If opening balance is negative (advance), treat it as available credit for invoices
	3. Then allocate remaining payments against invoices in date order
	"""
	data = []
	payment_idx = 0

	# Track available credit from opening balance (if negative)
	available_credit = abs(opening_balance) if opening_balance < 0 else 0

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
				'blank': '',
				'voucher_no': pmt['name'],
				'voucher_type': pmt['voucher_type'],
				'voucher_date': pmt['date'],
				'voucher_amount': pmt['amount'],
			}
			data.append(row)
			first_opening_row = False

			# Move to next payment if exhausted
			if pmt['remaining'] <= 0:
				payment_idx += 1

		# If opening balance still has remaining (not fully paid)
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
				'blank': '',
				'voucher_no': '',
				'voucher_type': '',
				'voucher_date': None,
				'voucher_amount': 0,
			}
			data.append(row)

	# =========================================================================
	# Allocate against Invoices in FIFO order
	# =========================================================================
	for inv in invoices:
		inv_remaining = inv['remaining']
		first_invoice_row = True

		# First, use available credit from negative opening balance
		if available_credit > 0 and inv_remaining > 0:
			allocation = min(inv_remaining, available_credit)
			inv_remaining = flt(inv_remaining - allocation)
			available_credit = flt(available_credit - allocation)

			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': inv['name'],
				'invoice_date': inv['date'],
				'invoice_amount': inv['amount'],
				'allocation_amount': allocation,
				'balance': inv_remaining,
				'collection_amount': abs(opening_balance),  # Show original credit balance
				'blank': '',
				'voucher_no': 'Opening Credit',
				'voucher_type': 'Opening Balance',
				'voucher_date': f_date,
				'voucher_amount': abs(opening_balance),
			}
			data.append(row)
			first_invoice_row = False

		# Then allocate from payments while invoice has remaining balance
		while inv_remaining > 0 and payment_idx < len(payments):
			pmt = payments[payment_idx]

			if pmt['remaining'] <= 0:
				payment_idx += 1
				continue

			# Calculate allocation
			allocation = min(inv_remaining, pmt['remaining'])
			inv_remaining = flt(inv_remaining - allocation)
			pmt['remaining'] = flt(pmt['remaining'] - allocation)

			# Determine balance to show:
			# If invoice has remaining -> show invoice remaining
			# If invoice is fully paid but payment has remaining -> show payment remaining (negative to indicate credit)
			if inv_remaining > 0:
				balance_to_show = inv_remaining
			elif pmt['remaining'] > 0:
				balance_to_show = -pmt['remaining']  # Negative indicates payment has excess
			else:
				balance_to_show = 0

			# Add row
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': inv['name'] if first_invoice_row else '',
				'invoice_date': inv['date'] if first_invoice_row else None,
				'invoice_amount': inv['amount'] if first_invoice_row else None,
				'allocation_amount': allocation,
				'balance': balance_to_show,
				'collection_amount': pmt['amount'],
				'blank': '',
				'voucher_no': pmt['name'],
				'voucher_type': pmt['voucher_type'],
				'voucher_date': pmt['date'],
				'voucher_amount': pmt['amount'],
			}
			data.append(row)
			first_invoice_row = False

			# Move to next payment if exhausted
			if pmt['remaining'] <= 0:
				payment_idx += 1

		# If invoice has no allocation at all (unpaid), show it
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
				'blank': '',
				'voucher_no': '',
				'voucher_type': '',
				'voucher_date': None,
				'voucher_amount': 0,
			}
			data.append(row)

	# =========================================================================
	# Show remaining unallocated payments (adds to closing credit)
	# =========================================================================
	for pmt in payments:
		if pmt['remaining'] > 0:
			row = {
				'customer': customer,
				'customer_name': customer_name,
				'sales_invoice': 'Unallocated Payment',
				'invoice_date': None,
				'invoice_amount': None,
				'allocation_amount': 0,
				'balance': None,
				'collection_amount': pmt['amount'],
				'blank': '',
				'voucher_no': pmt['name'],
				'voucher_type': pmt['voucher_type'],
				'voucher_date': pmt['date'],
				'voucher_amount': pmt['amount'],
			}
			data.append(row)

	return data
