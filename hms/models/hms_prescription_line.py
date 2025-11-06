from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HmsPrescriptionLine(models.Model):
    _name = 'hms.prescription.line'
    _description = _('HMS Prescription Line')
    _inherit = ['mail.thread', 'mail.activity.mixin']

    prescription_id = fields.Many2one(
        'hms.prescription', string=_('Prescription'), required=True, ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product', string=_('Medicine'), required=True, domain=[('is_medicine', '=', True)]
    )
    quantity = fields.Float(string=_('Quantity'), required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string=_('Unit'))
    dosage = fields.Char(string=_('Dosage'))
    duration = fields.Char(string=_('Duration'))
    is_dispensed = fields.Boolean(string=_('Is Dispensed'), default=False)
    dispensed_date = fields.Date(string=_('Dispensed Date'))
    stock_move_id = fields.Many2one('stock.move', string=_('Stock Move'))
    

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.product_id.name} ({record.quantity} {record.uom_id.name})"
            if record.dosage:
                name += f" - {record.dosage}"
            result.append((record.id, name))
        return result


    @api.model
    def create(self, vals):
        if vals.get('is_dispensed', False):
            vals['dispensed_date'] = fields.Date.context_today(self)
        return super(HmsPrescriptionLine, self).create(vals)


