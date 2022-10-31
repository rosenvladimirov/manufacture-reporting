# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
from itertools import groupby
from statistics import mean

from odoo import models, tools, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round

import logging

_logger = logging.getLogger(__name__)


class MrpReportMaterialPricing(models.AbstractModel):
    _name = 'report.mrp_report_materials.mrp_pricing'

    @api.model
    def get_report_values(self, docids, data=None):
        _logger.info("mrp_report_pricing context %s:%s:%s" % (self._context, docids, data))

        if data.get('production_ids', False):
            docids = data['production_ids']

        # model = self.env.context.get('active_model')
        # production = self.env[model].browse(self.env.context.get('active_ids'))
        docs = self.env['mrp.pricing']. \
            with_context(dict(self._context, active_model='mrp.production', active_ids=docids)).create({})
        # _logger.info("mrp_report_materials %s:%s:%s" % (self._context, docs, data))
        # , precision_rounding = rounding
        return {
            'doc_ids': docs.ids,
            'doc_model': docs._name,
            'docs': docs,
            'time': time,
            'data': data,
            'float_round': lambda qty, rounding: float_round(qty, precision_rounding=rounding),
            'float_compare': lambda qty1, qty2, precision:
            float_compare(qty1, qty2, precision_digits=precision),
        }


class MrpReportMaterialPricingAbstract(models.TransientModel):
    _name = 'mrp.pricing'
    _description = 'Manufacture pricing by materials report abstract'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env['res.company']._company_default_get('stock.picking'),
    )
    name = fields.Char(
        string='Reference',
        default='/',
    )
    origin = fields.Char(
        string='Source Document',
    )
    date = fields.Date(
        string='Date',
        default=fields.Datetime.now,
    )
    stock_move_location_line_ids = fields.One2many(
        comodel_name='mrp.pricing.line',
        inverse_name='move_id',
        string="Report lines")
    production_ids = fields.Many2many(
        comodel_name='mrp.production',
        string='Productions',
    )
    report_small = fields.Boolean('Less data', default=True)

    @api.model
    def get_currency_amount(self, order, amount):
        if order.currency_id != order.company_id.currency_id:
            amount = order.currency_id.with_context(date=order.date_approve). \
                compute(amount, order.company_id.currency_id, round=False)
        return amount

    @api.model
    def get_unit_price(self, x):
        production_id = x.raw_material_production_id
        domain = [('product_id', '=', x.product_id.id)]
        if production_id:
            analytic_account_id = production_id.analytic_account_id
            domain.append(('account_analytic_id', '=', analytic_account_id.id))
        purchase_id = self.env['purchase.order.line'].search(domain, order='date_planned DESC', limit=1)

        if x.price_unit != 0.0:
            price_unit = x.price_unit
        elif x.price_unit == 0.0 and purchase_id:
            price_unit = purchase_id.price_unit
            order = purchase_id.order_id
            if purchase_id.taxes_id:
                price_unit = purchase_id.taxes_id.with_context(round=False).compute_all(
                    price_unit, currency=purchase_id.order_id.currency_id, quantity=1.0, product=purchase_id.product_id,
                    partner=purchase_id.order_id.partner_id
                )['total_excluded']
            if purchase_id.product_uom.id != purchase_id.product_id.uom_id.id:
                price_unit *= purchase_id.product_uom.factor / purchase_id.product_id.uom_id.factor
            if order.currency_id != order.company_id.currency_id:
                price_unit = order.currency_id.with_context(date=order.date_approve).\
                    compute(price_unit, order.company_id.currency_id, round=False)
        else:
            price_unit = x.product_id.standard_price
        # _logger.info("PRICE UNIT 1 %s=>std=%s:mv=%s:p=%s" % (x.product_id.display_name, x.product_id.standard_price, x.price_unit, purchase_id and purchase_id.price_unit))
        return abs(price_unit), purchase_id

    @api.model
    def default_get(self, fields_list):
        res = super(MrpReportMaterialPricingAbstract, self).default_get(fields_list)
        productions = False
        moves = []
        if self._context.get('production_ids'):
            productions = self.env['mrp.production'].browse(self._context['production_ids'])

        if not productions:
            productions = self.production_ids

        if not productions and self._context.get('active_model') == 'mrp.production':
            productions = self.env['mrp.production'].browse(self._context['active_ids'])

        if not productions and self._context.get('active_model') == 'sale.order':
            sales = self.env['sale.order'].browse(self._context['active_ids'])
            productions = self.env['mrp.production'].search([('sale_id', 'in', sales.ids)])

        if not productions:
            return res
        if productions:
            res['production_ids'] = [(6, False, productions.ids)]
            res['origin'] = '-'.join([x.name for x in productions])
        res['report_small'] = self._context.get('report_small', False)

        for product_tmpl_id, group_tmpl_moves in groupby(productions.sorted(lambda r: r.product_id.product_tmpl_id.id),
                                                         lambda r: r.product_id.product_tmpl_id):
            copy_group_tmpl_moves = list(group_tmpl_moves)
            group_productions = self.env['mrp.production']
            sum_product_uom_qty = 0.0
            for production_id in copy_group_tmpl_moves:
                group_productions |= production_id
                sum_product_uom_qty += production_id.product_qty
            move_raw_ids = group_productions.mapped('move_raw_ids')
            price_subtotal = own_price_subtotal = 0.0
            for line in move_raw_ids:
                if line.product_uom_qty == 0.0:
                    continue
                price_unit, purchase_id = self.get_unit_price(line)
                if line.product_id.product_tmpl_id.own_mrp_component:
                    own_price_subtotal += price_unit * line.raw_material_production_id.product_qty
                else:
                    price_subtotal += price_unit * line.raw_material_production_id.product_qty
                _logger.info("PRODUCTION %s=%s*%s" % (product_tmpl_id.display_name, price_unit, line.raw_material_production_id.product_qty))

            for product_id, group_moves in groupby(move_raw_ids.sorted(lambda r: r.product_id.id),
                                                   lambda r: r.product_id):
                copy_group_moves = list(group_moves)
                sum_moves_product_uom_qty = 0.0
                use_in = self.env['mrp.production']
                move_line = self.env['stock.move']
                analytic_account_id = self.env['account.analytic.account']
                for line in copy_group_moves:
                    if line.product_uom_qty == 0.0:
                        continue
                    sum_moves_product_uom_qty += line.product_uom_qty
                    use_in |= line.raw_material_production_id
                    analytic_account_id |= line.raw_material_production_id.analytic_account_id
                    move_line |= line

                domain = [('product_id', '=', product_id.id)]
                if analytic_account_id:
                    domain.append(('account_analytic_id', 'in', analytic_account_id.ids))
                purchase_ids = self.env['purchase.order.line'].search(domain, order='date_planned DESC')
                vals = self._copy_move_line(copy_group_moves[0],
                                            product_tmpl_id,
                                            sum_product_uom_qty,
                                            [price_subtotal, own_price_subtotal],
                                            sum_moves_product_uom_qty,
                                            unit_factor=mean([x.unit_factor for x in copy_group_moves]),
                                            productions=use_in.sorted(lambda r: r.name),
                                            product_group_moves=move_line.sorted(
                                                lambda r: r.raw_material_production_id),
                                            purchase_ids=purchase_ids)
                moves.append((0, False, vals))

        if moves:
            res['stock_move_location_line_ids'] = moves
        # _logger.info("RES %s" % res)
        return res

    def _copy_move_line(self, move_line, product_tmpl_id, product_qty, price_subtotal, sum_moves_product_uom_qty,
                        unit_factor=0.0,
                        productions=False,
                        product_group_moves=False,
                        purchase_ids=False):
        production = move_line.raw_material_production_id
        move_ids = self.env['stock.move.line']
        price_unit = own_price_unit = 0.0
        if move_line.product_id.product_tmpl_id.own_mrp_component:
            own_price_unit, purchase_id = self.get_unit_price(move_line)
        else:
            price_unit, purchase_id = self.get_unit_price(move_line)

        # _logger.info("PRICE UNIT 2 %s=%s" % (move_line.product_id.display_name, price_unit))
        return {
            'sequence': move_line.sequence,
            'company_id': production.company_id.id,
            'currency_id': production.company_id.currency_id.id,
            'name': production.name,
            'date': production.date_planned_start,
            'product_tmpl_id': product_tmpl_id.id,
            'product_id': move_line.product_id.id,
            'product_uom': move_line.product_uom.id,
            'product_qty': product_qty,
            'price_unit_tmpl': price_subtotal[0]/product_qty,
            'price_tmpl_subtotal': price_subtotal[0],
            'own_price_unit_tmpl': price_subtotal[1]/product_qty,
            'own_price_tmpl_subtotal': price_subtotal[1],
            'product_uom_qty': sum_moves_product_uom_qty,
            'price_unit': price_unit,
            'price_subtotal': price_unit*sum_moves_product_uom_qty,
            'own_price_unit': own_price_unit,
            'own_price_subtotal': own_price_unit * sum_moves_product_uom_qty,
            'origin': production.name,
            'unit_factor': unit_factor,
            'production_ids': productions and [(6, False, productions.ids)] or False,
            'picking_ids': move_ids and [(6, False, move_ids.mapped('picking_id').ids)] or False,
            'move_ids': product_group_moves and [(6, False, product_group_moves.ids)] or False,
            'purchase_ids': purchase_ids and [(6, False, purchase_ids.ids)] or False,
        }

    @api.multi
    def print_report(self, report_type='qweb-pdf', given_context=None):
        # self.ensure_one()
        if given_context is None:
            given_context = dict(self._context)
        # _logger.info('PRINT REPORT %s:%s:%s' % (given_context, report_type, self._context))
        if report_type == 'xlsx':
            action = self.env.ref('mrp_order_pricing.action_mrp_order_pricing_report_xlsx')
            return action.with_context(given_context).report_action(self, data={
                'production_ids': given_context['active_ids'],
            })
        else:
            action = self.env.ref('mrp_order_pricing.action_mrp_order_pricing_qweb')
            return action.with_context(given_context).report_action(self, data={
                'ids': self.ids,
                'model': self._table,
                'print_pdf': True,
                'production_ids': given_context['active_ids'],
            })

    @api.model
    def get_html(self, given_context=None):
        """ Render dynamic view from ir.action.client"""
        result = {}
        rcontext = {
            'time': time,
            'context_timestamp': lambda t: fields.Datetime.context_timestamp(self.with_context(tz=self.env.user.tz), t),
            'float_round': lambda qty, rounding: float_round(qty, precision_rounding=rounding),
            'float_compare': lambda qty1, qty2, precision: float_compare(qty1, qty2, precision_digits=precision),
        }
        if given_context is None:
            given_context = self._context
        docs = self.with_context(dict(self._context,
                                      active_model='mrp.production',
                                      active_ids=given_context.get('active_ids'))).create({})
        _logger.info("GET HTML %s:%s:%s" % (docs.stock_move_location_line_ids, self._context, given_context))
        if docs:
            rcontext['o'] = docs
            result['html'] = self.env.ref('mrp_order_pricing.mrp_order_pricing_document_base').render(rcontext)
        return result

    def get_buttons(self, given_context=None):
        res = [{'name': _('Print to PDF'), 'action': 'print_report', 'data_id': 'asset', 'ttype': 'qweb-pdf'},
               {'name': _('Export to XLSX'), 'action': 'print_report', 'data_id': 'asset', 'ttype': 'xlsx'}]
        return res


class MrpReportMaterialLineProductAbstract(models.TransientModel):
    _name = "mrp.pricing.line"
    _description = 'Manufacture line pricing materials report abstract'

    move_id = fields.Many2one(
        comodel_name='mrp.pricing',
        string='Report reference',
        index=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string="Sequence",
    )
    name = fields.Char(
        string="Name",
    )
    date = fields.Datetime(
        string=""
    )
    product_id = fields.Many2one(
        string="Product",
        comodel_name="product.product",
        required=True,
    )
    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Product template')
    product_qty = fields.Float(
        string="Quantity to produce",
        digits=dp.get_precision('Product Unit of Measure'),
    )
    price_unit_tmpl = fields.Float(
        string='Template Unit price'
    )
    price_tmpl_subtotal = fields.Monetary(
        string='Product template Subtotal'
    )
    own_price_unit_tmpl = fields.Float(
        string='Own Template Unit price'
    )
    own_price_tmpl_subtotal = fields.Monetary(
        string='Own Product template Subtotal'
    )
    product_uom = fields.Many2one(
        string='Product Unit of Measure',
        comodel_name='product.uom',
    )
    product_uom_qty = fields.Float(
        string="Quantity to move",
        digits=dp.get_precision('Product Unit of Measure'),
    )
    price_unit = fields.Float(
        string='Unit price'
    )
    price_subtotal = fields.Monetary(
        string='Subtotal'
    )
    own_price_unit = fields.Float(
        string='Own Unit price'
    )
    own_price_subtotal = fields.Monetary(
        string='Own Subtotal'
    )
    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
        related='move_id.company_id',
    )
    currency_id = fields.Many2one(
        string='Currency',
        comodel_name='res.currency',
        default = lambda self: self.env.user.company_id.currency_id.id,
    )
    origin = fields.Char(
        string="Ref"
    )
    unit_factor = fields.Float(
        string="Unit Factor",
    )
    production_ids = fields.Many2many(
        comodel_name='mrp.production',
        string='Productions',
    )
    picking_ids = fields.Many2many(
        comodel_name='stock.picking',
        string='Stock picking',
    )
    move_ids = fields.Many2many(
        comodel_name='stock.move',
        string='Stock move',
    )
    purchase_ids = fields.Many2many(
        comodel_name='purchase.order.line',
        string='Purchase order line'
    )
