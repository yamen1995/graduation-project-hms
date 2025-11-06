from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    hms_role_id = fields.Many2one(
        "hms.role", string="HMS Role"
    )
    case_ids = fields.One2many(
        "hms.case", "main_doctor_id", string="Cases"
    )
    nurse_case_ids = fields.One2many(
        "hms.case", "nurse_id", string="Nurse Cases"
    )
    is_Lab_Technician = fields.Boolean(string="Is Lab Technician"
    )
    is_Doctor = fields.Boolean(string="Is Doctor", compute="_compute_role_flags"
    )
    is_Nurse = fields.Boolean(string="Is Nurse", compute="_compute_role_flags"
    )
    @api.depends('hms_role_id')
    def _compute_role_flags(self):
        for employee in self:
            role = employee.hms_role_id.code if employee.hms_role_id else ''
            employee.is_Doctor = (role == 'doctor')
            employee.is_Nurse = (role == 'nurse')

    @api.onchange('user_id', 'hms_role_id')
    def _assign_hms_groups(self):
        """Assign HMS role group to user without overwriting other groups."""
        for employee in self:
            if employee.user_id:
                base_group = self.env.ref('base.group_user')
                inventory = self.env.ref('stock.group_stock_user')
                accounting = self.env.ref('account.group_account_invoice')
                employee.user_id.group_ids = [(6, 0, [base_group.id, inventory.id, accounting.id])]
                if employee.hms_role_id and employee.hms_role_id.group_id:
                    # Replace only the HMS group, keep others
                    employee.user_id.group_ids = [(4, employee.hms_role_id.group_id.id)]
                else:
                    # Remove HMS group if no role
                    employee.user_id.group_ids = [(3, employee.hms_role_id.group_id.id)] if employee.hms_role_id else []
    @api.model
    def create(self, vals):
        """Ensure HMS group assignment on creation."""
        employee = super().create(vals)
        employee._assign_hms_groups()
        return employee

    def write(self, vals):
        """Ensure HMS group assignment on update."""
        res = super().write(vals)
        self._assign_hms_groups()
        return res


    def action_open_password_wizard(self):
        return {
            'name': 'Change Employee Password',
            'type': 'ir.actions.act_window',
            'res_model': 'change.employee.password.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_id': self.id},
        }
    def action_create_user(self):
        self.ensure_one()
        if self.user_id:
            raise ValidationError(_("This employee already has a user."))

        # if HMS role is chosen → inject groups_id defaults
        if self.hms_role_id and self.hms_role_id.group_id:
            return {
                'name': _('Create User'),
                'type': 'ir.actions.act_window',
                'res_model': 'res.users',
                'view_mode': 'form',
                'view_id': self.env.ref('hr.view_users_simple_form').id,
                'target': 'new',
                'context': dict(self._context, **{
                    'default_create_employee_id': self.id,
                    'default_name': self.name,
                    'default_phone': self.work_phone,
                    'default_mobile': self.mobile_phone,
                    'default_login': self.work_email,
                    'default_partner_id': self.work_contact_id.id,
                    'default_groups_id': [(6, 0, [
                        self.env.ref("base.group_user").id,
                        self.hms_role_id.group_id.id
                    ])]
                })
            }
        else:
            # fallback → original simple form (default Odoo logic)
            return super().action_create_user()


