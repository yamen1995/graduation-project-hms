from odoo import models, fields, _

class StockLocation(models.Model):
    _inherit = 'stock.location'

    is_pharmacy = fields.Boolean(string=_('Is Pharmacy'), default=False,
                               help=_('Check this box if this location is used as a pharmacy storage'))