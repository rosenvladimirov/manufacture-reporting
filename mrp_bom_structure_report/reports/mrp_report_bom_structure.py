# Copyright 2019 Odoo, S.A.
# Copyright 2019 Eficent Business and IT Consulting Services S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

import json

from odoo import api, models, _
from odoo.tools import float_round

import logging
_logger = logging.getLogger(__name__)


class ReportBomStructure(models.AbstractModel):
    _name = 'report.mrp_bom_structure_report.report_bom_structure'
    _description = 'BOM Structure Report'

    @api.model
    def get_report_values(self, docids, data=None):
        docs = []
        for bom_id in docids:
            bom = self.env['mrp.bom'].browse(bom_id)
            variant = data and data.get('variant')
            variants = data and data.get('variants')
            if variants:
                variants = list(map(int, json.loads(variants)))
                _logger.info("VARIANTS %s" % variants)
                candidates = self.env['product.product'].browse(variants)
            else:
                candidates = variant \
                             and self.env['product.product'].browse(int(variant)) \
                             or bom.product_tmpl_id.product_variant_ids
            for product_variant_id in candidates:
                if data and data.get('childs'):
                    doc = self._get_pdf_line(bom_id,
                                             product_id=product_variant_id,
                                             qty=float(data.get('quantity')),
                                             child_bom_ids=json.loads(
                                                 data.get('childs')))
                else:
                    doc = self._get_pdf_line(bom_id,
                                             product_id=product_variant_id,
                                             unfolded=True)
                doc['report_type'] = 'pdf'
                doc['report_structure'] = data and data.get(
                    'report_type') or 'all'
                docs.append(doc)
            if not candidates:
                if data and data.get('childs'):
                    doc = self._get_pdf_line(bom_id,
                                             qty=float(data.get('quantity')),
                                             child_bom_ids=json.loads(
                                                 data.get('childs')))
                else:
                    doc = self._get_pdf_line(bom_id, unfolded=True)
                doc['report_type'] = 'pdf'
                doc['report_structure'] = data and data.get(
                    'report_type') or 'all'
                docs.append(doc)
        return {
            'doc_ids': docids,
            'doc_model': 'mrp.bom',
            'docs': docs,
        }

    @api.model
    def get_html(self, bom_id=False, searchQty=1, searchVariant=False, bom_ids=False):
        res = self._get_report_data(bom_id=bom_id, searchQty=searchQty,
                                    searchVariant=searchVariant, bom_ids=bom_ids)
        if bom_id or searchVariant:
            bom = self.env['mrp.bom'].browse(bom_id)
            res['variant'] = searchVariant or bom.product_tmpl_id.product_variant_id.id

        res['lines']['report_type'] = 'html'
        res['lines']['report_structure'] = 'all'
        res['lines']['has_attachments'] = res['lines']['attachments'] or any(
            component['attachments'] for component in
            res['lines']['components'])
        res['lines'] = self.env.ref(
            'mrp_bom_structure_report.report_mrp_bom').render(
            {'data': res['lines']})
        return res

    @api.model
    def get_bom(self, bom_id=False, product_id=False, line_qty=False,
                line_id=False, level=False):
        lines = self._get_bom(bom_id=bom_id, product_id=product_id,
                              line_qty=line_qty, line_id=line_id, level=level)
        return self.env.ref(
            'mrp_bom_structure_report.report_mrp_bom_line').render(
            {'data': lines})

    @api.model
    def get_operations(self, bom_id=False, qty=0, level=0):
        bom = self.env['mrp.bom'].browse(bom_id)
        lines = self._get_operation_line(bom.routing_id,
                                         float_round(qty / bom.product_qty,
                                                     precision_rounding=1,
                                                     rounding_method='UP'),
                                         level)
        values = {
            'bom_id': bom_id,
            'currency': self.env.user.company_id.currency_id,
            'operations': lines,
        }
        return self.env.ref(
            'mrp_bom_structure_report.report_mrp_operation_line').render(
            {'data': values})

    def _get_bom_reference(self, bom):
        return bom.display_name

    @api.model
    def _get_report_data(self, bom_id, searchQty=0, searchVariant=False, bom_ids=False):
        # lines = {}
        # if bom_ids:
        bom = self.env['mrp.bom'].browse(bom_id)
        # if searchQty is not None:
        #     searchQty = float(searchQty)
        # if searchVariant is not None:
        #     searchVariant = int(searchVariant)
        bom_quantity = searchQty or bom.product_qty
        bom_product_variants = {}
        bom_uom_name = ''

        if bom:
            bom_uom_name = bom.product_uom_id.name

            # Get variants used for search
            if not bom.product_id:
                for variant in bom.product_tmpl_id.product_variant_ids:
                    bom_product_variants[variant.id] = variant.display_name

        lines = self._get_bom(bom_id, product_id=searchVariant,
                              line_qty=bom_quantity, level=1)
        return {
            'lines': lines,
            'variants': bom_product_variants,
            'bom_uom_name': bom_uom_name,
            'bom_qty': bom_quantity,
            'is_variant_applied': self.env.user.user_has_groups('product.group_product_variant') and len(bom_product_variants) > 1,
            'is_uom_applied': self.env.user.user_has_groups('product.group_uom')
        }

    def _get_bom(self, bom_id=False, product_id=False, line_qty=False,
                 line_id=False, level=False):

        bom = self.env['mrp.bom'].browse(bom_id)
        bom_quantity = line_qty

        _logger.info("bom_quantity:%s / bom.product_qty:%s=>%s" % (line_qty, bom.product_qty, product_id))

        if line_id:
            current_line = self.env['mrp.bom.line'].browse(int(line_id))
            bom_quantity = current_line.product_uom_id._compute_quantity(line_qty, bom.product_uom_id)
        # Display bom components for current selected product variant
        if product_id:
            if isinstance(product_id, str):
                product = self.env['product.product'].browse(int(product_id))
            elif isinstance(product_id, int):
                product = self.env['product.product'].browse(product_id)
            else:
                product = product_id
        else:
            product = bom.product_id or bom.product_tmpl_id.product_variant_id
        if product:
            attachments = self.env['mrp.document'].search(
                ['|', '&', ('res_model', '=', 'product.product'),
                 ('res_id', '=', product.id), '&',
                 ('res_model', '=', 'product.template'),
                 ('res_id', '=', product.product_tmpl_id.id)])
        else:
            product = bom.product_tmpl_id
            attachments = self.env['mrp.document'].search(
                [('res_model', '=', 'product.template'),
                 ('res_id', '=', product.id)])
        operations = self._get_operation_line(bom.routing_id, float_round(
            bom_quantity / bom.product_qty, precision_rounding=1,
            rounding_method='UP'), 0)
        lines = {
            'bom': bom,
            'bom_qty': bom_quantity,
            'bom_prod_name': product.display_name,
            'currency': self.env.user.company_id.currency_id,
            'product': product,
            'code': bom and self._get_bom_reference(bom) or '',
            'price': product.uom_id._compute_price(
                product.standard_price, bom.product_uom_id) * bom_quantity,
            'total': sum([op['total'] for op in operations]),
            'level': level or 0,
            'operations': operations,
            'operations_cost': sum([op['total'] for op in operations]),
            'attachments': attachments,
            'operations_time': sum(
                [op['duration_expected'] for op in operations])
        }
        components, total = self._get_bom_lines(bom, bom_quantity, product,
                                                line_id, level)
        lines['components'] = components
        lines['total'] += total
        return lines

    def _get_bom_lines(self, bom, bom_quantity, product, line_id, level):
        components = []
        total = 0
        for line in bom.bom_line_ids:
            line_quantity = (bom_quantity / (
                bom.product_qty or 1.0)) * line.product_qty
            line_quantity_real = (bom_quantity / (
                bom.product_qty or 1.0)) * line.product_qty_real
            if line._skip_bom_line(product):
                continue
            price = line.product_id.uom_id._compute_price(
                line.product_id.standard_price,
                line.product_uom_id) * line_quantity
            price_real = line.product_id.uom_id._compute_price(
                line.product_id.standard_price,
                line.product_uom_id) * line_quantity_real
            if line.child_bom_id:
                factor = line.product_uom_id._compute_quantity(
                    line_quantity,
                    line.child_bom_id.product_uom_id) / \
                         line.child_bom_id.product_qty
                sub_total = self._get_price(line.child_bom_id, factor)
            else:
                sub_total = price
            if line.child_bom_id:
                factor = line.product_uom_id._compute_quantity(
                    line_quantity_real,
                    line.child_bom_id.product_uom_id) / \
                         line.child_bom_id.product_qty
                sub_total_real = self._get_price(line.child_bom_id, factor)
            else:
                sub_total_real = price_real
            sub_total = self.env.user.company_id.currency_id.round(sub_total)
            components.append({
                'prod_id': line.product_id.id,
                'prod_name': line.product_id.display_name,
                'code': line.child_bom_id and self._get_bom_reference(
                    line.child_bom_id) or '',
                'prod_qty': line_quantity,
                'prod_qty_loss': line.loss,
                'prod_qty_real': line_quantity_real,
                'prod_qty_available': line.product_id.qty_available,
                # 'prod_qty_location': line.with_context(dict(self._context, location=bom.location_id)).product_id.qty_available,
                'prod_incoming_qty': line.product_id.incoming_qty,
                'prod_uom': line.product_uom_id.name,
                'prod_cost': self.env.user.company_id.currency_id.round(price),
                'prod_cost_real': self.env.user.company_id.currency_id.round(price_real),
                'parent_id': bom.id,
                'line_id': line.id,
                'level': level or 0,
                'total': sub_total,
                'total_real': sub_total_real,
                'child_bom': line.child_bom_id.id,
                'phantom_bom': (line.child_bom_id and
                                line.child_bom_id.type == 'phantom' or False),
                'attachments': self.env['mrp.document'].search(
                    ['|', '&', ('res_model', '=', 'product.product'),
                     ('res_id', '=', line.product_id.id),
                     '&', ('res_model', '=', 'product.template'),
                     ('res_id', '=', line.product_id.product_tmpl_id.id)]),

            })
            total += sub_total
        return components, total

    def _get_operation_line(self, routing, qty, level):
        operations = []
        total = 0.0
        for operation in routing.operation_ids:
            operation_cycle = float_round(
                qty / operation.workcenter_id.capacity, precision_rounding=1,
                rounding_method='UP')
            duration_expected = operation_cycle * operation.time_cycle + \
                                operation.workcenter_id.time_stop + \
                                operation.workcenter_id.time_start
            # Field costs_hours in mrp.workcenter does not exists in v11
            # total = ((duration_expected / 60.0) *
            # operation.workcenter_id.costs_hour)
            operations.append({
                'level': level or 0,
                'operation': operation,
                'name': operation.name + ' - ' + operation.workcenter_id.name,
                'duration_expected': duration_expected,
                'total': self.env.user.company_id.currency_id.round(total),
            })
        return operations

    def _get_price(self, bom, factor):
        price = 0
        if bom.routing_id:
            # routing are defined on a BoM and don't have a concept of quantity
            # It means that the operation time are defined for the quantity on
            # the BoM (the user produces a batch of products). E.g the user
            # product a batch of 10 units with a 5 minutes operation, the time
            # will be the 5 for a quantity between 1-10, then doubled for
            # 11-20,...
            operation_cycle = float_round(factor, precision_rounding=1,
                                          rounding_method='UP')
            operations = self._get_operation_line(bom.routing_id,
                                                  operation_cycle, 0)
            price += sum([op['total'] for op in operations])
            price += 0.0

        for line in bom.bom_line_ids:
            if line.child_bom_id:
                qty = line.product_uom_id._compute_quantity(
                    line.product_qty * factor,
                    line.child_bom_id.product_uom_id
                ) / line.child_bom_id.product_qty
                sub_price = self._get_price(line.child_bom_id, qty)
                price += sub_price
            else:
                prod_qty = line.product_qty * factor
                not_rounded_price = line.product_id.uom_id._compute_price(
                    line.product_id.standard_price,
                    line.product_uom_id) * prod_qty
                price += self.env.user.company_id.currency_id.round(
                    not_rounded_price)
        return price

    def _get_pdf_line(self, bom_id, product_id=False, qty=1,
                      child_bom_ids=False, unfolded=False):
        if not child_bom_ids:
            child_bom_ids = []

        _logger.info("_get_pdf_line %s" % product_id)

        data = self._get_bom(bom_id=bom_id, product_id=product_id,
                             line_qty=qty)

        def get_sub_lines(bom, product_id, line_qty, line_id, level):
            data = self._get_bom(bom_id=bom.id, product_id=product_id,
                                 line_qty=line_qty, line_id=line_id,
                                 level=level)
            bom_lines = data['components']
            lines = []
            for bom_line in bom_lines:
                lines.append({
                    'name': bom_line['prod_name'],
                    'type': 'bom',
                    'quantity': bom_line['prod_qty'],
                    'uom': bom_line['prod_uom'],
                    'prod_cost': bom_line['prod_cost'],
                    'bom_cost': bom_line['total'],
                    'level': bom_line['level'],
                    'code': bom_line['code']
                })
                if bom_line['child_bom'] and (
                    unfolded or bom_line['child_bom'] in child_bom_ids):
                    line = self.env['mrp.bom.line'].browse(bom_line['line_id'])
                    lines += (get_sub_lines(line.child_bom_id, line.product_id,
                                            line.product_qty * data['bom_qty'],
                                            line, level + 1))
            if data['operations']:
                lines.append({
                    'name': _('Operations'),
                    'type': 'operation',
                    'quantity': data['operations_time'],
                    'uom': _('minutes'),
                    'bom_cost': data['operations_cost'],
                    'level': level,
                })
                for operation in data['operations']:
                    if unfolded or 'operation-' + str(bom.id) in child_bom_ids:
                        lines.append({
                            'name': operation['name'],
                            'type': 'operation',
                            'quantity': operation['duration_expected'],
                            'uom': _('minutes'),
                            'bom_cost': operation['total'],
                            'level': level + 1,
                        })
            return lines

        bom = self.env['mrp.bom'].browse(bom_id)
        product = product_id or bom.product_id or \
                  bom.product_tmpl_id.product_variant_id
        pdf_lines = get_sub_lines(bom, product, qty, False, 1)
        data['components'] = []
        data['lines'] = pdf_lines
        return data
