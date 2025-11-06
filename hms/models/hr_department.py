from odoo import models, fields

class HrDepartment(models.Model):
    _inherit = "hr.department"

    is_hospital = fields.Boolean(string="Hospital Department", default=False)