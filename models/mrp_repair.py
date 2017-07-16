from odoo import models, fields, api
from odoo.exceptions import UserError

from datetime import datetime
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

    # NEW FIELDS
    valid_warranty = fields.Selection([('yes','Yes'),('no','No')], string='Valid Warranty?', required=True, default='no')
    routing = fields.Many2one('mrp.repair.routing', string='Routing')
    last_route = fields.Many2one('mrp.repair.routing', string='Last Route', readonly=True)
    status = fields.Many2one('mrp.repair.status', 'Status')
    status_history = fields.Text('Status History')
    is_in_customer = fields.Boolean(string="Delivered to Customer", compute='_compute_customer_location')
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
    total_system_time = fields.Char(string='Total System Time', readonly=True, compute='_compute_total_system_time')
    total_outsourced_time = fields.Char(string='Total Outsourced Time', readonly=True, compute='_compute_total_outsourced_time')
    total_outsourced_service_time = fields.Char(string='Total Outsourced Service Time', readonly=True, compute='_compute_total_outsourced_service_time')
    total_outsourced_wait_time = fields.Char(string='Total Outsourced Wait Time', readonly=True)
    performance_time = fields.Char(string='Performance Time', readonly=True, compute='_compute_performance_time')
    store_disp_reaction_time = fields.Char(string='Store Dispatch Reaction Time', readonly=True, compute='_compute_store_disp_reaction_time')
    store_custret_reaction_time = fields.Char(string='Store Customer Return Reaction Time', readonly=True, compute='_compute_store_custret_reaction_time')
    
    # OVERRIDE FIELDS
    product_id = fields.Many2one(string='Repair Item')
    invoice_method = fields.Selection(default='after_repair')
    location_id = fields.Many2one(default=_new_default_stock_location)
    # operations = fields.One2many(states={})

    @api.onchange('location_id')
    def onchange_location_id(self):
        location_ids = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
        self.location_dest_id = location_ids.id

    @api.onchange('valid_warranty')
    def onchange_valid_warranty(self):
        for operation in self.operations:
            if self.valid_warranty == 'yes':
                operation.to_invoice = False
            else:
                operation.to_invoice = True
    
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
            last_repair_locn = record.repair_locn
            _logger.info('LIAR')
            _logger.info(last_repair_locn)
            last_route = self.env['mrp.repair.routing'].search([('id', '=', record.last_route.id)], limit=1)
            if last_route:
                if last_route.route == 'central':
                    record.repair_locn = 'cwh'
                elif last_route.route == 'servicecenter':
                    record.repair_locn = 'exstore'
                elif last_route.route == 'thirdparty':
                    record.repair_locn = 'thirdparty'
                else:
                    if record.state == 'done' or record.state == '2binvoiced':
                        location_ids = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
                        if record.location_id.id == location_ids.id:
                            record.repair_locn = 'instore'
                    else:
                        record.repair_locn = last_repair_locn

    # COMPUTE TOTAL SYSTEM TIME
    @api.multi
    @api.depends('ri_ret_to_cust_date','ri_recd_from_cust_date')
    def _compute_total_system_time(self):
        for record in self:
            if record.ri_ret_to_cust_date and record.ri_recd_from_cust_date:
                timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_from_cust_date, '%Y-%m-%d %H:%M:%S')
                # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
                days, seconds = timeDiff.days, timeDiff.seconds
                hours = days * 24 + seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                record.total_system_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'

    # COMPUTE TOTAL OUTSOURCED TIME
    @api.multi
    @api.depends('ri_recd_back_date','ri_sent_out_date')
    def _compute_total_outsourced_time(self):
        for record in self:
            if record.ri_recd_back_date and record.ri_sent_out_date:
                timeDiff = datetime.strptime(record.ri_recd_back_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_sent_out_date, '%Y-%m-%d %H:%M:%S')
                # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
                days, seconds = timeDiff.days, timeDiff.seconds
                hours = days * 24 + seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                record.total_outsourced_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'

    # COMPUTE TOTAL OUTSOURCED SERVICE TIME
    @api.multi
    @api.depends('ri_sent_back_date','ri_recd_out_date')
    def _compute_total_outsourced_service_time(self):
        for record in self:
            if record.ri_sent_back_date and record.ri_recd_out_date:
                timeDiff = datetime.strptime(record.ri_sent_back_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_out_date, '%Y-%m-%d %H:%M:%S')
                # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
                days, seconds = timeDiff.days, timeDiff.seconds
                hours = days * 24 + seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                record.total_outsourced_service_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'

    # # COMPUTE TOTAL OUTSOURCED WAIT TIME
    # @api.multi
    # @api.depends('total_outsourced_time','total_outsourced_service_time')
    # def _compute_total_outsourced_wait_time(self):
    #     for record in self:
    #         if record.total_outsourced_time and record.total_outsourced_service_time:
    #             timeDiff = datetime.strptime(record.total_outsourced_time, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.total_outsourced_service_time, '%Y-%m-%d %H:%M:%S')
    #             # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
    #             days, seconds = timeDiff.days, timeDiff.seconds
    #             hours = days * 24 + seconds // 3600
    #             minutes = (seconds % 3600) // 60
    #             seconds = seconds % 60
    #             record.total_outsourced_wait_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'

    # COMPUTE PERFORMANCE TIME
    @api.multi
    @api.depends('ri_ret_to_cust_date','ro_promised_date')
    def _compute_performance_time(self):
        for record in self:
            if record.ri_ret_to_cust_date and record.ro_promised_date:
                timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ro_promised_date, '%Y-%m-%d %H:%M:%S')
                # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
                days, seconds = timeDiff.days, timeDiff.seconds
                hours = days * 24 + seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                record.performance_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'

    # COMPUTE STORE DISP REACTION TIME
    @api.multi
    @api.depends('ri_sent_out_date','ri_recd_from_cust_date')
    def _compute_store_disp_reaction_time(self):
        for record in self:
            if record.ri_sent_out_date and record.ri_recd_from_cust_date:
                timeDiff = datetime.strptime(record.ri_sent_out_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_from_cust_date, '%Y-%m-%d %H:%M:%S')
                # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
                days, seconds = timeDiff.days, timeDiff.seconds
                hours = days * 24 + seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                record.store_disp_reaction_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'

    # COMPUTE STORE CUSTOMER RETURN REACTION TIME
    @api.multi
    @api.depends('ri_ret_to_cust_date','ro_ended_date')
    def _compute_store_custret_reaction_time(self):
        for record in self:
            if record.repair_locn == 'instore':
                if record.ri_ret_to_cust_date and record.ro_ended_date:
                    timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ro_ended_date, '%Y-%m-%d %H:%M:%S')
                    # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
                    days, seconds = timeDiff.days, timeDiff.seconds
                    hours = days * 24 + seconds // 3600
                    minutes = (seconds % 3600) // 60
                    seconds = seconds % 60
                    record.store_custret_reaction_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'
            else:
                if record.ri_ret_to_cust_date and record.ri_recd_back_date:
                    timeDiff = datetime.strptime(record.ri_ret_to_cust_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.ri_recd_back_date, '%Y-%m-%d %H:%M:%S')
                    # result = timeDiff.days + ' Days' + timeDiff.hours + ' Hours'
                    days, seconds = timeDiff.days, timeDiff.seconds
                    hours = days * 24 + seconds // 3600
                    minutes = (seconds % 3600) // 60
                    seconds = seconds % 60
                    record.store_custret_reaction_time = str(hours) + ' Hour(s) ' + str(minutes) + ' Minute(s) ' + str(seconds) + ' Second(s)'

    @api.model
    def create(self, values):
        location_dest_id = self.env['stock.location'].search([('name', '=', 'Customers')], limit=1)
        values['location_dest_id'] = location_dest_id.id

        # LOGGING (STATUS, REPAIR TECH, DATE PROMISED)
        update_user = self.env.user.login
        update_date = time.strftime('%m/%d/%y %H:%M:%S')
        current_status_history = self.status_history 
        new_status_history = ''
        
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
        
        warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', current_location_id.id)])
        picking_type_name = warehouse_id.code + '-RECV Repair Item from Customer'
        picking_type_id = self.env['stock.picking.type'].search([('name', '=', picking_type_name)], limit=1)

        Transfer = self.env['stock.picking'].create({
            'picking_type_id' : picking_type_id.id,            
            'partner_id' : partner_id.id,
            'location_id' : location_dest_id.id,
            'location_dest_id' : current_location_id.id,
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
        super(PrimerRepair, self).action_repair_start()
        start_date = time.strftime('%m/%d/%y %H:%M:%S')
        return self.write({'ro_started_date': start_date})

    @api.multi
    def action_repair_end(self):
        super(PrimerRepair, self).action_repair_end()
        for repair in self:
            end_date = time.strftime('%m/%d/%y %H:%M:%S')
            repair.write({'ro_ended_date': end_date})
        return True
    
    @api.multi
    def write(self, values):
        update_user = self.env.user.login
        update_date = time.strftime('%m/%d/%y %H:%M:%S')
        current_status_history = self.status_history 
        new_status_history = ''
        
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
                    values['ri_sent_out_date'] = time.strftime('%m/%d/%y %H:%M:%S')
                else:
                    raise UserError("No route warehouse defined for the selected routing. Please update routing first.")
                
            elif route == 'servicecenter': 
                if route_warehouse:               
                    picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'internal'),('warehouse_id','=',route_warehouse.id),('active', '=', True)], limit=1)
                    location_dest_id = self.env['stock.picking.type'].browse(picking_type_id.id).default_location_dest_id
                    values['last_route'] = selected_routing
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
    qty_on_hand = fields.Float(string='Quantity on Hand', readonly=True, store=True)

    # OVERRIDE FIELDS
    type = fields.Selection(default='add')

    @api.onchange('type', 'repair_id')
    def onchange_operation_type(self):
        if not self.type:
            self.location_id = False
            self.Location_dest_id = False
        elif self.type == 'add':
            warehouse = self.env['stock.warehouse'].search([('id','=',self.env.user.warehouse_id.id)], limit=1)
            self.location_id = warehouse.lot_stock_id
            self.location_dest_id = self.env['stock.location'].search([('usage', '=', 'production')], limit=1).id
            valid_warranty = self.repair_id.valid_warranty
            if valid_warranty == 'yes':
                self.to_invoice = False
            else:
                self.to_invoice = True
        else:
            self.location_id = self.env['stock.location'].search([('usage', '=', 'production')], limit=1).id
            self.location_dest_id = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1).id


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
        elif self.route == 'customer':
            self.name = 'Customer'
        else:
            self.name = self.route_warehouse.name
