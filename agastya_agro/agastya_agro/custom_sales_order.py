
import frappe
from frappe import _, msgprint
from frappe.model.document import Document
from datetime import date
from frappe.utils.data import add_to_date, flt

def custom_validate(self,method):
    
    price_nrv=[]
    for doc in self.items:

        nrv = frappe.db.get_value("Item Price",{"price_list":self.selling_price_list,
        'valid_from':["<=",self.transaction_date],
        "valid_upto":[">=",self.transaction_date],"item_code":doc.item_code},["nrv"])
        
        st = frappe.db.get_value("Item Price",{"price_list":self.selling_price_list,
        'valid_from':["<=",self.transaction_date],
        "valid_upto":[">=",self.transaction_date],"item_code":doc.item_code},["stock_transfer"])
        
        if nrv:

            doc.nrv = nrv
            frappe.db.set_value("Sales Order Item",doc.name,"nrv",nrv)
            price_nrv.append(flt(nrv) * flt(doc.qty))
            
        if st:
            doc.stock_transfer = st
            frappe.db.set_value("Sales Order Item",doc.name,"stock_transfer",st)
    
        if (doc.rate) < (doc.nrv) and doc.stock_transfer == 0:
            msg = "The price of the item {0} is less than {1}, Please correct it or contact the Administrator".format(doc.item_code,doc.nrv)
            frappe.throw(msg)
    print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",price_nrv)
    if sum(price_nrv) > self.grand_total:
        frappe.throw("Grand total of sales order is less than NRV price")
        
    
        
