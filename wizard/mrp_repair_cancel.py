# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import UserError


class RepairCancel(models.TransientModel):
    _name = 'primer.mrp.repair.cancel'
    _description = 'Cancel Repair'

    status = fields.Many2one('mrp.repair.status', 'User Status', required=True)

    @api.multi
    def cancel_repair(self):
        if not self._context.get('active_id'):
            return {'type': 'ir.actions.act_window_close'}
        repair = self.env['mrp.repair'].browse(self._context['active_id'])
        cancel_status = self.status
        repair.action_repair_cancel_force(cancel_status)
        return {'type': 'ir.actions.act_window_close'}