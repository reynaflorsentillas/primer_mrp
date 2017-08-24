# -*- coding: utf-8 -*-
{
    'name': "Primer Repair",

    'summary': """
        Primer Repair Customizations""",

    'description': """
    Extend Repair Order
        - Routing
        - Status History
        - Automatic Creation of Transfer Order
    Extend Transfer (Stock Picking)
        - Update Repair Current and Delivery Locations on Validation of Transfer Order
    """,

    'author': "Moxylus",
    'website': "http://www.moxylus.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Industrial',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mrp_repair', 'stock', 'account','primer_extend_security_access'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/hr_job_data.xml',
        'data/hr_employee_repair_data.xml',
        'data/mrp_repair_routing_data.xml',
        'data/mrp_repair_status_data.xml',
        'data/stock.location.csv',
        'wizard/mrp_repair_cancel_views.xml',
        'views/mrp_repair_views.xml',
        'views/mrp_repair_status_views.xml',
        'views/mrp_repair_routing_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_views.xml',
        # 'views/product_template_views.xml',
        # 'views/mrp_repair_menu.xml',
        'views/product_views.xml',
        'views/stock_reserve_views.xml',
        'report/mrp_repair_template_repair_order.xml',
        'report/external_layout_header_repair.xml',
        #'report/external_layout_header_invoice.xml',
        'report/stock_report_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
}