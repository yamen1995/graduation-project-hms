from odoo import models, fields, api, _

class MedicalRecordWizard(models.TransientModel):
    _name = 'medical.record.wizard'
    _description = 'Medical Record Wizard'    
    patient_id = fields.Many2one('res.partner', string='Patient', required=True,
                                 domain="[('is_patient', '=', True)]")
    name = fields.Char(string="Record ID", required=True, copy=False, readonly=True,
                       default=lambda self: 'New')
    blood_type = fields.Selection([
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ], string='Blood Type')
    allergies = fields.Text(string='Allergies')
    medical_history = fields.Text(string='Medical History')
    disease_ids = fields.Many2many('hms.disease', string='Known Diseases')

    def action_create_medical_record(self):
        self.ensure_one()
        
        record = self.env['hms.medical.record'].create({
            'patient_id': self.patient_id.id,
            'blood_type': self.blood_type,
            'allergies': self.allergies,
            'disease_ids': [(6, 0, self.disease_ids.ids)],
        })
        md_note = self.env['hms.note'].create({
            'medical_record_id': record.id,
            'note_type': 'medical_history',
            'user_id': self.env.user.id,
            'role': self.env.user.has_group('hms.group_hms_receptionist') and 'receptionist' or 'other',
        })
        if self.medical_history:
            md_note._append_note(self.medical_history)
        else:
            md_note._append_note(_("No medical history provided."))
        record.notes = [(4, md_note.id)]
        if self.env.context.get("from_appointment_id"):
            appointment = self.env["hms.appointment"].browse(self.env.context["from_appointment_id"])
            return {
                    "type": "ir.actions.act_window",
                    "res_model": "hms.case",
                    "view_mode": "form",
                    "target": "current",
                    "context": {
                        "default_medical_record_id": record.id,
                        "default_main_doctor_id": appointment.doctor_id.id if appointment.doctor_id else False,
                        "default_admission_date": appointment.date,
                        "from_appointment_id": appointment.id,
                    },
                }

    def action_close_wizard(self):
        return {'type': 'ir.actions.act_window_close'}