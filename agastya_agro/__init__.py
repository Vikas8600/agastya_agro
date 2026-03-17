
__version__ = '0.0.1'

try:
	import erpnext.accounts.report.general_ledger.general_ledger as gl_module
	from agastya_agro.overrides.general_ledger import custom_execute

	gl_module.execute = custom_execute
except ImportError:
	pass

