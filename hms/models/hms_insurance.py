from odoo import models, fields

class HmsInsurance(models.Model):
    _name = 'hms.insurance'
    _description = 'Insurance'

    name = fields.Char(string='Insurance Company', required=True)
    plan_code = fields.Char(string='Plan Code')
    coverage = fields.Text(string='Coverage Details')
    code = fields.Char(string='Code')
    insurance_number = fields.Float(string='Insurance Number', digits=(16, 2))
    coverage_percentage = fields.Float(string='Coverage Percentage', digits=(5, 2))
    company=fields.One2many("res.partner", "insurance_id", string='insurance company')
