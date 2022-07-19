# Copyright 2022 Rosen Vladimirov, BioPrint Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Mrp Report Materials',
    'summary': """
        MRP report for consumpted materials from orders.""",
    'version': '11.0.1.0.1',
    'license': 'AGPL-3',
    'author': 'Rosen Vladimirov, BioPrint Ltd.,Odoo Community Association (OCA)',
    'website': 'https://github.com/rosenvladimirov/manufacture-reporting',
    'depends': [
        'stock',
        'mrp',
        'l10n_bg_extend',
    ],
    'data': [
        'security/ir.model.access.csv',
        'reports/mrp_production_material.xml',
        'views/report_template.xml',
    ],
    'qweb': [
        'static/src/xml/mrp_production_materials_template.xml',
    ],
    'demo': [
    ],
}
