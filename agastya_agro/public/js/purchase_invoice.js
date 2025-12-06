
// frappe.ui.form.on("Purchase Invoice",{
//     onload_post_render:async function(frm){
//         console.log(frm.doc.items[0].purchase_receipt);
//         if(frm.doc.custom_sales_invoice){

//             const customer_result = await frappe.db.get_value("Customer", {
//                 "custom_supplier": frm.doc.supplier,
//                 "custom_is_internal_transfer": 1
//             }, "name")
//             const is_internal_stock_transfer = customer_result.message && customer_result.message.name
//             console.log(is_internal_stock_transfer)

//             if(frm.doc.items[0].purchase_receipt && frm.is_new() && is_internal_stock_transfer){
//                 const pr_doc = await frappe.db.get_value("Purchase Receipt",frm.doc.items[0].purchase_receipt,["supplier_address","billing_address"])

//                 frm.set_value("supplier_address", pr_doc.message.supplier_address)
//                 frm.set_value("billing_address", pr_doc.message.billing_address)
//                 frm.set_value("write_off_amount",frm.doc.rounded_total)
//                 frm.set_value("write_off_account","Stock Transfer Write Off - AAL")
//                 frm.set_value("write_off_cost_center",frm.doc.cost_center)

//             }
//         }
//     },
//     before_save:async function(frm){
//         if(frm.doc.custom_sales_invoice){

//             const customer_result = await frappe.db.get_value("Customer", {
//                 "custom_supplier": frm.doc.supplier,
//                 "custom_is_internal_transfer": 1
//             }, "name")
//             const is_internal_stock_transfer = customer_result.message && customer_result.message.name

//             if(frm.doc.items[0].purchase_receipt && frm.is_new() && is_internal_stock_transfer){
//                 const pr_doc = await frappe.db.get_value("Purchase Receipt",frm.doc.items[0].purchase_receipt,["supplier_address","billing_address"])

//                 frm.set_value("supplier_address", pr_doc.message.supplier_address)
//                 frm.set_value("billing_address", pr_doc.message.billing_address)
//                 frm.set_value("write_off_amount",frm.doc.rounded_total)
//                 frm.set_value("write_off_account","Stock Transfer Write Off - AAL")
//                 frm.set_value("write_off_cost_center",frm.doc.cost_center)

//             }
//         }
//     }
// })