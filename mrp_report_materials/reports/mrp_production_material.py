# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
from itertools import groupby

from odoo import models, tools, fields, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round

import logging

_logger = logging.getLogger(__name__)


class MrpReportMaterial(models.AbstractModel):
    _name = 'report.mrp_report_materials.mrp_consumption'

    @api.model
    def get_report_values(self, docids, data=None):
        _logger.info("mrp_report_materials context %s:%s" % (self._context, docids))
        # model = self.env.context.get('active_model')
        # production = self.env[model].browse(self.env.context.get('active_ids'))
        docs = self.env['mrp.consumption']. \
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

    @api.multi
    def print_report(self, report_type='qweb-pdf', report_sub_type=False):
        # self.ensure_one()
        context = dict(self.env.context)
        _logger.info('PRINT REPORT %s:%s:%s' % (context, report_type, report_sub_type))
        if report_type == 'xlsx':
            action = self.env.ref('mrp_order_planning.action_stock_inventory_valuation_report_xlsx')
            return action.with_context(context).report_action(self, data={'order_id': self._context.get('active_ids')})
        else:
            action = self.env.ref('mrp_report_materials.action_mrp_order_materials')
            return action.with_context(context).report_action(self, data={
                'ids': self.ids,
                'model': self._table,
                'print_pdf': True,
            })

    @api.model
    def get_html(self):
        """ Render dynamic view from ir.action.client"""
        result = {}
        rcontext = {}
        _logger.info("GET HTML %s" % self._context)
        rec = self.env['mrp.consumption']. \
            with_context(dict(self._context,
                              active_model='mrp.production',
                              active_ids=self._context.get('active_ids'))).create({})
        if rec:
            rcontext['o'] = rec
            result['html'] = self.env.ref('mrp_report_materials.mrp_production_material_document_base').render(rcontext)
        return result

    def get_buttons(self, given_context=None):
        _logger.info("GET BUTTONS %s" % given_context)
        res = [{'name': _('Print to PDF'), 'action': 'print_report', 'data_id': 'asset', 'ttype': 'qweb-pdf'},
               {'name': _('Export to XLSX'), 'action': 'print_report', 'data_id': 'asset', 'ttype': 'xlsx'}]
        return res


class MrpReportMaterialProductAbstract(models.TransientModel):
    _name = 'mrp.consumption'
    _description = 'Manufacture materials report abstract'

    origin_location_id = fields.Many2one(
        string='Origin Location',
        comodel_name='stock.location',
        required=True,
        domain=lambda self: self._get_locations_domain(),
    )
    destination_location_id = fields.Many2one(
        string='Destination Location',
        comodel_name='stock.location',
        required=True,
        domain=lambda self: self._get_locations_domain(),
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Destination Address',
    )
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
        comodel_name='mrp.consumption.line',
        inverse_name='move_id',
        string="Report lines")
    production_ids = fields.Many2many(
        comodel_name='mrp.production',
        string='Productions',
    )

    @api.model
    def default_get(self, fields_list):
        res = super(MrpReportMaterialProductAbstract, self).default_get(fields_list)
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1)
        manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        productions = False
        moves = []
        if self._context.get('active_ids'):
            productions = self.env['mrp.production'].browse(self._context['active_ids'])

        if not productions:
            productions = self.production_ids

        if not productions:
            return res
        res['production_ids'] = [(6, False, productions.ids)]
        res['origin'] = '-'.join([x.name for x in productions])
        move_raw_ids = productions.mapped('move_raw_ids')
        for product_id, group_moves in groupby(move_raw_ids.sorted(lambda r: r.product_id.id), lambda r: r.product_id):
            copy_group_moves = list(group_moves)
            sum_moves_product_uom_qty = consumed_product_uom_qty = 0.0
            use_in = self.env['mrp.production']
            move_line = self.env['stock.move']
            # convert from uom factor FIX in FUTURE !!!!!
            for line in copy_group_moves:
                if line.product_uom_qty == 0.0:
                    continue
                sum_moves_product_uom_qty += line.product_uom_qty
                consumed_product_uom_qty += line.quantity_done
                use_in |= line.raw_material_production_id
                move_line |= line
            if manufacture_route.id not in product_id.mapped('route_ids').ids:
                vals = self._copy_move_line(copy_group_moves[0],
                                            sum_moves_product_uom_qty,
                                            consumed_product_uom_qty,
                                            productions=use_in.sorted(lambda r: r.name),
                                            product_group_moves=move_line.sorted(
                                                lambda r: r.raw_material_production_id))
                moves.append((0, False, vals))

        if moves:
            if warehouse:
                res['origin_location_id'] = warehouse.lot_stock_id.id
            if not res.get('destination_location_id'):
                res['destination_location_id'] = productions[0].location_dest_id.id
            if self._context.get('move_semi_product'):
                origin_location_id_save = res['origin_location_id']
                res['origin_location_id'] = res['destination_location_id']
                res['destination_location_id'] = origin_location_id_save
            res['partner_id'] = productions[0].location_dest_id.partner_id \
                                and productions[0].location_dest_id.partner_id.id or False
            res['stock_move_location_line_ids'] = moves
        return res

    def _copy_move_line(self, move_line, sum_moves_product_uom_qty, consumed_product_uom_qty, productions=False,
                        product_group_moves=False):
        production = move_line.raw_material_production_id
        quant = self.env['stock.quant']
        exclude_picking_ids = productions.mapped('picking_move_ids')
        # move_ids = self.env['stock.move.line']
        available_quantity = transfers_quantity = product_qty = 0.0
        for line in productions:
            product_qty += line.product_qty
        if len(exclude_picking_ids.ids) > 0:
            move_ids = exclude_picking_ids.mapped('move_line_ids'). \
                filtered(lambda r: r.product_id == move_line.product_id)
            qty = sum([x.qty_done for x in move_ids])
            transfers_quantity = qty
        for line in product_group_moves.mapped('location_dest_id'):
            available_quantity += quant._get_available_quantity(move_line.product_id, line, strict=True)

        return {
            'sequence': move_line.sequence,
            'name': production.name,
            'date': production.date_planned_start,
            # 'date_expected': production.date_planned_start,
            'product_id': move_line.product_id.id,
            'product_uom': move_line.product_uom.id,
            'product_qty': product_qty,
            'product_uom_qty': sum_moves_product_uom_qty,
            'real_product_uom_qty': sum_moves_product_uom_qty,
            'exclude_product_uom_qty': available_quantity,
            'transfers_quantity': transfers_quantity,
            'consumed_product_uom_qty': consumed_product_uom_qty,
            'company_id': production.company_id.id,
            'price_unit': move_line.price_unit,
            'origin': production.name,
            'unit_factor': move_line.unit_factor,
            'production_ids': productions and [(6, False, productions.ids)] or False,
            'picking_ids': move_ids and [(6, False, move_ids.mapped('picking_id').ids)] or False,
            'move_ids': product_group_moves and [(6, False, product_group_moves.ids)] or False,
        }


class MrpReportMaterialLineProductAbstract(models.TransientModel):
    _name = "mrp.consumption.line"
    _description = 'Manufacture line materials report abstract'

    move_id = fields.Many2one(
        comodel_name='mrp.consumption',
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
    location_id = fields.Many2one(
        string='Origin Location',
        comodel_name='stock.location',
    )
    location_dest_id = fields.Many2one(
        string='Destination Location',
        comodel_name='stock.location',
    )
    product_qty = fields.Float(
        string="Quantity to produce",
        digits=dp.get_precision('Product Unit of Measure'),
    )
    product_uom = fields.Many2one(
        string='Product Unit of Measure',
        comodel_name='product.uom',
    )
    exclude_product_uom_qty = fields.Float(
        string="Real Quantity on stock",
        digits=dp.get_precision('Product Unit of Measure'),
    )
    product_uom_qty = fields.Float(
        string="Quantity to move",
        digits=dp.get_precision('Product Unit of Measure'),
    )
    consumed_product_uom_qty = fields.Float(
        string="Consumed Quantity to move",
        digits=dp.get_precision('Product Unit of Measure'),
    )
    real_product_uom_qty = fields.Float(
        string="Needed Real Quantity",
        digits=dp.get_precision('Product Unit of Measure'),
        compute="_compute_real_product_uom_qty",
    )
    transfers_quantity = fields.Float(
        string="Transfered quantity by special",
        digits=dp.get_precision('Product Unit of Measure'),
    )
    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
    )
    price_unit = fields.Float(
        string="Unit price"
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

    @staticmethod
    def _compare(qty1, qty2, precision_rounding):
        return float_compare(qty1, qty2, precision_rounding=precision_rounding)

    @api.multi
    @api.depends('product_uom_qty', 'exclude_product_uom_qty')
    def _compute_real_product_uom_qty(self):
        for record in self:
            record.real_product_uom_qty = record.product_uom_qty - record.transfers_quantity
