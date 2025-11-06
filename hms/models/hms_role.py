from odoo import models, fields
class HmsRole(models.Model):
    _name = "hms.role"
    _description = "Hospital System Role"

    name = fields.Char(string="Role Name", required=True)
    code = fields.Char(string="Role Code", required=True)
    group_id = fields.Many2one(
        "res.groups", string="Security Group",
        help="Link to Odoo security group for access control"
    )
    job_id = fields.Many2one(
        "hr.job", string="Job Position",
        help="Link to the job position associated with this role"
    )