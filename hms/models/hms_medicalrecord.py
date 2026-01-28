from odoo import models, fields, api
class HmsMedicalRecord(models.Model):
    _name = 'hms.medical.record'
    _description = "Patient's Medical Record"

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
    disease_ids = fields.Many2many('hms.disease', string='Known Diseases')
    case_ids = fields.One2many('hms.case', 'medical_record_id', string='Cases')
    notes = fields.Html(string='Notes')
    patient_phone = fields.Char(related="patient_id.phone", string="Phone", store=True)
    patient_email = fields.Char(related="patient_id.email", string="Email", store=True)
    patient_age = fields.Integer( string="Age", store=True)
    medication_ids = fields.Many2many('product.product', string='Medications' , domain="[('is_medicine','=',True)]")
    _sql_constraints = [
        ('unique_patient_record', 'unique(patient_id)', 'Each patient can only have one medical record!')
    ]

    @api.model
    def create(self, vals):
        recs = super(HmsMedicalRecord, self).create(vals)
        for rec in recs:
            if rec.name == 'New':
                patient = rec.patient_id
                rec.name = f"MR/{patient.name or ''}"
        return recs