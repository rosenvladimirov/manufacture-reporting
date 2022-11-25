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


class MrpReportMaterial(models.AbstractModel):
    _name = 'report.mrp_report_materials.mrp_consumption'

    @api.model
    def get_report_values(self, docids, data=None):
        # _logger.info("mrp_report_materials context %s:%s:%s" % (self._context, docids, data))

        if data.get('production_ids', False):
            docids = data['production_ids']

        # model = self.env.context.get('active_model')
        # production = self.env[model].browse(self.env.context.get('active_ids'))
        docs = self.env['mrp.consumption']. \
            with_context(dict(self._context, active_model='mrp.consumption', production_ids=docids)).create({})
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


class MrpReportMaterialProductAbstract(models.TransientModel):
    _name = 'mrp.consumption'
    _description = 'Manufacture materials report abstract'

    origin_location_id = fields.Many2one(
        string='Origin Location',
        comodel_name='stock.location',
        required=True,
    )
    destination_location_id = fields.Many2one(
        string='Destination Location',
        comodel_name='stock.location',
        required=True,
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
    report_small = fields.Boolean('Less data')
    report_no_detail = fields.Boolean('Without detail')
    wait_only = fields.Boolean('Only waiting materials')

    stock_move_location_line_ids = fields.One2many(
        comodel_name='mrp.consumption.line',
        inverse_name='move_id',
        string="Report lines")
    production_ids = fields.Many2many(
        comodel_name='mrp.production',
        string='Productions',
    )
    product_ids = fields.Many2many(
        comodel_name='product.product',
        string='Products',
    )
    product_tmpl_ids = fields.Many2many(
        comodel_name='product.template',
        string='Products',
    )
    bom_ids = fields.Many2many(
        comodel_name='mrp.bom',
        string='Used boms'
    )
    work_with_sale_order = fields.Boolean('Work with sale orders')

    @api.model
    def default_get(self, fields_list):
        res = super(MrpReportMaterialProductAbstract, self).default_get(fields_list)
        # _logger.info("CONTEXT %s" % self._context)
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1)
        manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        productions = False
        products = self.env['product.product']
        move_raw_ids = self.env['stock.move']
        new_bom_ids = self.env['mrp.bom']
        analytic_account_id = self.env['account.analytic.account']
        use_in = self.env['mrp.production']

        product_id = {}
        main_warehouse_location_id = False
        work_with_sale_order = False

        moves = []
        if self._context.get('production_ids'):
            productions = self.env['mrp.production'].browse(self._context['production_ids'])

        if not productions:
            productions = self.production_ids

        if productions:
            for production_id in productions:
                if not product_id.get(production_id.product_id):
                    product_id[production_id.product_id] = 0.0
                product_id[production_id.product_id] += production_id.product_qty
                use_in |= production_id
                analytic_account_id |= production_id.analytic_account_id
                products |= production_id.product_id

        if not products and self._context.get('sale_order_line_ids'):
            main_warehouse_location_id = warehouse.lot_stock_id
            sales = self.env['sale.order.line'].browse(self._context['sale_order_line_ids'])
            for line in sales:
                work_with_sale_order = True
                analytic_account_id |= line.order_id.analytic_account_id
                products |= line.product_id
                if not product_id.get(line.product_id):
                    product_id[line.product_id] = 0.0
                product_id[line.product_id] += line.product_uom_qty

        if products:
            company_id = self.env.user.company_id
            res['company_id'] = company_id.id
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_id.id)], limit=1)
            mrp_warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_id.id),
                                                                ('manufacture_to_resupply', '=', True)], limit=1)
            location_dest_id = mrp_warehouse.lot_stock_id
            res['destination_location_id'] = mrp_warehouse.lot_stock_id.id
            for product in products:
                bom = self.env['mrp.bom']._bom_find(product=product, company_id=company_id.id)
                if not bom:
                    bom = self.env['mrp.bom']._bom_find(product_tmpl=product.product_tmpl_id, company_id=company_id.id)
                if not bom:
                    continue
                new_bom_ids |= bom
                # _logger.info("BOM %s" % bom.product_tmpl_id)
                qty = 1.0
                if product_id.get(product):
                    qty = product_id[product]
                factor = product.uom_id._compute_quantity(qty, bom.product_uom_id) / bom.product_qty
                boms, exploded_lines = bom.with_context(dict(self._context, force_phantom=work_with_sale_order)). \
                    explode(product, factor, picking_type=bom.picking_type_id)
                # bom_raw_ids = bom.mapped('bom_line_ids')
                if bom.routing_id:
                    location_id = bom.routing_id.location_id
                else:
                    location_id = warehouse.lot_stock_id
                for bom_line, line_data in exploded_lines:
                    # sequence_product_type_id = bom_line.sequence
                    # product_type_id = bom_line.product_id.product_tmpl_id.categ_id.get_product_type_id()
                    # if product_type_id and product_type_id.sequence:
                    #     sequence_product_type_id = int(product_type_id.sequence)

                    new_move = self.env['stock.move'].new({
                        'sequence': bom_line.sequence,
                        'name': product.name,
                        'product_id': bom_line.product_id.id,
                        'product_uom_qty': line_data['qty'],
                        'product_uom': bom_line.product_uom_id.id,
                        'location_id': location_id.id,
                        'location_dest_id': location_dest_id.id,
                        'company_id': company_id.id,
                        # 'origin': "Force transfer %s" % product.name,
                        'warehouse_id': warehouse.id,
                        'procure_method': 'make_to_stock',
                        'bom_line_id': bom_line.id,
                        'unit_factor': line_data['qty'] / qty,
                    })
                    # new_move.product_uom_qty = sum_moves
                    # _logger.info("LINE %s" % new_move)
                    move_raw_ids |= new_move
            res['product_ids'] = [(6, False, products.ids)]
            res['product_tmpl_ids'] = [(6, False, products.mapped('product_tmpl_id').ids)]
            res['bom_ids'] = [(6, False, new_bom_ids.ids)]
        if not productions and not products:
            return res
        res['production_ids'] = [(6, False, productions.ids)]
        res['origin'] = '-'.join([x.name for x in productions])
        res['report_small'] = self._context.get('report_small', False)
        res['report_no_detail'] = self._context.get('report_no_detail', False)
        res['wait_only'] = self._context.get('wait_only', False)
        res['work_with_sale_order'] = work_with_sale_order
        if warehouse:
            res['origin_location_id'] = warehouse.lot_stock_id.id
        if not res.get('destination_location_id'):
            res['destination_location_id'] = productions[0].location_dest_id.id
            res['partner_id'] = productions[0].location_dest_id.partner_id \
                                and productions[0].location_dest_id.partner_id.id or False

        if not move_raw_ids:
            move_raw_ids = productions.mapped('move_raw_ids')
        # if productions:
        #     total_final_product = sum(x.product_qty for x in productions)
        # else:
        #     total_final_product = 1.0

        for product_id, group_moves in groupby(move_raw_ids.sorted(lambda r: r.product_id.id), lambda r: r.product_id):
            copy_group_moves = list(group_moves)
            sum_moves_product_uom_qty = consumed_product_uom_qty = 0.0
            move_line = self.env['stock.move']
            # convert from uom factor FIX in FUTURE !!!!!
            # analytic_account_id = self.env['account.analytic.account']

            for line in copy_group_moves:
                if line.product_uom_qty == 0.0:
                    continue
                sum_moves_product_uom_qty += line.product_uom_qty
                consumed_product_uom_qty += line.quantity_done
                use_in |= line.raw_material_production_id
                move_line |= line
                analytic_account_id |= line.raw_material_production_id.analytic_account_id

            domain = [('product_id', '=', product_id.id)]
            if analytic_account_id:
                domain.append(('account_analytic_id', 'in', analytic_account_id.ids))
            purchase_ids = self.env['purchase.order.line'].search(domain, order='date_planned DESC')
            if manufacture_route.id not in product_id.mapped('route_ids').ids:
                vals = self.with_context(dict(self._context,
                                              main_warehouse_location_id=main_warehouse_location_id,
                                              work_with_sale_order=work_with_sale_order)). \
                    _copy_move_line(copy_group_moves[0],
                                    sum_moves_product_uom_qty,
                                    consumed_product_uom_qty,
                                    unit_factor=mean([x.unit_factor for x in copy_group_moves]),
                                    productions=use_in.sorted(lambda r: r.name),
                                    product_group_moves=move_line.sorted(
                                        lambda r: r.product_id.display_name),
                                    purchase_ids=purchase_ids)
                moves.append((0, False, vals))

        if moves:
            res['stock_move_location_line_ids'] = moves
        # _logger.info("RES %s" % res)
        return res

    def _copy_move_line(self, move_line, sum_moves_product_uom_qty, consumed_product_uom_qty, unit_factor=0.0,
                        productions=False,
                        product_group_moves=False,
                        purchase_ids=False):

        product_type_id = False
        production = move_line.raw_material_production_id
        sequence_product_type_id = move_line.sequence
        product_type_id = move_line.product_id.product_tmpl_id.categ_id.get_product_type_id()
        if product_type_id and product_type_id.sequence:
            sequence_product_type_id = int(product_type_id.sequence)

        quant = self.env['stock.quant']
        exclude_picking_ids = productions.mapped('picking_move_ids')
        move_ids = self.env['stock.move.line']
        available_quantity = transfers_quantity = product_qty = 0.0
        for line in productions:
            product_qty += line.product_qty

        if self._context.get('work_with_sale_order', False) and self._context.get('main_warehouse_location_id', False):
            available_quantity += quant. \
                _get_available_quantity(move_line.product_id, self._context['main_warehouse_location_id'], strict=True)

            for line in purchase_ids:
                picking_qty = 0.0
                for picking_id in purchase_ids:
                    picking_qty = sum([x.quantity_done for x in picking_id.move_ids.
                                      filtered(lambda r: r.product_id == move_line.product_id)])
                    # _logger.info("PURCHASE %s (%s)" % (picking_id, picking_qty))
                purchase_product_qty = line.product_uom._compute_quantity(line.product_qty, move_line.product_uom)
                purchase_product_qty = picking_qty < purchase_product_qty and picking_qty or purchase_product_qty
                transfers_quantity += purchase_product_qty - line.product_uom. \
                    _compute_quantity(line.qty_received, move_line.product_uom)

                # _logger.info("LINE %s" % transfers_quantity)

        else:
            if len(exclude_picking_ids.ids) > 0:
                move_ids = exclude_picking_ids.mapped('move_line_ids'). \
                    filtered(lambda r: r.product_id == move_line.product_id)
                qty = sum([x.qty_done for x in move_ids])
                transfers_quantity = qty
            for line in product_group_moves.mapped('location_dest_id'):
                available_quantity += quant._get_available_quantity(move_line.product_id, line, strict=True)

        return {
            'sequence': sequence_product_type_id,
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
            'unit_factor': unit_factor,
            'production_ids': productions and [(6, False, productions.ids)] or False,
            'picking_ids': move_ids and [(6, False, move_ids.mapped('picking_id').ids)] or False,
            'move_ids': move_ids and [(6, False, move_ids.mapped('move_id').ids)] or product_group_moves and [(6, False, product_group_moves.ids)] or False,
            'purchase_ids': purchase_ids and [(6, False, purchase_ids.ids)] or False,
            'product_type_id': product_type_id and product_type_id.id,
        }

    @api.multi
    def print_report(self, report_type='qweb-pdf', given_context=None):
        # self.ensure_one()
        if given_context is None:
            given_context = dict(self._context)
        # _logger.info('PRINT REPORT %s:%s:%s' % (given_context, report_type, self._context))
        if report_type == 'xlsx':
            action = self.env.ref('mrp_report_materials.action_mrp_order_materials_report_xlsx')
            return action.with_context(given_context).report_action(self, data={
                'production_ids': given_context['active_ids'],
                'sale_order_line_ids': self._context.get('sale_order_line_ids', False),
            })
        else:
            action = self.env.ref('mrp_report_materials.action_mrp_order_materials_qweb')
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
        # _logger.info("GET HTML %s:%s:%s" % (docs.stock_move_location_line_ids, self._context, given_context))
        if docs:
            rcontext['o'] = docs
            result['html'] = self.env.ref('mrp_report_materials.mrp_production_material_document_base').render(rcontext)
        return result

    def get_buttons(self, given_context=None):
        # _logger.info("GET BUTTONS %s" % given_context)
        res = [{'name': _('Print to PDF'), 'action': 'print_report', 'data_id': 'asset', 'ttype': 'qweb-pdf'},
               {'name': _('Export to XLSX'), 'action': 'print_report', 'data_id': 'asset', 'ttype': 'xlsx'}]
        return res


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
    purchase_ids = fields.Many2many(
        comodel_name='purchase.order.line',
        string='Purchase order line'
    )
    product_type_id = fields.Many2one(
        comodel_name='project.product.types',
        string='Product Type',
    )

    @staticmethod
    def _compare(qty1, qty2, precision_rounding):
        return float_compare(qty1, qty2, precision_rounding=precision_rounding)

    @api.multi
    @api.depends('product_uom_qty', 'exclude_product_uom_qty', 'transfers_quantity')
    def _compute_real_product_uom_qty(self):
        for record in self:
            if record.move_id.work_with_sale_order:
                record.real_product_uom_qty = record.product_uom_qty - \
                                              (record.exclude_product_uom_qty + record.transfers_quantity)
            else:
                record.real_product_uom_qty = record.product_uom_qty - record.transfers_quantity
