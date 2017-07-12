from odoo import models, fields, api

class PrimerStockMove(models.Model):
    _inherit = 'stock.move'
    _order = 'date, picking_id, sequence, id'