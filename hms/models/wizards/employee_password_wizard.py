from odoo import models, fields, api, Command

class ChangeEmployeePasswordWizard(models.TransientModel):
    _name = "change.employee.password.wizard"
    _description = "Change Employee User Password"

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    new_password = fields.Char(string="New Password", required=True, password=True)


    def action_change_user_password(self):
        """ Change the password of the user linked to this employee """
        self.ensure_one()
        if not self.employee_id.user_id:
            return False  # no linked user
        
        # Create wizard record programmatically
        wizard = self.env['change.password.wizard'].create({
            'user_ids': [
                Command.create({
                    'user_id': self.employee_id.user_id.id,
                    'user_login': self.employee_id.user_id.login,
                    'new_passwd': self.new_password  # optional if wizard supports it
                })
            ]
        })
        # Trigger the password change
        wizard.change_password_button()
        return True