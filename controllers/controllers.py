# -*- coding: utf-8 -*-
from odoo import http

# class PrimerMrp(http.Controller):
#     @http.route('/primer_mrp/primer_mrp/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/primer_mrp/primer_mrp/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('primer_mrp.listing', {
#             'root': '/primer_mrp/primer_mrp',
#             'objects': http.request.env['primer_mrp.primer_mrp'].search([]),
#         })

#     @http.route('/primer_mrp/primer_mrp/objects/<model("primer_mrp.primer_mrp"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('primer_mrp.object', {
#             'object': obj
#         })