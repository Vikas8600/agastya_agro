# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document
from frappe.utils.data import flt, getdate


class PriceListGenerator(Document):

	def validate(self):
		if getdate(self.start_date)>getdate(self.end_date):
			frappe.throw("End date Cannot be Less than Start date")
		for res in self.price_details:
			pack_g=frappe.db.get_value("Product Pack",{"item":res.item},["diff_price"])
			if res.brand:
				lst=frappe.get_doc("Brand",res.brand)
				for i in lst.brand_defaults:
					if i.selling_cost_center:
						if self.company==i.company and self.cost_center==i.selling_cost_center:
							res.brand_list_price=i.item_price
						if not i.item_price:
							frappe.throw("Please set Item Price in brand")

	def before_save(self):
		self.get_cost_volume()


	def get_cost_volume(self):
		for res in self.price_details:
			if res.item:
				if flt(res.brand_list_price) > 0:
					res.list_priceunit = (flt(res.brand_list_price) + flt(res.addpkg_cost)) * flt(res.weight)
				if flt(res.nrv_per_liter) > 0:
					res.nrv_unit = (flt(res.nrv_per_liter) + flt(res.addpkg_cost)) * flt(res.weight)
			


	@frappe.whitelist()
	def get_items_brand(self,filters=None):
		filters['disabled'] = 0
		filters['is_stock_item'] = 1
		filters['is_sales_item'] = 1
		cost_center=""
		if self.cost_center:
			cost_center=self.cost_center
		brand_price_list = frappe.db.get_all("Brand Price",{"cost_center":cost_center},["brand","price","nrv"])
		if brand_price_list:
			for brand in brand_price_list:
				item_list=frappe.db.get_all("Item",filters,['*'])
				for item in item_list:
					pack_data=frappe.db.get_value("Product Pack",{"item":item.name},["diff_price"])
					self.append("price_details",{
							"item":item.name,
							"item_name":item.item_name,
							"item_group":item.item_group,
							"uom":item.stock_uom,
							"costunit":item.valuation_rate,
							"weight":item.weight_per_unit,
							"weight_uom":item.weight_uom,
							"brand":item.brand,
							"min_qty":1,
							"addpkg_cost":pack_data,
							"brand_list_price":brand.get("price"),
							"nrv_per_liter":brand.get("nrv")
						})
		else:	
			item_list=frappe.db.get_all("Item",filters,['*'])
			for item in item_list:
				pack_data=frappe.db.get_value("Product Pack",{"item":item.name},["diff_price"])
				self.append("price_details",{
						"item":item.name,
						"item_name":item.item_name,
						"item_group":item.item_group,
						"uom":item.stock_uom,
						"costunit":item.valuation_rate,
						"weight":item.weight_per_unit,
						"weight_uom":item.weight_uom,
						"brand":item.brand,
						"min_qty":1,
						"addpkg_cost":pack_data,
						"brand_list_price":0,
						"nrv_per_liter":0
					})
		self.save()
		return True

	def on_submit(self):
		doc=frappe.new_doc("Price List")
		doc.price_list_name=self.pricelist_name
		doc.selling=self.selling
		doc.buying=self.buying
		doc.cost_center=self.cost_center
		doc.filter=self.filter_for_pricelist
		doc.append("countries", {
			"Country":"India"
		})
		doc.save()
		for res in self.price_details: 
			doc_it=frappe.new_doc("Item Price")
			doc_it.item_code=res.item
			doc_it.brand=res.brand
			doc_it.price_list=doc.name
			doc_it.price_list_rate=res.list_priceunit
			doc_it.valid_from=self.start_date
			doc_it.valid_upto=self.end_date
			doc.filter=self.filter_for_pricelist
			doc_it.nrv=res.nrv_unit
			doc_it.stock_transfer=self.stock_transfer 
			doc_it.save(ignore_permissions=True)
