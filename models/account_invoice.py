# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    #Get the Repair Item
    @api.multi
    def get_repair_item_name(self):
    	self.ensure_one()
    	model_mrp_repair = self.env['mrp.repair'].search([('name', '=', self.origin)])
    	if model_mrp_repair:
    		return model_mrp_repair.product_id.name
    	return False
    	
    #Check if Invoice is a Repair Item Invoce
    @api.multi
    def is_invoice_in_repairs(self):
    	self.ensure_one()
    	model_mrp_repair = self.env['mrp.repair'].search([('name', '=', self.origin)])
    	if model_mrp_repair:
    		return True
    	return False    