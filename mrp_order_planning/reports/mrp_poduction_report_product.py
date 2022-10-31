# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, tools, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class MrpReportPlanningProductAbstract(models.TransientModel):
    _name = 'mrp.planning'
    _description = 'Manufacture variant planning report abstract'

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
    production_ids = fields.Many2many(
        comodel_name='mrp.production',
        string='Productions',
    )

    @api.model
    def default_get(self, fields_list):
        res = super(MrpReportPlanningProductAbstract, self).default_get(fields_list)
        production_ids = res.get('production_ids', False) and res['production_ids'][0][2]
        if not production_ids:
            production_ids = self._context.get('production_ids')
        productions = self.env['mrp.production'].browse(production_ids)
        res['production_ids'] = [(6, False, productions.ids)]
        res['origin'] = '-'.join([x.name for x in productions])
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1)
        manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        if warehouse:
            res['origin_location_id'] = warehouse.lot_stock_id.id
        if not res.get('destination_location_id'):
            res['destination_location_id'] = productions[0].location_dest_id.id
        res['partner_id'] = productions[0].location_dest_id.partner_id \
                            and productions[0].location_dest_id.partner_id.id or False
        return res

    def get_html(self, given_context=None):
        context = dict(self._context)
        if given_context is None:
            given_context = context
        production_ids = given_context.get('production_ids')
        docs = self.env['mrp.production'].browse(production_ids)
        doc, headers, sub_headers, footer, pages = self.env['mrp.production.report.product'].get_cross_table(docs)
        rcontext = {
            'doc_ids': self.ids,
            'doc_model': 'mrp.production',
            'docs': self,
            'variants': doc,
            'headers': headers,
            'sub_headers': sub_headers,
            'count_sub_headers': len(sub_headers) + 1,
            'footers': footer,
            'pages': pages,
            'orders': docs,
            'env': self.env,
            'print_pdf': False,
            'context_timestamp': lambda t: fields.Datetime.context_timestamp(self.with_context(tz=self.env.user.tz), t),
        }
        result = {
            'html': self.env.ref('mrp_order_planning.report_mrp_variant_base').with_context(context).render(rcontext)
        }
        # _logger.info("ORDER get_html %s\n:%s\n%s\n%s" % (order_id, self._context, rcontext, result))
        return result

    @api.multi
    def print_report(self, report_type='qweb-pdf', given_context=None):
        # self.ensure_one()
        context = dict(self.env.context)
        if given_context is None:
            given_context = context
        # _logger.info('PRINT REPORT %s:%s:%s' % (context, report_type, report_sub_type))
        if report_type == 'xlsx':
            # order_id = self._context.get('order_id')
            # docs = self.env['sale.order'].browse(order_id)
            action = self.env.ref('mrp_order_planning.action_mrp_order_planning_report_xlsx')
            return action.with_context(context).report_action(self, data={
                'production_ids': given_context.get('active_ids')
            })
        else:
            action = self.env.ref('mrp_order_planning.action_mrp_order_planning_qweb')
            return action.with_context(context).report_action(self, data={
                'print_pdf': True,
                'production_ids': given_context.get('active_ids'),
            })

    def get_buttons(self, given_context=None):
        retr = []
        retr.append({'name': _('Print'), 'action': 'print_report', 'data_id': False, 'ttype': 'qweb-pdf'})
        retr.append({'name': _('Export'), 'action': 'print_report', 'data_id': False, 'ttype': 'xlsx'})
        return retr


class MrpProductReportProductAbstract(models.AbstractModel):
    _name = 'report.mrp_order_planning.mrp_variant'

    # _description = 'Sale order report variants abstract'

    @api.model
    def get_report_values(self, docids, data=None):
        production_ids = False
        if data:
            production_ids = data.get('production_ids')
        if not production_ids:
            production_ids = self._context.get('production_ids')
        if not production_ids:
            production_ids = docids
        _logger.info("ORDER get_report_values order_id=>%s\n:_context=>%s\n::data=>%s\n::docids=>%s" % (
            production_ids, self._context, data, docids))

        if not production_ids:
            return {
                'doc_ids': docids,
                'doc_model': 'mrp.production',
                'env': self.env,
                'context_timestamp': lambda t: fields.Datetime.context_timestamp(self.with_context(tz=self.env.user.tz),
                                                                                 t),
            }
        report = self.env[self._context['active_model']].browse(self._context['active_id'])
        # docs = self.env['mrp.production'].browse(production_ids)
        # _logger.info("DOCS %s:%s" % (docs, report and report.production_ids))
        doc, headers, sub_headers, footer, pages = self.env['mrp.production.report.product'].\
            get_cross_table(report.production_ids)
        # _logger.info("RESULT %s::%s" % (docids, data))
        return {
            'doc_ids': report.ids,
            'doc_model': 'mrp.production',
            'docs': report,
            'data': data,
            'variants': doc,
            'headers': headers,
            'sub_headers': sub_headers,
            'count_sub_headers': len(sub_headers) + 1,
            'footers': footer,
            'pages': pages,
            'orders': report.production_ids,
            'env': self.env,
            'print_pdf': True,
        }


class MrpProductionReportProduct(models.AbstractModel):
    _name = 'mrp.production.report.product'
    _description = 'MRP Production group by variants'
    _auto = False
    _rec_name = 'date'
    _order = 'date desc'

    production_id = fields.Many2one('mrp.production', 'Manufacturing Order', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    date = fields.Datetime('Order date', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', readonly=True)
    name = fields.Char('Attribute Value', readonly=True)
    # key = fields.Char('Key')
    product_uom_qty = fields.Float('Quantity', readonly=True)
    attribute_product_uom_qty = fields.Float('Attribute Quantity', readonly=True)
    attribute_id = fields.Many2one('product.attribute', 'Attribute')
    attribute_value_id = fields.Many2one('product.attribute.value', 'Attribute value')
    state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('planned', 'Planned'),
        ('progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)

    def get_report_header(self, order_id):
        values = self.env['product.attribute.value']
        products = order_id.mapped('product_id')
        for product in products:
            for line in product.attribute_value_ids:
                if product.product_tmpl_id.attribute_line_ids.filtered(lambda r:
                                                                       r.type_attribute == 'col'
                                                                       and r.attribute_id == line.attribute_id):
                    values |= line
        return sorted([x for x in values.with_context(lang=None).mapped('name')], key=lambda r: r)

    def _where_report(self):
        sql = ""
        return sql

    def get_cross_table(self, order_id):
        res = [{}]
        pages = [False]
        footer = {'Total': 0.0}
        values = self.env['product.attribute.value']
        rows = self.env['product.attribute.value']
        others = self.env['product.attribute.value']
        sequence_others = {}
        products = order_id.mapped('product_id')
        for product in products:
            sequence_others[product] = 0
            inx = 0
            for line in product.attribute_value_ids.sorted(lambda r: r.attribute_id.sequence):
                inx += 1
                if product.product_tmpl_id.attribute_line_ids.filtered(lambda r:
                                                                       r.type_attribute == 'col'
                                                                       and r.attribute_id == line.attribute_id):
                    values |= line
                if product.product_tmpl_id.attribute_line_ids.filtered(lambda r:
                                                                       r.type_attribute == 'row'
                                                                       and r.attribute_id == line.attribute_id):
                    rows |= line
                if product.product_tmpl_id.attribute_line_ids.filtered(lambda r:
                                                                       not r.type_attribute
                                                                       and r.attribute_id == line.attribute_id):
                    others |= line
                    if inx <= 2:
                        sequence_others[product] = inx
        # regexp_replace(name, '[^0-9\.]+', '', 'g')
        sql = """SELECT * FROM crosstab($$SELECT
dense_rank() OVER (ORDER BY sr.product_id)::int AS row_name,
sr.product_id,
string_agg(DISTINCT  vr.sequence::int || '+' || vr.name::varchar, ';') AS key,
sr.name,
sum(coalesce(product_qty, 0.0)) AS product_uom_qty
FROM mrp_production_report_product AS sr
LEFT JOIN sale_report_variant_product AS vr
    ON sr.product_id = vr.product_id WHERE production_id = ANY (%s) """ + self._where_report() + """GROUP BY sr.product_id, sr.name
ORDER BY 2,3$$, $$VALUES %s$$""" % ",".join(["('%s')" % x.name for x in values]) + \
              ") AS t (%s)" % 'row_no int,product_id int,key varchar,%s' % ",".join(
            ['"%s" float' % x.name for x in values])
        _logger.info("SQL %s" % sql)
        self.env.cr.execute(sql, (order_id.ids,))
        result = self.env.cr.dictfetchall()
        for line in result:
            line['product_id'] = self.env['product.product'].browse(line['product_id'])
        for line in sorted(result, key=lambda r: "%s-%s" % (r['product_id'].id, r['key'])):
            line_new = dict(line)
            line_new.pop('product_id')

            for row in rows:
                if set(line['product_id'].attribute_value_ids.ids) & set([row.id]):
                    if len(line['key'].split(';')) > 2:
                        other = line['key'].split(';')[-1]
                        other = other.split('+')[1]
                    else:
                        other = 'none'
                    # _logger.info("KEY: %s & %s = %s" % (line['product_id'].attribute_value_ids.ids, [row.id], line_new))
                    if not res[0].get(line['product_id'].product_tmpl_id):
                        res[0][line['product_id'].product_tmpl_id] = {}
                    if not res[0][line['product_id'].product_tmpl_id].get(other):
                        res[0][line['product_id'].product_tmpl_id][other] = {}

                    if not res[0][line['product_id'].product_tmpl_id][other].get(row):
                        res[0][line['product_id'].product_tmpl_id][other][row] = {}
                    if not res[0][line['product_id'].product_tmpl_id][other][row].get('Total'):
                        res[0][line['product_id'].product_tmpl_id][other][row]['Total'] = 0.0
                    for key, value in line_new.items():
                        if key in ['row_no', 'key']:
                            continue
                        # _logger.info("KEY %s=%s" % (key, value))
                        if not res[0][line['product_id'].product_tmpl_id][other][row].get(key):
                            res[0][line['product_id'].product_tmpl_id][other][row][key] = 0.0
                        if not value:
                            value = 0.0
                        # _logger.info("KEY %s::%s" % (res[0][line['product_id'].product_tmpl_id][row][key], value))
                        res[0][line['product_id'].product_tmpl_id][other][row][key] += value
                        if not footer.get(key):
                            footer[key] = 0.0
                        footer[key] += value
                        res[0][line['product_id'].product_tmpl_id][other][row]['Total'] += value
                        footer['Total'] += value
        # _logger.info("RES %s" % res)
        headers = [rows[0].attribute_id.name] + [values[0].attribute_id.name]
        sub_headers = self.get_report_header(order_id) + ['Total']
        # _logger.info("RESULT %s:::%s" % (result, headers))
        return [res], headers, sub_headers, footer, pages

    # pa.attribute_id,
    # pa_pp.product_attribute_value_id AS attribute_value_id

    def _select(self):
        sql = """SELECT mp.product_id as product_id,
    pa.name,
    mp.product_qty/(SELECT COUNT(id) FROM product_attribute_line cpl WHERE cpl.product_tmpl_id = pp.product_tmpl_id) as product_qty,
    mp.product_qty as attribute_product_qty,
    mp.id AS production_id,
    mp.date_planned_start AS date,
    mp.state,
    pp.product_tmpl_id AS product_tmpl_id,
    mp.company_id AS company_id,
    pa.attribute_id,
    pa_pp.product_attribute_value_id AS attribute_value_id,
    mp.id as id
"""
        return sql

    def _from(self):
        sql = """mrp_production AS mp
LEFT JOIN product_product AS pp
    ON mp.product_id = pp.id
INNER JOIN product_attribute_value_product_product_rel AS pa_pp
    ON pa_pp.product_product_id = mp.product_id
INNER JOIN product_attribute_value AS pa
    ON pa_pp.product_attribute_value_id = pa.id
LEFT JOIN product_attribute_line AS pl
    ON pl.product_tmpl_id = pp.product_tmpl_id AND pl.attribute_id = pa.attribute_id
"""
        return sql

    def _group_by(self):
        sql = """mp.product_id, pa.name
        """
        return sql

    def _order_by(self):
        sql = """mp.product_id
        """
        return sql

    @api.model_cr
    def init(self):
        # self._table = sale_report_product
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s FROM %s)""" % (
            self._table, self._select(), self._from(),))
