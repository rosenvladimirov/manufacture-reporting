# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class Picking(models.Model):
    _inherit = "stock.picking"

    @api.multi
    def action_report_consumption(self):
        production_ids = self.env['mrp.production']
        for record in self:
            if record.production_ids:
                production_ids |= record.production_ids

        if production_ids:
            action = self.env.ref('mrp_report_materials.action_mrp_order_materials_report').read()[0]
            action.update({
                'context': {
                    'active_model': 'mrp.production',
                    'active_ids': production_ids.ids,
                }
            })
            return action
        else:
            UserWarning(_('It not possible to print report consumption because no any production order in pickings'))
            return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def get_material_consumption(self):
        docs = self.env['mrp.consumption']
        for record in self:
            if record.production_ids:
                docs |= self.env['mrp.consumption']. \
                    with_context(dict(self._context,
                                      active_model='mrp.production',
                                      production_ids=record.production_ids.ids)).create({})
        return docs
