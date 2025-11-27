frappe.ui.form.on("Purchase Receipt",{
    onload_post_render:async function(frm){
        if(frm.doc.supplier_delivery_note && frm.is_new()){
            const dn_doc = await frappe.get_doc("Delivery Note",frm.doc.supplier_delivery_note)            
            frm.doc.supplier_address = dn_doc.company_address
            frm.doc.billing_address = dn_doc.customer_address
        }
    }
})