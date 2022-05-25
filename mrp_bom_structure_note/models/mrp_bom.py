# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    description = fields.Char('Description')
