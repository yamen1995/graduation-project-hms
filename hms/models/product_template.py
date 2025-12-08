from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_consumable = fields.Boolean(string="Is Consumable")
    is_lab_test = fields.Boolean(string="Is Lab Test")
    is_medicine = fields.Boolean(string="Is Medicine")
    danger_disease_ids = fields.Many2many(
        "hms.disease",
        "medicine_danger_disease_rel",    
        "product_id",                     
        "disease_id",                     
        string="Contraindicated Diseases",
        help="Diseases that make this medicine unsafe."
    )
    cautiuse_disease_ids = fields.Many2many(
        "hms.disease",
        "medicine_caution_disease_rel",
        "product_id",
        "disease_id",
        string="Caution Diseases",
        help="Diseases requiring special caution with this medicine."
    )
    interfering_medication_ids = fields.Many2many(
        'product.product', string="Interfering Medications",
    )

    @api.constrains('is_medicine', 'is_lab_test')
    def _check_is_medicine_and_lab_test_mutually_exclusive(self):
        for record in self:
            if record.is_medicine and record.is_lab_test:
                raise ValidationError(_("A product cannot be both a Medicine and a Lab Test."))

    