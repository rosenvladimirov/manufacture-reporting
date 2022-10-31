# Copyright (C) 2011 Julius Network Solutions SARL <contact@julius.fr>
# Copyright 2018 Camptocamp SA
# Copyright 2019 Sergio Teruel - Tecnativa <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from itertools import groupby

import logging

_logger = logging.getLogger(__name__)


class MrpReportMaterialsWizard(models.TransientModel):
    _name = "wiz.mrp.report.materials"

    report_small = fields.Boolean('Show less data', default=True)
    report_no_detail = fields.Boolean('Without detail', default=True)
    wait_only = fields.Boolean('Only waiting materials')
    production_ids = fields.Many2many('mrp.production', string='Production')
    sale_order_line_ids = fields.Many2many('sale.order.line', string='Sale order lines')

    @api.model
    def default_get(self, fields_list):
        res = super(MrpReportMaterialsWizard, self).default_get(fields_list)
        if not res.get('production_ids') and self._context.get('active_model') == 'mrp.production':
            production_ids = self.env['mrp.production'].browse(self._context['active_ids'])
            res['production_ids'] = [(6, False, production_ids.ids)]
        if not res.get('production_ids') and self._context.get('active_model') == 'stock.picking':
            production_ids = self.env['mrp.production']
            picking_ids = self.env['stock.picking'].browse(self._context['active_ids'])
            for line in picking_ids:
                production_ids |= line.production_ids
            res['production_ids'] = [(6, False, production_ids.ids)]
        if not res.get('production_ids') and self._context.get('active_model') == 'sale.order':
            sale_line_ids = self.env['sale.order.line']
            sale_ids = self.env['sale.order'].browse(self._context['active_ids'])
            production_ids = self.env['mrp.production'].search([('sale_id', 'in', sale_ids.ids)])
            for sale_id in sale_ids:
                for line in sale_id.order_line:
                    sale_line_ids |= line
            res['production_ids'] = [(6, False, production_ids.ids)]
            res['sale_order_line_ids'] = [(6, False, sale_line_ids.ids)]
        return res

    @api.multi
    def action_reports(self):
        for record in self:
            if record.production_ids or record.sale_order_line_ids:
                action = self.env.ref('mrp_report_materials.action_mrp_order_materials_report').read()[0]
                _logger.info("ACTION %s" % action['context'])
                action['context'] = {
                    'active_model': 'mrp.consumption',
                    'report_small': record.report_small,
                    'report_no_detail': record.report_no_detail,
                    'wait_only': record.wait_only,
                    'production_ids': record.production_ids.ids,
                    'sale_order_line_ids': record.sale_order_line_ids.ids,
                }
                return action
