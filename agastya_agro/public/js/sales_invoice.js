
frappe.ui.form.on('Sales Invoice', {
    refresh: async function(frm) {
        if (frm.doc.docstatus !== 1) return;
        const is_internal_transfer = (await frappe.db.get_value("Customer", frm.doc.customer, "custom_is_internal_transfer")).message.custom_is_internal_transfer;
        
        if (is_internal_transfer) {
        frm.add_custom_button(__('Internal Purchase Invoice'), async function() {
            let delivery_note_name = frm.doc.items?.[0]?.delivery_note;

            if (!delivery_note_name) {
                frappe.msgprint("No Delivery Note found in Sales Invoice.");
                return;
            }

            const { message: pr_list } = await frappe.call({
                method: "agastya_agro.public.py.sales_invoice.get_all_pr_from_dn",
                args: { delivery_note: delivery_note_name }
            });

            if (!pr_list || pr_list.length === 0) {
                frappe.msgprint("No Purchase Receipts found for this Delivery Note.");
                return;
            }

            const { message: pr_data } = await frappe.call({
                method: "agastya_agro.public.py.sales_invoice.get_remaining_pr_items",
                args: {
                    pr_list,
                    sales_invoice: frm.doc.name
                }
            });

            if (!pr_data || pr_data.items.length === 0) {
                frappe.msgprint("All quantities already invoiced. Nothing remaining.");
                return;
            }

            frappe.model.with_doctype("Purchase Invoice", () => {

                let pi_doc = frappe.model.get_new_doc("Purchase Invoice");

                pi_doc.company = pr_data.company;
                pi_doc.supplier = pr_data.supplier;
                pi_doc.posting_date = frappe.datetime.get_today();
                pi_doc.cost_center = pr_data.cost_center
                pi_doc.supplier_address = pr_data.supplier_address
                pi_doc.billing_address =  pr_data.billing_address
                // Link sales invoice on parent level
                pi_doc.custom_sales_invoice = frm.doc.name;

                // Add Items
                pr_data.items.forEach(row => {
                    let child = frappe.model.add_child(pi_doc, "Purchase Invoice Item", "items");

                    child.item_code = row.item_code;
                    child.item_name = row.item_name;
                    child.description = row.description;
                    child.qty = row.remaining_qty;
                    child.uom = row.uom;
                    child.rate = row.rate;
                    child.warehouse = row.warehouse;

                    // Link PR
                    child.purchase_receipt = row.pr_name;

                    // Link Sales Invoice Item row for remaining qty logic
                    child.custom_sales_invoice_detail = row.sales_invoice_item;
                });

                frappe.set_route("Form", pi_doc.doctype, pi_doc.name);
            });

        }, __("Create"));
    }
    },
    onload_post_render: async function(frm){
        if(frm.doc.customer && frm.is_new()){  
            const is_internal_transfer = (await frappe.db.get_value("Customer", frm.doc.customer, "custom_is_internal_transfer")).message.custom_is_internal_transfer;
            if(is_internal_transfer){

                frm.set_value("write_off_amount",frm.doc.rounded_total)
                frm.set_value("write_off_account","Stock Transfer Write Off - AAL")
                frm.set_value("write_off_cost_center",frm.doc.cost_center)
            }
        }
    },
    customer: async function(frm){
        if(frm.doc.customer && frm.is_new()){  
            const is_internal_transfer = (await frappe.db.get_value("Customer", frm.doc.customer, "custom_is_internal_transfer")).message.custom_is_internal_transfer;
            if(is_internal_transfer){
                frm.set_value("write_off_amount",frm.doc.rounded_total)
                frm.set_value("write_off_account","Stock Transfer Write Off - AAL")
                frm.set_value("write_off_cost_center",frm.doc.cost_center)
            }
        }
    },
    before_save: async function(frm){
        if(frm.doc.customer && frm.is_new()){  
            const is_internal_transfer = (await frappe.db.get_value("Customer", frm.doc.customer, "custom_is_internal_transfer")).message.custom_is_internal_transfer;
            if(is_internal_transfer){
                frm.set_value("write_off_amount",frm.doc.rounded_total)
                frm.set_value("write_off_account","Stock Transfer Write Off - AAL")
                frm.set_value("write_off_cost_center",frm.doc.cost_center)
            }
        }
    }
});



// frappe.ui.form.on('Sales Invoice', {
//     refresh: function(frm) {
//         if (frm.doc.docstatus === 1) {
//             frm.add_custom_button(__('Internal Purchase Invoice'), async function() {
//                 let delivery_note_name = null;

//                if (frm.doc.items && frm.doc.items.length > 0 && frm.doc.items[0].delivery_note) {
//                     delivery_note_name = frm.doc.items[0].delivery_note;
//                 }

//                 if (!delivery_note_name) {
//                     frappe.msgprint(__('No linked Delivery Note found in this Sales Invoice.'));
//                     return;
//                 }

//                 let grn_name = null;
//                 await frappe.call({
//                     method: "frappe.client.get_list",
//                     args: {
//                         doctype: "Purchase Receipt",
//                         filters: { custom_delivery_note: delivery_note_name },
//                         fields: ["name"],
//                         limit_page_length: 1
//                     },
//                     async: false,
//                     callback: function(r) {
//                         if (r.message && r.message.length > 0) {
//                             grn_name = r.message[0].name;
//                         }
//                     }
//                 });

//                 if (!grn_name) {
//                     frappe.msgprint(__('No Purchase Receipt (GRN) found linked to Delivery Note ') + delivery_note_name);
//                     return;
//                 }

//                 // Call server to make Purchase Invoice from Purchase Receipt and open it
//                 frappe.call({
//                     method: "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice",
//                     args: {
//                         source_name: grn_name
//                     },
//                     callback: function(r) {
//                         if (r.message) {
//                             let doc = frappe.model.sync(r.message)[0];
//                             frappe.set_route('Form', doc.doctype, doc.name);
//                         }
//                     }
//                 });
//             }, __('Create'));
//         }
//     }
// });
