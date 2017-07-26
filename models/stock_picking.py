from odoo import models, fields, api
from odoo.exceptions import UserError
import time

import logging
_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def force_assign(self):
        super(Picking, self).force_assign()
        if self.origin:
            operation_id = self.env['stock.pack.operation'].search([('picking_id', '=', self.id)])
            _logger.info(operation_id)

            for operation in operation_id:
                lot = self.env['stock.production.lot'].search([('name', '=', self.origin),('product_id', '=', operation.product_id.id)])
                if lot:
                    lot_id = lot.id
                else:
                    lot_id = None
                OperationLot = self.env['stock.pack.operation.lot'].create({
                    'lot_name' : self.origin,
                    'qty_todo' : 1,
                    'qty' : 1,
                    'operation_id' : operation.id,
                    'lot_id' : lot_id,
                })
                operation.write({
                    'qty_done' : 1,
                })
        return True

    @api.multi
    def do_new_transfer(self):
        super(Picking, self).do_new_transfer()
        for pick in self:
            origin = pick.origin
            is_return = False
            check_repair = self.env['mrp.repair'].search([('name', '=', origin)], limit=1)

            if not len(check_repair):
                # CHECK IF RETURN
                transfer_order = self.env['stock.picking'].search([('name', '=', origin)], limit=1)
                if transfer_order:
                    origin = transfer_order.origin
                    is_return = True

            repair = self.env['mrp.repair'].search([('name', '=', origin)], limit=1)
            if repair:
                # UPDATE REPAIR
                if self.state == 'done':
                    customer_location_id = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)

                    # warehouse_id = self.env.user.warehouse_id
                    # warehouse = self.env['stock.warehouse'].search([('id', '=', warehouse_id.id)])

                    # DELIVR TO CUSTOMER
                    # if warehouse.lot_stock_id.id == self.location_dest_id.id: 
                    if repair.ro_store_location.id == self.location_dest_id.id: 
                        _logger.info('JAJAMYEON!')
                        lot_id = self.env['stock.production.lot'].search([('name','=',origin)])
                        _logger.info(lot_id)

                        repair.sudo().write({
                            'location_id' : self.location_dest_id.id,
                            'location_dest_id' : customer_location_id.id,
                            'routing' : None,
                            'lot_id' : lot_id.id,
                        })
                    else:
                        _logger.info('BIBIMBAP!')
                        repair.sudo().write({
                            'location_id': self.location_dest_id.id,
                            'location_dest_id': self.location_id.id,
                            'routing': None,
                        })

                    # UPDATE REPAIR COST ITEMS LOCATION
                    if repair.state != 'under_repair':
                        if repair.location_id.id != customer_location_id.id:
                            repair_line = self.env['mrp.repair.line'].search([('repair_id', '=', repair.id)])
                            for line in repair_line:
                                line.write({
                                    'location_id' : self.location_dest_id.id,
                                })


                # STATISTICS
                if is_return == False:
                    if repair.last_route:
                        # DATE RETURNED TO CUSTOMER
                        if repair.last_route.route == 'customer':
                            _logger.info('DATE RETURNED TO CUSTOMER')
                            cust_location_id = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
                            if pick.location_dest_id.id == cust_location_id.id:
                                repair.write({'ri_ret_to_cust_date': time.strftime('%m/%d/%y %H:%M:%S')})

                                Move = self.env['stock.move']
                                moves = self.env['stock.move']
                                for operation in repair.operations:
                                    move = Move.create({
                                        'name': operation.name,
                                        'product_id': operation.product_id.id,
                                        'restrict_lot_id': operation.lot_id.id,
                                        'product_uom_qty': operation.product_uom_qty,
                                        'product_uom': operation.product_uom.id,
                                        'partner_id': repair.address_id.id,
                                        'location_id': operation.location_id.id,
                                        'location_dest_id': operation.location_dest_id.id,
                                    })
                                    moves |= move
                                    operation.write({'move_id': move.id, 'state': 'done'})
                                moves.action_done()
                        # RECEIVE OUT
                        else:
                            _logger.info('RECEIVE OUT')
                            repair.write({'ri_recd_out_date': time.strftime('%m/%d/%y %H:%M:%S')})
                    else:
                        # DATE RECEIVED REPAIR ITEM FROM CUSTOMER
                        # _logger.info('DATE RECEIVED REPAIR ITEM FROM CUSTOMER')
                        warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', pick.location_dest_id.id)])
                        if warehouse_id:
                            picking_type_name = warehouse_id.code + '-RECV Repair Item from Customer'
                            picking_type_id = self.env['stock.picking.type'].search([('name', '=', picking_type_name)], limit=1)
                            if pick.picking_type_id.id == picking_type_id.id:
                                repair.write({'ri_recd_from_cust_date': time.strftime('%m/%d/%y %H:%M:%S')})

                else:
                    # DATE RECEIVED BACK IN STORE
                    # _logger.info('DATE RECEIVED BACK IN STORE')
                    repair.write({'ri_recd_back_date': time.strftime('%m/%d/%y %H:%M:%S')})
        return
            