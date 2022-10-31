# Copyright 2022 Rosen Vladimirov, BioPrint Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Mrp Order Pricing',
    'summary': """
        MRP pricing.""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Rosen Vladimirov, BioPrint Ltd.,Odoo Community Association (OCA)',
    'website': 'https://github.com/rosenvladimirov/manufacture-reporting',
    'depends': [
        'mrp',
        'purchase',
        'stock',
        'report_xlsx',
        'mrp_bom_losses',
        'mrp_bom_multi',
    ],
    'data': [
        'reports/mrp_order_pricing.xml',
        'views/report_template.xml',
        'wizards/mrp_order_pricing.xml',
    ],
    'demo': [
    ],
    'qweb': [
        'static/src/xml/mrp_order_pricing_template.xml',
    ],
}
