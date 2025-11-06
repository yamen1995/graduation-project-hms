from odoo import models, fields

class HmsDisease(models.Model):
    _name = 'hms.disease'
    _description = 'Disease'

    name = fields.Char(string='Disease Name', required=True)
    code = fields.Char(string='ICD-10 Code')
    description = fields.Text(string='Description')
    is_chronic = fields.Boolean(string='Chronic Disease', default=False)  # ← أضفته
