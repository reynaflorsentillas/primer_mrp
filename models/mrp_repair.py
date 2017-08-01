from odoo import models, fields, api, _
from odoo.exceptions import UserError

from datetime import datetime
from datetime import timedelta
import time

import logging
_logger = logging.getLogger(__name__)

class PrimerRepair(models.Model):
    _inherit = 'mrp.repair'

    @api.model
    def _new_default_stock_location(self):
        warehouse = self.env['stock.warehouse'].search([('id', '=', self.env.user.warehouse_id.id)])
        if warehouse:
            return warehouse.lot_stock_id.id
        return False

    @api.model
    def _filter_repair_tech(self):
        job_id = self.env['hr.job'].search([('name', '=', 'Repair Tech')])
        return [('job_id', '=', job_id.id)]


    # OVERRIDE FIELDS
    name = fields.Char('Repair Reference',default=lambda self: _('New Repair'),copy=False, required=True,states={'confirmed': [('readonly', True)]})
    product_id = fields.Many2one(string='Repair Item')
    invoice_method = fields.Selection(default='after_repair')
    location_id = fields.Many2one(default=_new_default_stock_location)
    operations = fields.One2many(readonly=False,states={})

    # NEW FIELDS
    ro_store_location = fields.Many2one('stock.location', 'Store Location of RO', default=_new_default_stock_location, readonly=True)
    valid_warranty = fields.Selection([('yes','Yes'),('no','No')], string='Valid Warranty?', required=True, default='no')
    routing = fields.Many2one('mrp.repair.routing', string='Routing')
    last_route = fields.Many2one('mrp.repair.routing', string='Last Route', readonly=True)
    last_route_non_cust = fields.Many2one('mrp.repair.routing', string='Last Route Non Cust', readonly=True)
    status = fields.Many2one('mrp.repair.status', 'Status')
    status_history = fields.Text('Status History')
    is_in_customer = fields.Boolean(string="Delivered to Customer", compute='_compute_customer_location', store=True)
    repair_tech = fields.Many2one('hr.employee', 'Repair Tech', domain=_filter_repair_tech)
    repair_locn = fields.Selection([
        ('cwh', 'CWH'),
        ('instore', 'In-Store'),
        ('thirdparty', '3rd Party'),
        ('exstore', 'Ex-Store')
    ], string='Repair Location', readonly=True, compute='_compute_repair_location', store=True)
    # RO Dates
    ro_confirmed_date = fields.Datetime(string='Confirmed Date', readonly=True)
    ro_started_date = fields.Datetime(string='Started Date', readonly=True)
    ro_ended_date = fields.Datetime(string='Ended Date', readonly=True)
    ro_promised_date = fields.Datetime(string='Promised Date')
    # RI Dates
    ri_recd_from_cust_date = fields.Datetime(string='Received from Customer', readonly=True)
    ri_sent_out_date = fields.Datetime(string='Sent Out Date', readonly=True)
    ri_recd_out_date = fields.Datetime(string='Received Out Date', readonly=True)
    ri_sent_back_date = fields.Datetime(string='Sent Back Date', readonly=True)
    ri_recd_back_date = fields.Datetime(string='Received Back Date', readonly=True)
    ri_ret_to_cust_date = fields.Datetime(string='Return to Customer', readonly=True)
    # Calculated Elapsed Time
    total_system_time = fields.Float(string='Total System Time', readonly=True, compute='_compute_total_system_time')
    total_outsourced_time = fields.Float(string='Total Outsourced Time', readonly=True, compute='_compute_total_outsourced_time')
    total_outsourced_service_time = fields.Float(string='Total Outsourced Service Time', readonly=True, compute='_compute_total_outsourced_service_time')
    total_outsourced_wait_time = fields.Float(string='Total Outsourced Wait Time', readonly=True, compute="_compute_total_outsourced_wait_time")
    performance_time = fields.Float(string='Performance Time', readonly=True, compute='_compute_performance_time')
    store_disp_reaction_time = fields.Float(string='Store Dispatch Reaction Time', readonly=True, compute='_compute_store_disp_reaction_time')
    store_custret_reaction_time = fields.Float(string='Store Customer Return Reaction Time', readonly=True, compute='_compute_store_custret_reaction_time')

    @api.onchange('location_id')
    def onchange_location_id(self):
        location_ids = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
        self.location_dest_id = location_ids.id

    @api.onchange('valid_warranty')
    def onchange_valid_warranty(self):
        for operation in self.operations:
            if self.valid_warranty == 'yes':
                operation.price_unit = 0.00
            else:
                super(PrimerRepairLine, operation).onchange_product_id()
    
    @api.multi
    @api.depends('location_id')
    def _compute_customer_location(self):
        location_ids = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
        for record in self:
            if record.location_id.id == location_ids.id:
                record.is_in_customer = True
            else:
                record.is_in_customer = False

    @api.multi
    @api.depends('last_route')
    def _compute_repair_location(self):
        for record in self:
            last_route = self.env['mrp.repair.routing'].search([('id', '=', record.last_route.id)], limit=1)
            if last_route:
                if last_route.route == 'central':
                    record.repair_locn = 'cwh'
                elif last_route.route == 'servicecenter':
                    record.repair_locn = 'exstore'
                elif last_route.route == 'thirdparty':
                    record.repair_locn = 'thirdparty'
                elif last_route.route == 'customer':
                    _logger.info('CUSTOMER')
                    last_route_non_cust = record.last_route_non_cust
                    if last_route_non_cust:
                        if last_route_non_cust.route == 'central':
                            record.repair_locn = 'cwh'
                        elif last_route_non_cust.route == 'servicecenter':
                            record.repair_locn = 'exstore'
                        elif last_route_non_cust.route == 'thirdparty':
                            record.repair_locn = 'thirdparty'
                    else:
                        record.repair_locn = 'instore'


    # COMPUTE TOTAL SYSTEM TIME
    @api.multi
    @api.depends('ri_ret_to_cust_date','ri_recd_from_cust_date')
    def _compute_total_system_time(self):
        for record in self:
            if record.ri_ret_to_cust_date and record.ri_recd_from_cust_date:
                timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_from_cust_date, '%Y-%m-%d %H:%M:%S')

                # days, seconds = timeDiff.days, timeDiff.seconds
                # hours = days * 24 + seconds // 3600
                # minutes = (seconds % 3600) // 60
                # seconds = seconds % 60
                record.total_system_time = timeDiff.seconds

    # COMPUTE TOTAL OUTSOURCED TIME
    @api.multi
    @api.depends('ri_recd_back_date','ri_sent_out_date')
    def _compute_total_outsourced_time(self):
        for record in self:
            if record.ri_recd_back_date and record.ri_sent_out_date:
                timeDiff = datetime.strptime(record.ri_recd_back_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_sent_out_date, '%Y-%m-%d %H:%M:%S')

                # days, seconds = timeDiff.days, timeDiff.seconds
                # hours = days * 24 + seconds // 3600
                # minutes = (seconds % 3600) // 60
                # seconds = seconds % 60
                record.total_outsourced_time = timeDiff.seconds

    # COMPUTE TOTAL OUTSOURCED SERVICE TIME
    @api.multi
    @api.depends('ri_sent_back_date','ri_recd_out_date')
    def _compute_total_outsourced_service_time(self):
        for record in self:
            if record.ri_sent_back_date and record.ri_recd_out_date:
                timeDiff = datetime.strptime(record.ri_sent_back_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_out_date, '%Y-%m-%d %H:%M:%S')

                # days, seconds = timeDiff.days, timeDiff.seconds
                # hours = days * 24 + seconds // 3600
                # minutes = (seconds % 3600) // 60
                # seconds = seconds % 60
                record.total_outsourced_service_time = timeDiff.seconds

    # # COMPUTE TOTAL OUTSOURCED WAIT TIME
    @api.multi
    @api.depends('total_outsourced_time','total_outsourced_service_time')
    def _compute_total_outsourced_wait_time(self):
        for record in self:
            if record.total_outsourced_time and record.total_outsourced_service_time:
                timeDiff = record.total_outsourced_time - record.total_outsourced_service_time

                # days, seconds = timeDiff.days, timeDiff.seconds
                # hours = days * 24 + seconds // 3600
                # minutes = (seconds % 3600) // 60
                # seconds = seconds % 60

                record.total_outsourced_wait_time = timeDiff

    # COMPUTE PERFORMANCE TIME
    @api.multi
    @api.depends('ri_ret_to_cust_date','ro_promised_date')
    def _compute_performance_time(self):
        for record in self:
            if record.ri_ret_to_cust_date and record.ro_promised_date:
                timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ro_promised_date, '%Y-%m-%d %H:%M:%S')
                
                # days, seconds = timeDiff.days, timeDiff.seconds
                # hours = days * 24 + seconds // 3600
                # minutes = (seconds % 3600) // 60
                # seconds = seconds % 60
                record.performance_time = timeDiff.seconds

    # COMPUTE STORE DISP REACTION TIME
    @api.multi
    @api.depends('ri_sent_out_date','ri_recd_from_cust_date')
    def _compute_store_disp_reaction_time(self):
        for record in self:
            if record.ri_sent_out_date and record.ri_recd_from_cust_date:
                timeDiff = datetime.strptime(record.ri_sent_out_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_from_cust_date, '%Y-%m-%d %H:%M:%S')
                
                # days, seconds = timeDiff.days, timeDiff.seconds
                # hours = days * 24 + seconds // 3600
                # minutes = (seconds % 3600) // 60
                # seconds = seconds % 60
                record.store_disp_reaction_time = timeDiff.seconds

    # COMPUTE STORE CUSTOMER RETURN REACTION TIME
    @api.multi
    @api.depends('ri_ret_to_cust_date','ro_ended_date')
    def _compute_store_custret_reaction_time(self):
        for record in self:
            if record.repair_locn == 'instore':
                if record.ri_ret_to_cust_date and record.ro_ended_date:
                    timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ro_ended_date, '%Y-%m-%d %H:%M:%S')
                    
                    # days, seconds = timeDiff.days, timeDiff.seconds
                    # hours = days * 24 + seconds // 3600
                    # minutes = (seconds % 3600) // 60
                    # seconds = seconds % 60
                    record.store_custret_reaction_time = timeDiff.seconds
            else:
                if record.ri_ret_to_cust_date and record.ri_recd_back_date:
                    timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_back_date, '%Y-%m-%d %H:%M:%S')
                    
                    # days, seconds = timeDiff.days, timeDiff.seconds
                    # hours = days * 24 + seconds // 3600
                    # minutes = (seconds % 3600) // 60
                    # seconds = seconds % 60
                    record.store_custret_reaction_time = timeDiff.seconds

    # Add 5 business days to transfer order scheduled date
    def set_transfer_scheduled_date(self, from_date, add_days):
        business_days_to_add = add_days
        current_date = from_date
        while business_days_to_add > 0:
            current_date += timedelta(days=1)
            weekday = current_date.weekday()
            if weekday >= 5:
                continue
            business_days_to_add -= 1
        return current_date

    @api.model
    def create(self, values):
        location_dest_id = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
        values['location_dest_id'] = location_dest_id.id

        # LOGGING (STATUS, REPAIR TECH, DATE PROMISED)
        update_user = self.env.user.login
        update_date = time.strftime('%m/%d/%y %H:%M:%S')
        current_status_history = self.status_history 
        new_status_history = ''
        

        #Added by SDS to get the Latest IR SEQUENCE CODE
        if values.get('name', _('New Repair')) == _('New Repair'):
            values['name'] = self.env['ir.sequence'].next_by_code('mrp.repair')         

        # STATUS
        if values.get('status'):
            current_status_id = values.get('status')
            update_status = self.env['mrp.repair.status'].browse(current_status_id)
            if update_status:
                new_status_history += update_user + ' ' + update_date + ' - ' + update_status.name + '\n'
        
        # REPAIR TECH ASSIGNED
        if values.get('repair_tech'):
            repair_tech = values.get('repair_tech')
            repair_tech_emp = self.env['hr.employee'].search([('id', '=', repair_tech)])
            new_status_history += update_user + ' ' + update_date + ' - ' + 'Repair Tech Assigned: ' + repair_tech_emp.name + '\n'
        
        # DATE PROMISED
        if values.get('ro_promised_date'):
            promised_date = values.get('ro_promised_date')
            new_status_history += update_user + ' ' + update_date + ' - ' + 'Promise date committed: ' + promised_date + '\n'

        #  STATUS LOG 
        if current_status_history:
            values['status_history'] = new_status_history + current_status_history
        else:
            current_status_history = '\n'
            values['status_history'] = new_status_history + current_status_history

        result = super(PrimerRepair, self).create(values)

        return result

    @api.multi
    def action_repair_confirm(self):
        super(PrimerRepair, self).action_repair_confirm()
        for repair in self:
            confirm_date = time.strftime('%m/%d/%y %H:%M:%S')
            repair.write({'ro_confirmed_date': confirm_date})
            # CREATE TRANSFER ORDER UPON CONFIRMATION OF REPAIR
            self.create_transfer_order() 
        return True

    def create_transfer_order(self):
        partner_id = self.partner_id
        product_id = self.product_id
        product_uom = self.product_uom
        current_location_id = self.location_id
        location_dest_id = self.location_dest_id
        name = self.name
        scheduled_date = self.set_transfer_scheduled_date(datetime.now(), 5)
        
        warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', current_location_id.id)])
        picking_type_name = warehouse_id.code + '-RECV Repair Item from Customer'
        picking_type_id = self.env['stock.picking.type'].search([('name', '=', picking_type_name)], limit=1)

        Transfer = self.env['stock.picking'].create({
            'picking_type_id' : picking_type_id.id,            
            'partner_id' : partner_id.id,
            'location_id' : location_dest_id.id,
            'location_dest_id' : current_location_id.id,
            'min_date': scheduled_date,
            'origin' : name,
            'move_lines' : [(0, 0, {
                'product_id' : product_id.id,
                'product_uom' : product_uom.id,
                'product_uom_qty' : 1.00,
                'name': name,
            })]
        })



    @api.multi
    def action_repair_start(self):
        #SDS
        #Validate First if Item has already been received in Inventory
        #Get the Picking type where Type is Customer to WareHouse Location
        model_stock_picking = self.env['stock.picking'].search([('origin','=', self.name), 
                                                                ('picking_type_id.default_location_dest_id','=', self.location_id.id),  
                                                                ('picking_type_id.default_location_src_id','=', self.location_dest_id.id),])
        if model_stock_picking:
            if model_stock_picking.state != 'done':
                raise UserError('Item to be Repair has not yet receive. Please confirm in Inventory.')
        # else:
            # raise UserError('Item to be Repair has not yet receive. Please confirm in Inventory.')

        for repair in self:
            # VALIDATE IF REPAIR TECHNICIAN ENTERED
            if not repair.repair_tech:
                raise UserError('Repair technician must be entered before starting repair.')

            # VALIDATE REPAIR COSTS ENTERED
            if not repair.operations:
                 raise UserError('Repair Costs must be entered before starting repair.')

            # VALIDATE SPARE PARTS STOCK
            for operation in repair.operations:
                if operation.product_id.categ_id.name == 'Spare Part':
                    if operation.qty_on_hand <= 0:
                        raise UserError('Not enough stock for spare part: ' + str(operation.product_id.name))

        super(PrimerRepair, self).action_repair_start()
        start_date = time.strftime('%m/%d/%y %H:%M:%S')
        return self.write({'ro_started_date': start_date})

    @api.multi
    def action_repair_end(self):
        super(PrimerRepair, self).action_repair_end()
        for repair in self:
            # if repair.is_in_customer == False:
            #     for item in repair.operations:
            #         # if item.location_id != repair.location_id:
            #         #     raise UserError('Make sure the source location of the repair items match the current location of the RO.')
            #         # CHECK IF NOT DELIVERED TO CUSTOMER
            #         if item.product_id.categ_id.name == 'Spare Part':
            #             if item.qty_on_hand <= 0 or item.qty_on_hand < item.product_uom_qty:
            #                 raise UserError('Make sure the repair items listed in the Repair Costs have sufficient qty on hand in the source location indicated.')
            
            # Create Stock Moves for Spare Parts
            Move = self.env['stock.move']
            moves = self.env['stock.move']
            for operation in repair.operations:
                if operation.product_id.categ_id.name == 'Spare Part':
                    _logger.info('REIN')
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
            
            end_date = time.strftime('%m/%d/%y %H:%M:%S')
            repair.write({'ro_ended_date': end_date})
        return True

    @api.multi
    def action_repair_done(self):
        res = {}
        return res
    
    @api.multi
    def write(self, values):
        update_user = self.env.user.login
        update_date = time.strftime('%m/%d/%y %H:%M:%S')
        current_status_history = self.status_history 
        new_status_history = ''
        scheduled_date = self.set_transfer_scheduled_date(datetime.now(), 5)
        
        # STATUS
        if values.get('status'):
            current_status_id = values.get('status')
            update_status = self.env['mrp.repair.status'].browse(current_status_id)
            if update_status:
                new_status_history += update_user + ' ' + update_date + ' - ' + update_status.name + '\n'
        
        # REPAIR TECH ASSIGNED
        if values.get('repair_tech'):
            repair_tech = values.get('repair_tech')
            repair_tech_emp = self.env['hr.employee'].search([('id', '=', repair_tech)])
            new_status_history += update_user + ' ' + update_date + ' - ' + 'Repair Tech Assigned: ' + repair_tech_emp.name + '\n'
        
        # DATE PROMISED
        if values.get('ro_promised_date'):
            promised_date = values.get('ro_promised_date')
            new_status_history += update_user + ' ' + update_date + ' - ' + 'Promise date committed: ' + promised_date + '\n'

        #  STATUS LOG 
        if current_status_history:
            values['status_history'] = new_status_history + current_status_history
        else:
            current_status_history = '\n'
            values['status_history'] = new_status_history + current_status_history

        # ROUTING
        if values.get('routing'):
            selected_routing = values.get('routing')
            # values['last_route'] = selected_routing

            selected_routing_route = self.env['mrp.repair.routing'].search([('id', '=', selected_routing)])

            partner_id = self.partner_id.id
            product_id = self.product_id
            product_uom = self.product_uom
            name = self.name
            location_id = self.location_id

            route = selected_routing_route.route
            route_warehouse = selected_routing_route.route_warehouse

            if location_id.id == route_warehouse.lot_stock_id.id:
                raise UserError("Routing to the same location is not allowed.")

            if route == 'central':
                if route_warehouse:
                    picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'internal'),('warehouse_id','=',route_warehouse.id),('active', '=', True)], limit=1)
                    location_dest_id = self.env['stock.picking.type'].browse(picking_type_id.id).default_location_dest_id
                    values['last_route'] = selected_routing
                    values['last_route_non_cust'] = selected_routing
                    values['ri_sent_out_date'] = time.strftime('%m/%d/%y %H:%M:%S')
                else:
                    raise UserError("No route warehouse defined for the selected routing. Please update routing first.")
                
            elif route == 'servicecenter': 
                if route_warehouse:               
                    picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'internal'),('warehouse_id','=',route_warehouse.id),('active', '=', True)], limit=1)
                    location_dest_id = self.env['stock.picking.type'].browse(picking_type_id.id).default_location_dest_id
                    values['last_route'] = selected_routing
                    values['last_route_non_cust'] = selected_routing
                    values['ri_sent_out_date'] = time.strftime('%m/%d/%y %H:%M:%S')
                else:
                    raise UserError("No route warehouse defined for the selected routing. Please update routing first.")
            
            elif route == 'customer':
                warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', location_id.id)])
                picking_type_name = warehouse_id.code + '-Delivery Order'
                picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'outgoing'),('warehouse_id','=', warehouse_id.id),('active', '=', True),('name', '=', picking_type_name)], limit=1)
                location_dest_id = self.location_dest_id
                values['last_route'] = selected_routing
                
            elif route == 'thirdparty':
                warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', location_id.id)])
                picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'incoming'),('warehouse_id', '=', warehouse_id.id),('active', '=', True),('name', 'like', 'Vendor')], limit=1)
                location_dest_id = self.env['stock.picking.type'].browse(picking_type_id.id).default_location_dest_id
                partner_id = False
                values['last_route'] = selected_routing
                values['last_route_non_cust'] = selected_routing
                values['ri_sent_out_date'] = time.strftime('%m/%d/%y %H:%M:%S')

            # CHECK IF EXISTS IN CURRENT STOCK
            # lot = self.env['stock.production.lot'].search([('name', '=', name),('product_id', '=', product_id.id)])
            # stock_quant = self.env['stock.quant'].search([('location_id', '=', location_id.id),('lot_id', '=', lot.id),('product_id', '=', product_id.id)])

            # CHECK IF A PENDING INITIAL PICKING EXISTS
            picking_pending_initial_exists = self.env['stock.picking'].search([('origin', '=', name),('state', 'not in', ['done','cancel']),('location_dest_id', '=', location_id.id)])

            # if stock_quant:
            if not picking_pending_initial_exists:
                picking_pending_exists = self.env['stock.picking'].search([('origin', '=', name),('state', 'not in', ['done','cancel']),('location_id', '=', location_id.id)])
                if not picking_pending_exists:
                    Transfer = self.env['stock.picking'].create({
                        'picking_type_id' : picking_type_id.id,            
                        'partner_id' : partner_id,
                        'location_id' : location_id.id,
                        'location_dest_id' : location_dest_id.id,
                        'min_date': scheduled_date,
                        'origin' : name,
                        'move_lines' : [(0, 0, {
                            'product_id' : product_id.id,
                            'product_uom' : product_uom.id,
                            'product_uom_qty' : 1.00,
                            'name' : name,
                            'origin' : name,
                        })]
                    })
                else:
                    raise UserError("A pending transfer exists for this repair. Validate or cancel it before you're allowed to proceed.")
            else:
                raise UserError("A pending transfer exists for this repair. Validate or cancel it before you're allowed to proceed.")
            # else:
            #     raise UserError("Please make sure the item your routing is in stock.")
                
        result = super(PrimerRepair, self).write(values)

        return result

class PrimerRepairLine(models.Model):
    _inherit = 'mrp.repair.line'

    # NEW FIELDS
    qty_on_hand = fields.Float(string='Quantity on Hand', readonly=True, compute='_compute_qty_on_hand')

    # OVERRIDE FIELDS
    type = fields.Selection(default='add')

    @api.onchange('type', 'repair_id')
    def onchange_operation_type(self):
        super(PrimerRepairLine, self).onchange_operation_type()
        if self.type == 'add':
            warehouse = self.env['stock.warehouse'].search([('id', '=', self.env.user.warehouse_id.id)])
            self.location_id = warehouse.lot_stock_id
            self.to_invoice = True

    @api.onchange('repair_id', 'product_id', 'product_uom_qty')
    def onchange_product_id(self):
        super(PrimerRepairLine, self).onchange_product_id()
        valid_warranty = self.repair_id.valid_warranty
        if valid_warranty == 'yes':
            self.price_unit = 0.00

    @api.multi
    @api.depends('product_id','location_id')
    def _compute_qty_on_hand(self):
        for record in self:
            if record.product_id.categ_id.name == 'Spare Part':
                stock_quant = self.env['stock.quant'].search([('product_id', '=', record.product_id.id),('location_id', '=', record.location_id.id)])
                for stock in stock_quant:
                    record.qty_on_hand += stock.qty

    #SDS
    #Override Method
    @api.multi
    def write(self, vals):
        if self.env.ref('primer_extend_security_access.fpt_group_repair_user') in self.env.user.groups_id:
            #Get if Product has Been Changed
            if vals.get('product_id'):
                model_product_product = self.env['product.product'].search([('id', '=', vals['product_id'])])
                partner = self.repair_id.partner_id
                pricelist = self.repair_id.pricelist_id
                product_oum_qty = self.product_uom_qty
                if vals.get('product_uom_qty'):
                    product_oum_qty = vals['product_uom_qty']
                price = pricelist.get_product_price(model_product_product, product_oum_qty, partner)
                vals['price_unit'] = price
        return super(PrimerRepairLine, self).write(vals)

    @api.model
    def create(self,vals):
        if self.env.ref('primer_extend_security_access.fpt_group_repair_user') in self.env.user.groups_id:
            model_mrp_repair = self.env['mrp.repair'].search([('id', '=', vals['repair_id'])])
            model_product_product = self.env['product.product'].search([('id', '=', vals['product_id'])])
            partner = model_mrp_repair.partner_id
            pricelist = model_mrp_repair.pricelist_id
            price = pricelist.get_product_price(model_product_product, self.product_uom_qty, partner)
            vals['price_unit'] = price

        res = super(PrimerRepairLine, self).create(vals)
        return res


class PrimerRepairStatus(models.Model):
    _name = 'mrp.repair.status'
    _description = 'Custom and common statuses for Repair Order with state Under Repair'

    name = fields.Char()

class PrimerRepairRouting(models.Model):
    _name = 'mrp.repair.routing'

    name = fields.Char(required=True)

    route = fields.Selection([
        ('central','Central Warehouse'),
        ('thirdparty','3rd Party Vendor'),
        ('customer','Customer'),
        ('servicecenter','Service Center'),
    ], string='Route', required=True)

    route_warehouse = fields.Many2one('stock.warehouse', string='Route Warehouse') 

    @api.onchange('route', 'route_warehouse')
    def _set_name(self):
        if self.route == 'central':
            self.name = 'Central Warehouse'
        elif self.route == 'thirdparty':
            self.name = '3rd Party Vendor'
            self.route_warehouse = None
        elif self.route == 'customer':
            self.name = 'Customer'
            self.route_warehouse = None
        else:
            self.name = self.route_warehouse.name
