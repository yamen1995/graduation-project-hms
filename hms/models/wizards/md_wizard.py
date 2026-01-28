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
    medical_history = fields.Html(string='Medical History')
    disease_ids = fields.Many2many('hms.disease', string='Known Diseases')
    medication_ids = fields.Many2many('product.product', string='Medications', domain="[('is_medicine','=',True)]")

    def action_create_medical_record(self):
        self.ensure_one()
        
        record = self.env['hms.medical.record'].create({
            'patient_id': self.patient_id.id,
            'blood_type': self.blood_type,
            'allergies': self.allergies,
            'disease_ids': [(6, 0, self.disease_ids.ids)],
            'medication_ids': [(6, 0, self.medication_ids.ids)],
            'notes': self.medical_history,
        })
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