from odoo import models, fields, api
import math
class HmsVitalSigns(models.Model):
    _name = "hms.vital.signs"
    _description = "Vital Signs Record"
    _order = "recorded_at desc"

    case_id = fields.Many2one('hms.case', string='Case', required=True)
    medical_record_id = fields.Many2one(
        'hms.medical.record', string='Medical Record',related='case_id.medical_record_id' , required=True,
    )

    patient_id = fields.Many2one('res.partner', string='Patient',
                                  related='medical_record_id.patient_id', store=True)
    
    recorded_by = fields.Many2one("res.users", default=lambda self: self.env.user)
    recorded_at = fields.Datetime(default=lambda self: fields.Datetime.now())

    systolic_bp = fields.Integer("Systolic BP")
    diastolic_bp = fields.Integer("Diastolic BP")
    heart_rate = fields.Integer("Heart Rate")
    respiratory_rate = fields.Integer("Respiratory Rate")
    temperature = fields.Float("Temperature (°C)")
    spo2 = fields.Integer("Oxygen Saturation (%)")
    weight = fields.Float("Weight (kg)")
    height = fields.Float("Height (cm)")
    bmi = fields.Float("BMI", compute="_compute_bmi", store=True)
    blood_glucose = fields.Float("Blood Glucose (mg/dL)")
    pain_score = fields.Integer("Pain Score (0-10)")
    notes = fields.Html(
        string='Vital Note', store=True, readonly=False,
    )

    @api.depends('weight', 'height')
    def _compute_bmi(self):
        for rec in self:
            if rec.weight and rec.height:
                h = rec.height / 100  # cm → meters
                rec.bmi = round(rec.weight / (h * h), 1)
            else:
                rec.bmi = 0
class HmsConsultation(models.Model):
    _name = "hms.consultation"
    _description = "Doctor Consultation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "recorded_at desc"

    case_id = fields.Many2one('hms.case', string='Case', required=True)
    medical_record_id = fields.Many2one(
        'hms.medical.record', string='Medical Record',related='case_id.medical_record_id' , required=True,
    )

    patient_id = fields.Many2one('res.partner', string='Patient',
                                  related='medical_record_id.patient_id', store=True)
    
    recorded_by = fields.Many2one("res.users", default=lambda self: self.env.user)
    recorded_at = fields.Datetime(default=lambda self: fields.Datetime.now())
    notes = fields.Html(
        string='Consultation', store=True, readonly=False,
    )