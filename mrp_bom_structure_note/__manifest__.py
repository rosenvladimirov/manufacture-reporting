# Copyright 2022 Rosen Vladimirov, BioPrint Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Mrp Bom Structure Note',
    'summary': """
        Add description in bom line row""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Rosen Vladimirov, BioPrint Ltd.,Odoo Community Association (OCA)',
    'website': 'https://github.com/rosenvladimirov/manufacture-reporting',
    'depends': [
        'mrp',
        'project_mrp',
    ],
    'data': [
        'views/mrp_bom_view.xml',
        'views/report_project_bom_views.xml',
    ],
    'demo': [
    ],
}
