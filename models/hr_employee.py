from odoo import models, fields, api

class hr_employee(models.Model):
    _inherit = 'hr.employee'

    @api.multi
    def name_get(self):
        result = []
        context = self._context or {}
        if context.get('repair_tech', False):
            for record in self:
                department = record.department_id.name
                if department:
                    result.append((record.id, record.name + " - " + department))
                else:
                    result.append((record.id, record.name))
        else:
            for record in self:
                result.append((record.id, record.name))
        return result