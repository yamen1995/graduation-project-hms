from odoo import models, fields, api, _

class HmsConsumableLine(models.Model):
    _name = "hms.consumable.line"
    _description = _("Consumable Line")
    _order = "id desc"

    product_id = fields.Many2one(
        "product.product",
        string=_("Product"),
        required=True,
        ondelete="restrict",
        domain=[('is_consumable', '=', True)]
      
    )
    #كود جديد
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product Template",
        related="product_id.product_tmpl_id",
        store=True,
        index=True,
        readonly=True,
    )#نهايته
    quantity = fields.Float(string=_("Quantity"), required=True, default=1.0)
    unit_price = fields.Float(string=_("Unit Price"), required=True, default=0.0)
    case_id = fields.Many2one(
        "hms.case",
        string=_("Case"),
        required=True,
        ondelete="cascade",
    )
    stock_move_id = fields.Many2one('stock.move', string=_('Stock Move'))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.unit_price = rec.product_id.lst_price or rec.product_id.list_price or 0.0