import frappe

INDEX_NAME = "party_balance_index"

# Every column the party balance aggregation reads, so it can be answered from
# the index alone. Equality columns lead, then party so the grouping needs no
# sort, then the date range and the summed amounts.
INDEX_FIELDS = [
	"party_type",
	"company",
	"is_cancelled",
	"party",
	"posting_date",
	"debit",
	"credit",
]


def execute():
	"""Index the ledger for per-party balances.

	Customer Ageing Report and Trial Balance for Party both sum debit and credit
	per party across the whole ledger. Without every column in one index each of
	the millions of matching rows is fetched from the table just to read two
	amounts, which costs minutes; covered by an index the same scan takes
	seconds.
	"""
	frappe.db.add_index("GL Entry", INDEX_FIELDS, INDEX_NAME)
