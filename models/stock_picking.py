from odoo import models, fields, api
from odoo.exceptions import UserError
import time

import logging
_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = 'stock.picking'

    state = fields.Selection([
        ('draft', 'Draft'), ('cancel', 'Cancelled'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting Availability'),
        ('partially_available', 'Partially Available'),
        ('assigned', 'Available'), ('done', 'Done')], string='Status', compute='_new_compute_state',
        copy=False, index=True, readonly=True, store=True, track_visibility='onchange',
        help=" * Draft: not confirmed yet and will not be scheduled until confirmed\n"
             " * Waiting Another Operation: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n"
             " * Waiting Availability: still waiting for the availability of products\n"
             " * Partially Available: some products are available and reserved\n"
             " * Ready to Transfer: products reserved, simply waiting for confirmation.\n"
             " * Transferred: has been processed, can't be modified or cancelled anymore\n"
             " * Cancelled: has been cancelled, can't be confirmed anymore")

    @api.depends('move_type', 'launch_pack_operations', 'move_lines.state', 'move_lines.picking_id', 'move_lines.partially_available')
    @api.one
    def _new_compute_state(self):
        ''' State of a picking depends on the state of its related stock.move
         - no moves: draft or assigned (launch_pack_operations)
         - all moves canceled: cancel
         - all moves done (including possible canceled): done
         - All at once picking: least of confirmed / waiting / assigned
         - Partial picking
          - all moves assigned: assigned
          - one of the move is assigned or partially available: partially available
          - otherwise in waiting or confirmed state
        '''
        if not self.move_lines and self.launch_pack_operations:
            self.state = 'assigned'
        elif not self.move_lines:
            self.state = 'draft'
        elif any(move.state == 'draft' for move in self.move_lines):  # TDE FIXME: should be all ?
            self.state = 'draft'
        elif all(move.state == 'cancel' for move in self.move_lines):
            self.state = 'cancel'
        elif all(move.state in ['cancel', 'done'] for move in self.move_lines):
            self.state = 'done'

            # CHECK IF LOCATION BELONGS TO REPAIR'S SERVICE CENTER
            warehouse_id = self.env.user.warehouse_id
            warehouse = self.env['stock.warehouse'].search([('id', '=', warehouse_id.id)])

            origin = self.origin

            check_repair = self.env['mrp.repair'].search([('name', '=', origin)], limit=1)

            if not len(check_repair):
                # CHECK IF RETURN
                transfer_order = self.env['stock.picking'].search([('name', '=', origin)], limit=1)
                if transfer_order:
                    origin = transfer_order.origin

            repair = self.env['mrp.repair'].search([('name', '=', origin)], limit=1)

            customer_location_id = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
            # UPDATE REPAIR LOCATION
            if len(repair):
                if warehouse.lot_stock_id.id == self.location_dest_id.id: 
                    # _logger.info(customer_location_id.id)
                    lot_id = self.env['stock.production.lot'].search([('name','=',origin)])
                    sql = """UPDATE public.mrp_repair SET location_id = %s, location_dest_id = %s, routing = %s, lot_id = %s WHERE id = %s"""
                    self.env.cr.execute(sql, (self.location_dest_id.id, customer_location_id.id, None, lot_id.id, repair.id)) 
                    # if repair.state == 'confirmed':
                    #     self.
                else:
                    sql = """UPDATE public.mrp_repair SET location_id = %s, location_dest_id = %s, routing = %s WHERE id = %s"""
                    self.env.cr.execute(sql, (self.location_dest_id.id, self.location_id.id, None,repair.id))

                # UPDATE REPAIR COST ITEMS LOCATION
                
                if repair.state != 'under_repair':
                    if repair.location_id.id != customer_location_id.id:
                        repair_line = self.env['mrp.repair.line'].search([('repair_id', '=', repair.id)])
                        for line in repair_line:
                            sql = """UPDATE public.mrp_repair_line SET location_id = %s WHERE id = %s"""
                            self.env.cr.execute(sql, (self.location_dest_id.id,line.id))
                            # super(PrimerRepair, self)._compute_qty_on_hand()
                            # line._compute_qty_on_hand()

        else:
            # We sort our moves by importance of state: "confirmed" should be first, then we'll have
            # "waiting" and finally "assigned" at the end.
            moves_todo = self.move_lines\
                .filtered(lambda move: move.state not in ['cancel', 'done'])\
                .sorted(key=lambda move: (move.state == 'assigned' and 2) or (move.state == 'waiting' and 1) or 0)
            if self.move_type == 'one':
                self.state = moves_todo[0].state
            elif moves_todo[0].state != 'assigned' and any(x.partially_available or x.state == 'assigned' for x in moves_todo):
                self.state = 'partially_available'
            else:
                self.state = moves_todo[-1].state

    @api.multi
    def force_assign(self):
        """ Changes state of picking to available if moves are confirmed or waiting.
        @return: True
        """
        self.mapped('move_lines').filtered(lambda move: move.state in ['confirmed', 'waiting']).force_assign()

        if self.origin:
            operation_id = self.env['stock.pack.operation'].search([('picking_id', '=', self.id)])

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
            # check_repair = self.env['mrp.repair'].search([('name', '=', origin),('state', 'not in', ['done','cancel'])], limit=1)
            check_repair = self.env['mrp.repair'].search([('name', '=', origin)], limit=1)

            if not len(check_repair):
                # CHECK IF RETURN
                # transfer_order = self.env['stock.picking'].search([('name', '=', origin),('state', 'not in', ['done','cancel'])], limit=1)
                transfer_order = self.env['stock.picking'].search([('name', '=', origin)], limit=1)
                if transfer_order:
                    origin = transfer_order.origin
                    is_return = True

            # repair = self.env['mrp.repair'].search([('name', '=', origin),('state', 'not in', ['done','cancel'])], limit=1)
            repair = self.env['mrp.repair'].search([('name', '=', origin)], limit=1)
            if repair:
                if is_return == False:
                    if repair.last_route:
                        # DATE RETURNED TO CUSTOMER
                        if repair.last_route.route == 'customer':
                            _logger.info('DATE RETURNED TO CUSTOMER')
                            cust_location_id = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
                            if pick.location_dest_id.id == cust_location_id.id:
                                _logger.info('MAUI')
                                _logger.info(pick.location_dest_id.id)
                                _logger.info(cust_location_id.id)
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
                        _logger.info('DATE RECEIVED REPAIR ITEM FROM CUSTOMER')
                        warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', pick.location_dest_id.id)])
                        if warehouse_id:
                            picking_type_name = warehouse_id.code + '-RECV Repair Item from Customer'
                            picking_type_id = self.env['stock.picking.type'].search([('name', '=', picking_type_name)], limit=1)
                            if pick.picking_type_id.id == picking_type_id.id:
                                repair.write({'ri_recd_from_cust_date': time.strftime('%m/%d/%y %H:%M:%S')})

                else:
                    # DATE RECEIVED BACK IN STORE
                    _logger.info('DATE RECEIVED BACK IN STORE')
                    repair.write({'ri_recd_back_date': time.strftime('%m/%d/%y %H:%M:%S')})
        return
            