from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GrantPortalWizard(models.TransientModel):
    _name = "grant.portal.wizard"
    _description = "Grant Portal Access Wizard"

    patient_id = fields.Many2one("res.partner", string="Patient", required=True)
    email = fields.Char(related="patient_id.email", readonly=False)
    login = fields.Char(string="Login", required=True)
    password = fields.Char(string="Password", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        patient_id = self.env.context.get("default_patient_id")
        if patient_id:
            patient = self.env["res.partner"].sudo().browse(patient_id)
            res.update({
                "patient_id": patient.id,
                "login": patient.email or patient.phone or f"user_{patient.id}"
            })
        return res

    def action_create_user(self):
        self.ensure_one()
        if self.patient_id.user_ids:
            raise UserError(_("This patient already has a portal user."))
        self.patient_id.sudo().signup_prepare()

        portal_group = self.env.ref("base.group_portal")
        user = self.env['res.users'].sudo().create({
            "name": self.patient_id.name,
            "login": self.login,
            "password": self.password,
            "partner_id": self.patient_id.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "res.users",
            "view_mode": "form",
            "res_id": user.id,
        }
