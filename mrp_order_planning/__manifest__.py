# Copyright 2022 Rosen Vladimirov, BioPrint Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Mrp Order Planning',
    'summary': """
        MRP Orders planning report""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Rosen Vladimirov, BioPrint Ltd.,Odoo Community Association (OCA)',
    'website': 'https://github.com/rosenvladimirov/manufacture-reporting',
    'depends': [
        'mrp',
        'report_xlsx',
        'sale_order_variant_mgmt',
    ],
    'data': [
        'security/ir.model.access.csv',
        'reports/mrp_poduction_report_product.xml',
        'views/report_template.xml',
    ],
    'qweb': [
        'static/src/xml/mrp_production_variant_mgmt_template.xml',
    ],
    'demo': [
    ],
}
