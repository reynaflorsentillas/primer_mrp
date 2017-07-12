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
    'depends': ['base', 'mrp_repair', 'stock'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # 'views/views.xml',
        # 'views/templates.xml',
        'data/mrp_repair_routing_data.xml',
        'data/mrp_repair_status_data.xml',
        'views/mrp_repair_view.xml',
        'views/stock_move_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
}