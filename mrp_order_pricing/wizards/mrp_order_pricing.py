# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from itertools import groupby

import logging

_logger = logging.getLogger(__name__)


class MrpReportPricingWizard(models.TransientModel):
    _name = "wiz.mrp.report.pricing"

    production_ids = fields.Many2many('mrp.production', string='Production')
    report_small = fields.Boolean('Less data', default=True)

    @api.model
    def default_get(self, fields_list):
        res = super(MrpReportPricingWizard, self).default_get(fields_list)
        if not res.get('production_ids') and self._context.get('active_model') == 'sale.order':
            sale_order_id = self.env['sale.order'].browse(self._context['active_ids'])
            production_ids = self.env['mrp.production'].search([('sale_id', 'in', self._context['active_ids'])])
            if production_ids:
                res['production_ids'] = [(6, False, production_ids.ids)]
        if not res.get('production_ids') and self._context.get('active_model') == 'mrp.production':
            production_ids = self.env['mrp.production'].browse(self._context['active_ids'])
            if production_ids:
                res['production_ids'] = [(6, False, production_ids.ids)]
        if not res.get('production_ids'):
            raise UserError(_('Not found any production!'))
        return res

    @api.multi
    def action_reports(self):
        for record in self:
            if record.production_ids:
                action = self.env.ref('mrp_order_pricing.action_mrp_order_pricing_report').read()[0]
                # _logger.info("ACTION %s" % action['context'])
                report = self.env['mrp.pricing'].\
                    with_context(dict(self._context, production_ids=record.production_ids.ids)).create({})
                # _logger.info("REPORT %s:%s" % (report, report._name))
                action['context'] = {
                    'active_id': report.id,
                    'active_model': report._name,
                    'production_ids': record.production_ids.ids,
                    'report_small': record.report_small,
                }
                return action
