from odoo import models, fields, api

class ProductBrandedCollection(models.Model):
    _name = 'product.product.branded.collections'

    name = fields.Char('Name')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    branded_collection_ids = fields.Many2many('product.product.branded.collections', 'product_branded_collection_rel', 'prod_id', 'bran_coll_id', string='Brand, Collection, etc.')    


class ProductProduct(models.Model):
    _inherit = 'product.product'

    branded_collection_ids = fields.Many2many('product.product.branded.collections', 'product_branded_collection_rel', 'prod_id', 'bran_coll_id', string='Brand, Collection, etc.')        