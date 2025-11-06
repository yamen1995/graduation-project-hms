from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Patient-related
    is_patient = fields.Boolean(string="Is Patient")
    is_insurance_company = fields.Boolean(string="Is Insurance Company")

    birthdate = fields.Date(string="Birthdate")
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender")

    insurance_id = fields.Many2one(
        "hms.insurance", string="Insurance Company"
    )

    medical_record_id = fields.One2many(
        "hms.medical.record", "patient_id", string="Medical Record"
    )

    # Computed: is this partner linked to an employee (staff)?
    is_staff = fields.Boolean(
        string="Is Staff Member", compute="_compute_is_staff", store=True
    )
    medical_case_ids = fields.One2many(
        related='medical_record_id.case_ids',
        string='Medical Cases',
        readonly=True,
    )

    show_create_medical_record = fields.Boolean(
        compute='_compute_show_create_medical_record',
        store=False
    )

    emergency_contact_id = fields.Many2one(
        "res.partner", string="Emergency Contact"
    )
    emergency_phone = fields.Char(string="Emergency Phone")
    emergency_relation = fields.Char(string="Relation to Patient")
    outsider_patient = fields.Boolean(string="Outsider Patient",
                                      help="Patient registered through the registration page")
    

    def _compute_is_staff(self):
        for partner in self:
            # Count employees linked to this partner AND having an HMS role
            partner.is_staff = bool(
                self.env['hr.employee'].search_count([
                    ('address_id', '=', partner.id),
                    ('hms_role_id', '!=', False)
                ])
            )
    @api.constrains("medical_record_id")
    def _check_one_medical_record(self):
        """Ensure each patient has at most one medical record."""
        for partner in self:
            if len(partner.medical_record_id) > 1:
                raise ValidationError(_("A patient can only have one medical record."))

    def action_open_medical_wizard(self):
        self.ensure_one()
        self.outsider_patient = False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Medical Record',
            'res_model': 'medical.record.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_patient_id': self.id},
        }
        
    


    @api.depends('is_patient', 'medical_record_id')
    def _compute_show_create_medical_record(self):
        for partner in self:
            partner.show_create_medical_record = (
                (partner.is_patient and not partner.medical_record_id
                 and (self.env.user.has_group('hms.group_hms_receptionist') or self.env.user.has_group('base.group_system')))
            )

    def action_grant_portal_access(self):
        """Open wizard to create portal access for this patient."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grant Portal Access'),
            'res_model': 'grant.portal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_patient_id': self.id},
        }

    def action_schedule_appointment(self):
        """Open appointment creation form for this patient."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Appointment'),
            'res_model': 'hms.appointment',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_patient_id': self.id},
        }

    def action_start_hospital_visit(self):
        """Open hospital case creation form for this patient."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Start Hospital Visit'),
            'res_model': 'hms.case',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_patient_id': self.id},
        }
    can_edit_patient = fields.Boolean(string="Can Edit Patient Info", compute="_compute_can_edit_patient")  

    @api.depends('is_patient', 'medical_record_id')
    def _compute_can_edit_patient(self):
        for partner in self:
            partner.can_edit_patient = (
                partner.is_patient and
                (self.env.user.has_group('hms.group_hms_receptionist') or self.env.user.has_group('base.group_system')))
            

    def send_patient_email(self, subject, message):
        """Send email to patient using the configured template"""
        if not self.email:
            raise UserError(_('Patient email address is not set!'))

        template = self.env.ref('hms.hms_patient_email_template')

        template.send_mail(
            self.id,
            force_send=True,
            email_values={
                'subject': subject,
                'body_html': message,
                'email_to': self.email,
            }
        )
        