from odoo import models, fields, api, _
import time

import logging
_logger = logging.getLogger(__name__)

class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    # @api.multi
    # def _create_returns(self):
    #     super(ReturnPicking, self)._create_returns()
    #     for wizard in self:
    #         picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
    #         if picking:
    #             repair = self.env['mrp.repair'].search([('name', '=', picking.origin)])
    #             if repair:
    #                 repair.write({'ri_sent_back_date': time.strftime('%m/%d/%y %H:%M:%S')})

    @api.multi
    def create_returns(self):
        # for wizard in self:
        #     picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
        #     if picking:
        #         repair = self.env['mrp.repair'].search([('name', '=', picking.origin)])
        #         if repair:
        #             repair.write({'ri_sent_back_date': time.strftime('%m/%d/%y %H:%M:%S')})
        # super(ReturnPicking, self).create_returns()
        for wizard in self:
            new_picking_id, pick_type_id = wizard._create_returns()
            _logger.info('BANG!')
            _logger.info(self.env.context.get('active_id'))
            picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
            if picking:
                _logger.info(picking)
                repair = self.env['mrp.repair'].search([('name', '=', picking.origin)])
                if repair:
                    repair.write({'ri_sent_back_date': time.strftime('%m/%d/%y %H:%M:%S')})
        # Override the context to disable all the potential filters that could have been set previously
        ctx = dict(self.env.context)
        ctx.update({
            'search_default_picking_type_id': pick_type_id,
            'search_default_draft': False,
            'search_default_assigned': False,
            'search_default_confirmed': False,
            'search_default_ready': False,
            'search_default_late': False,
            'search_default_available': False,
        })
        return {
            'name': _('Returned Picking'),
            'view_type': 'form',
            'view_mode': 'form,tree,calendar',
            'res_model': 'stock.picking',
            'res_id': new_picking_id,
            'type': 'ir.actions.act_window',
            'context': ctx,
        }