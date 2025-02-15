# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import models
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class ReportMrpProductMaterialsXlsx(models.TransientModel):
    _name = 'report.mp_cm.report_mrp_product_materials_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def _get_objs_for_report(self, docids, data):
        # active_model = self._context['active_model']
        if data.get('production_ids', False):
            docids = data['production_ids']
        return self.env['mrp.consumption']. \
            with_context(dict(self._context, active_model='mrp.production',
                              active_ids=docids,
                              sale_order_line_ids=data.get('sale_order_line_ids', False))).create({})

    # def generate_xlsx_report(self, workbook, data, objs):
    #     # _logger.info("XLS %s:%s::%s" % (data, self._context, objs))
    #     docids = []
    #     if data.get('production_ids', False):
    #         docids = data['production_ids']
    #     self.env['mrp.consumption'].\
    #         with_context(dict(self._context, active_model='mrp.production', active_ids=docids)).create({})

    def _get_ws_params(self, wb, data, objects):

        mrp_production_materials_template = {
            '1_number': {
                'header': {
                    'value': '#',
                },
                'data': {
                    'value': self._render('n'),
                },
                'width': 12,
            },
            '2_material_name': {
                'header': {
                    'value': 'Material Name',
                },
                'data': {
                    'value': self._render('material_name'),
                },
                'width': 36,
            },
            '3_product_uom': {
                'header': {
                    'value': 'UOM',
                },
                'data': {
                    'value': self._render('product_uom'),
                },
                'width': 10,
            },
            '4_product_uom_qty': {
                'header': {
                    'value': 'Quantity',
                },
                'data': {
                    'value': self._render('product_uom_qty'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
            '5_exclude_product_uom_qty': {
                'header': {
                    'value': 'Total quantity',
                },
                'data': {
                    'value': self._render('exclude_product_uom_qty'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
            '6_transfers_quantity': {
                'header': {
                    'value': 'Special Transferred quantity',
                },
                'data': {
                    'value': self._render('transfers_quantity'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
            '7_real_product_uom_qty': {
                'header': {
                    'value': 'Rest quantity',
                },
                'data': {
                    'value': self._render('real_product_uom_qty'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
        }
        l1_mrp_production_materials_template = {
            '1_dates': {
                'data': {
                    'value': self._render('dates'),
                },
                'colspan': 7,
            },
        }
        l2_mrp_production_materials_template = {
            '1_raw_picking': {
                'data': {
                    'value': self._render('raw_picking'),
                },
                'colspan': 7,
            },
        }
        format_tcell_left = self.format_tcell_left
        format_tcell_left.set_text_wrap()
        l3_mrp_production_materials_template = {
            '1_number': {
                'data': {
                    'value': self._render('n'),
                },
                'width': 12,
            },
            '2_production_id': {
                'data': {
                    'value': self._render('production_id'),
                },
                'width': 36,
                'format': format_tcell_left,
            },
            '3_product_uom': {
                'data': {
                    'value': self._render('product_uom'),
                },
                'width': 10,
            },
            '4_product_uom_qty': {
                'data': {
                    'value': self._render('product_uom_qty'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
            '5_reserved_availability': {
                'data': {
                    'value': self._render('reserved_availability'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
            '6_quantity_done': {
                'data': {
                    'value': self._render('quantity_done'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
            '7_initial': {
                'data': {
                    'value': self._render('initial'),
                },
                'width': 10,
                'format': self.format_tcell_right,
            },
        }
        ws_params = {
            'ws_name': 'Manufacture material consumption',
            'generate_ws_method': '_mrp_production_variants_report',
            'title': 'Mrp Production Variant Report',
            'wanted_list': [k for k in sorted(
                mrp_production_materials_template.keys())],
            'col_specs': mrp_production_materials_template,
            'sub_levels': [{
                'wanted_list': [k for k in sorted(
                    l1_mrp_production_materials_template.keys())],
                'col_specs': l1_mrp_production_materials_template
            }, {
                'wanted_list': [k for k in sorted(
                    l2_mrp_production_materials_template.keys())],
                'col_specs': l2_mrp_production_materials_template
            }, {
                'wanted_list': [k for k in sorted(
                    l3_mrp_production_materials_template.keys())],
                'col_specs': l3_mrp_production_materials_template
            },
            ],
        }
        return [ws_params]

    def _mrp_production_variants_report(self, wb, ws, ws_params, data, objects):

        ws.set_portrait()
        ws.fit_to_pages(1, 0)
        ws.set_header(self.xls_headers['standard'])
        ws.set_footer(self.xls_footers['standard'])

        self._set_column_width(ws, ws_params)

        row_pos = 0
        row_pos = self._write_ws_title(ws, row_pos, ws_params, True)

        for o in objects:
            ws.write_row(
                row_pos, 0, ['Date', 'Partner'],
                self.format_theader_blue_center)
            ws.write_row(
                row_pos + 1, 0, [o.date or ''], self.format_tcell_date_center)
            if o.destination_location_id.out_partner_id:
                ws.write_row(
                    row_pos + 1, 1,
                    [o.destination_location_id.out_partner_id.display_name],
                    self.format_tcell_center)

            row_pos += 3
            row_pos = self._write_line(
                ws, row_pos, ws_params, col_specs_section='header',
                default_format=self.format_theader_blue_center)
            ws.freeze_panes(row_pos, 0)

            total = 0.00
            for count, line in enumerate(o.stock_move_location_line_ids):
                row_pos = self._write_line(
                    ws, row_pos, ws_params, col_specs_section='data',
                    render_space={
                        'n': count + 1,
                        'material_name': line.product_id.display_name or '',
                        'product_uom': line.product_uom.display_name or '',
                        'product_uom_qty': line.product_uom_qty or 0.00,
                        'exclude_product_uom_qty': line.exclude_product_uom_qty or 0.00,
                        'transfers_quantity': line.transfers_quantity or 0.00,
                        'real_product_uom_qty': line.real_product_uom_qty or 0.00,
                    },
                    default_format=self.format_tcell_left)
                if line.move_ids:
                    # first level
                    dates = {}
                    for raw_move_line in line.move_ids:
                        for raw_sale_order_line in raw_move_line.raw_material_production_id.sale_line_ids:
                            for requested_date in raw_sale_order_line.requested_date_ids:
                                dates[requested_date.date_confirmed] = raw_sale_order_line.product_uom_qty
                    if dates:
                        l1_ws_params = ws_params['sub_levels'][0]
                        row_pos = self._write_line(
                            ws, row_pos, l1_ws_params, col_specs_section='data',
                            render_space={
                                'dates': '%s' % ' '.join(['[%s => %s]' % (v, k) for k, v in dates.items()]),
                            },
                            default_format=self.format_tcell_left)
                    # second level
                    if line.picking_ids:
                        l2_ws_params = ws_params['sub_levels'][1]
                        row_pos = self._write_line(
                            ws, row_pos, l2_ws_params, col_specs_section='data',
                            render_space={
                                'raw_picking':
                                    '%s' % ' '.join([raw_picking.display_name for raw_picking in line.picking_ids]),
                            },
                            default_format=self.format_tcell_left)
                    # third level
                    l3_ws_params = ws_params['sub_levels'][2]
                    for l3_count, raw_move_line in enumerate(line.move_ids):
                        dates = []
                        for raw_sale_order_line in raw_move_line.raw_material_production_id.sale_line_ids:
                            dates = dates+[x.date_confirmed for x in raw_sale_order_line.requested_date_ids]
                        production_id = '(%s) %s [%s] %s::%s*%s=%s' % (raw_move_line.raw_material_production_id.state,
                                                                       raw_move_line.raw_material_production_id.display_name,
                                                                       dates and ' '.join(dates) or '', raw_move_line.raw_material_production_id.product_qty,
                                                                       raw_move_line.raw_material_production_id.product_qty,raw_move_line.unit_factor,
                                                                       float_round(raw_move_line.unit_factor*raw_move_line.raw_material_production_id.product_qty,
                                                                                   raw_move_line.product_uom.rounding))
                        production_id += "\n"
                        production_id += raw_move_line.operation_id.display_name
                        if raw_move_line.bom_line_id.description:
                            production_id += "\n"
                            production_id += raw_move_line.bom_line_id.description
                        production_id += "\n"
                        production_id += raw_move_line.raw_material_production_id.product_id.display_name
                        production_id += "\n"
                        production_id += raw_move_line.raw_material_production_id.product_id.product_tmpl_id.name
                        production_id += "\n"
                        production_id += raw_move_line.product_id.display_name
                        production_id += "\n"
                        production_id += raw_move_line.raw_material_production_id.bom_id.display_name
                        # _logger.info("LINE %s" % production_id)
                        default_format = self.format_tcell_left
                        # default_format.set_shrink()
                        row_pos = self._write_line(
                            ws, row_pos, l3_ws_params, col_specs_section='data',
                            render_space={
                                'n': "%s.%s" % (count + 1, l3_count + 1),
                                'production_id': production_id,
                                'product_uom': raw_move_line.product_uom.display_name,
                                'product_uom_qty': raw_move_line.product_uom_qty,
                                'reserved_availability': raw_move_line.reserved_availability,
                                'quantity_done': raw_move_line.quantity_done,
                                'initial': float_round(raw_move_line.unit_factor*
                                                       raw_move_line.raw_material_production_id.product_qty,
                                                       raw_move_line.product_uom.rounding),
                            },
                            default_format=default_format)
                total += line.real_product_uom_qty

            ws.write(row_pos, 6, total, self.format_theader_blue_amount_right)
