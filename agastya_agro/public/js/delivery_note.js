frappe.ui.form.on('Delivery Note', {
    refresh: async function(frm) {
        const is_internal_transfer = (await frappe.db.get_value("Customer", frm.doc.customer, "custom_is_internal_transfer")).message.custom_is_internal_transfer;
        
        if (is_internal_transfer) {
            frm.set_df_property("custom_to_depot_name", "reqd", 1);
            
            if (frm.doc.docstatus === 1) {
                frm.add_custom_button(__('Internal GRN'), async function() {
                    frappe.model.with_doctype('Purchase Receipt', async function() {
                        // Fetch total received qty map from server
                        const { message: received_map } = await frappe.call({
                            method: "agastya_agro.public.py.delivery_note.get_received_qty_map",
                            args: { delivery_note_name: frm.doc.name },
                        });

                        // Create new Purchase Receipt
                        let pr_doc = frappe.model.get_new_doc('Purchase Receipt');
                        const supplier = (await frappe.db.get_value("Customer", frm.doc.customer, "custom_supplier")).message.custom_supplier;

                        pr_doc.custom_delivery_note = frm.doc.name;
                        pr_doc.supplier = supplier;
                        pr_doc.posting_date = frappe.datetime.get_today();
                        pr_doc.company = frm.doc.company;
                        pr_doc.cost_center = frm.doc.custom_to_depot_name;
                        pr_doc.set_warehouse = (await frappe.db.get_value("Cost Center", frm.doc.custom_to_depot_name, "finished_good_warehouse")).message.finished_good_warehouse;
                        pr_doc.supplier_address = frm.doc.company_address
                        pr_doc.billing_address = frm.doc.customer_address
                        let has_remaining_items = false;

                        for (const item of frm.doc.items || []) {
                            const received_qty = flt(received_map?.[item.name] || 0);
                            const remaining_qty = flt(item.qty) - received_qty;

                            if (remaining_qty > 0) {
                                has_remaining_items = true;
                                let pr_item = frappe.model.add_child(pr_doc, 'Purchase Receipt Item', 'items');
                                pr_item.item_code = item.item_code;
                                pr_item.item_name = item.item_name;
                                pr_item.qty = remaining_qty;
                                pr_item.uom = item.uom;
                                pr_item.description = item.description;
                                pr_item.warehouse = item.target_warehouse || item.warehouse;
                                pr_item.batch_no = item.batch_no || '';
                                pr_item.rate = item.rate || 0;
                                pr_item.custom_delivery_note_detail = item.name;
                            }
                        }

                        if (!has_remaining_items) {
                            frappe.msgprint("All items are already received. No remaining quantities to create PR.");
                            return;
                        }

                        frappe.set_route('Form', 'Purchase Receipt', pr_doc.name);
                    });
                }, __('Create'));
            }
        }
    }
});



// frappe.ui.form.on('Delivery Note', {
//     refresh: async function(frm) {
//         const is_internal_transfer = (await frappe.db.get_value("Customer",frm.doc.customer,"custom_is_internal_transfer")).message.custom_is_internal_transfer
//         if(is_internal_transfer){  
//             frm.set_df_property("custom_to_depot_name","reqd",1)
//             if (frm.doc.docstatus === 1 ) {
//                 frm.add_custom_button(__('Internal GRN'), async function() {
//                     frappe.model.with_doctype('Purchase Receipt', async function() {
                       
//                         // Create new Purchase Receipt
//                         let pr_doc = frappe.model.get_new_doc('Purchase Receipt');
//                         const supplier = (await frappe.db.get_value("Customer",frm.doc.customer,"custom_supplier")).message.custom_supplier
//                         pr_doc.custom_delivery_note = frm.doc.name;
//                         pr_doc.supplier = supplier;
//                         pr_doc.posting_date = frappe.datetime.get_today();
//                         pr_doc.company = frm.doc.company;
//                         pr_doc.cost_center = frm.doc.custom_to_depot_name;
//                         pr_doc.set_warehouse = (await frappe.db.get_value("Cost Center",frm.doc.custom_to_depot_name,"finished_good_warehouse")).message.finished_good_warehouse


//                         if (frm.doc.items && frm.doc.items.length > 0) {
//                             frm.doc.items.forEach(item => {

//                                 // Only add items with remaining quantity
//                                 if (remaining_qty > 0) {
//                                     has_remaining_items = true;
//                                     let pr_item = frappe.model.add_child(pr_doc, 'Purchase Receipt Item', 'items');
//                                     pr_item.item_code = item.item_code || '';
//                                     pr_item.item_name = item.item_name || '';
//                                     pr_item.batch_no = ''
//                                     pr_item.qty = remaining_qty;
//                                     pr_item.uom = item.uom || '';
//                                     pr_item.description = item.description || '';
//                                     pr_item.warehouse = item.target_warehouse || item.warehouse || '';
//                                     pr_item.batch_no = item.batch_no || ''
//                                     pr_item.rate = item.rate || ''
//                                     pr_item.custom_delivery_note_details = item.name
//                                 }
//                             });
//                         }


//                         frappe.set_route('Form', 'Purchase Receipt', pr_doc.name);
//                     });
//                 }, __('Create'));
//             }
//         }
//     }
    
// });
