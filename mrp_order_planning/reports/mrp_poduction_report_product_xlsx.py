# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class ReportMrpProductionVariantXlsx(models.TransientModel):
    _name = 'report.mp_vp.report_report_report_mrp_product_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        # _logger.info("XLS %s:%s::%s" % (data, self._context, objs))
        order_id = data.get('order_id')
        if not order_id:
            order_id = self._context.get('order_id')
        objs = self.env['mrp.production'].browse(order_id)
        doc, headers, sub_headers, footer, pages = self.env['mrp.production.report.product'].get_cross_table(objs)
        if not data:
            data = {}
        data.update({
            'headers': headers,
            'sub_headers': sub_headers,
            'count_sub_headers': len(sub_headers),
            'footers': footer,
            'pages': pages,
            'variants': doc,
        })
        self._define_formats(workbook)
        for ws_params in self._get_ws_params(workbook, data, objs):
            ws_name = ws_params.get('ws_name')
            ws_name = self._check_ws_name(ws_name)
            ws = workbook.add_worksheet(ws_name)
            generate_ws_method = getattr(
                self, ws_params['generate_ws_method'])
            generate_ws_method(workbook, ws, ws_params, data, objs)

    def _get_ws_params(self, wb, data, objects):

        mrp_production_product_template = {
            '1_first': {
                'header': {
                    'value': data['headers'][0],
                },
                # 'data': {
                #     'value': data['headers'][0],
                # },
                'width': 36,
            },
            # '2_group': {
            #     'header': {
            #         'value': data['headers'][1],
            #     },
            #     'data': {
            #         'value': data['headers'][1],
            #     },
            #     'width': 36,
            # },
        }
        inx = 1
        for line in data['sub_headers']:
            field_name = '%s_%s' % (inx, line)
            mrp_production_product_template.update({
                field_name: {
                    'header': {
                        'value': line,
                    },
                    # 'data': {
                    #     'value': line,
                    #     'format': self.format_tcell_amount_conditional_right,
                    # },
                    'width': 18,
                },
            })
            inx += 1

        ws_params = {
            'ws_name': 'Sale Order Variant Report',
            'generate_ws_method': '_mrp_production_variants_report',
            'title': 'Mrp Production Variant Report',
            'wanted_list': [k for k in sorted(
                mrp_production_product_template.keys())],
            'col_specs': mrp_production_product_template,
        }
        return [ws_params]

    def _mrp_production_variants_report(self, wb, ws, ws_params, data, objects):

        ws.set_portrait()
        ws.fit_to_pages(1, 0)
        ws.set_header(self.xls_headers['standard'])
        ws.set_footer(self.xls_footers['standard'])

        self._set_column_width(ws, ws_params)

        row_pos = 0
        col = 1
        # row_pos = self._write_ws_title(ws, row_pos, ws_params, True)
        # row_pos += 2
        ws.merge_range(row_pos, 0, row_pos+1, 0, data['headers'][0], self.format_theader_blue_left)
        ws.merge_range(row_pos, 1, row_pos, data['count_sub_headers']+1, data['headers'][1], self.format_theader_blue_center)

        row_pos += 1
        for header in data['sub_headers']:
            ws.write(row_pos, col, header, self.format_theader_blue_center)
            col += 1
        row_pos += 1
        for page in data['variants']:
            for k, v in page.items():
                ws.merge_range(row_pos, 0, row_pos, data['count_sub_headers'], k.name, self.format_theader_blue_center)
                row_pos += 1
                for key, value in v.items():
                    _logger.info("line %s-%s" % (key, value))
                    ws.write(row_pos, 0, isinstance(key, str) and key or key.name, self.format_theader_blue_center)
                    col = 1
                    for field_name in data['sub_headers']:
                        ws.write(row_pos, col, value[field_name], self.format_theader_blue_amount_right)
                        col += 1
                    row_pos += 1

