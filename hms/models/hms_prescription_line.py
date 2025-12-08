from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HmsPrescriptionLine(models.Model):
    _name = 'hms.prescription.line'
    _description = _('HMS Prescription Line')
    _inherit = ['mail.thread', 'mail.activity.mixin']

    prescription_id = fields.Many2one(
        'hms.prescription', string=_('Prescription'), required=True, ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product', string=_('Medicine'), required=True, domain=[('is_medicine', '=', True)]
    )
    quantity = fields.Float(string=_('Quantity'), required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string=_('Unit'))
    dosage = fields.Char(string=_('Dosage'))
    duration = fields.Char(string=_('Duration'))
    is_dispensed = fields.Boolean(string=_('Is Dispensed'), default=False)
    dispensed_date = fields.Date(string=_('Dispensed Date'))
    stock_move_id = fields.Many2one('stock.move', string=_('Stock Move'))
    
    

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.product_id.name} ({record.quantity} {record.uom_id.name})"
            if record.dosage:
                name += f" - {record.dosage}"
            result.append((record.id, name))
        return result
    @api.onchange('product_id')
    def _onchange_product_diseases(self):
        if not self.product_id or not self.prescription_id:
            return

        patient_diseases = self.prescription_id.case_id.medical_record_id.disease_ids
        patient_medications = self.prescription_id.case_id.medical_record_id.medication_ids

        # 1. Danger = contraindicated → block selection
        dangerous = self.product_id.danger_disease_ids
        common_danger = dangerous & patient_diseases
        if common_danger:
            names = ", ".join(common_danger.mapped("name"))
            warning = {
                'title': _("Contraindicated Medicine"),
                'message': _("The medicine '%s' is contraindicated for diseases: %s.")
                        % (self.product_id.name, names)
            }
            # Reset product to avoid accidental save
            self.product_id = False
            return {'warning': warning}

        # 2. Caution = show warning only
        cautions = self.product_id.cautiuse_disease_ids
        common_caution = cautions & patient_diseases
        if common_caution:
            names = ", ".join(common_caution.mapped("name"))
            self.prescription_id.warning_message = _("Caution: The medicine '%s' requires caution for the patient's diseases: %s.") % (self.product_id.name, names)

            return {
                'warning': {
                    'title': _("Caution"),
                    'message': _("The medicine '%s' requires caution for diseases: %s.")
                            % (self.product_id.name, names)
                }
            }
        # 3. Interfering medications
        interfering_meds = self.product_id.interfering_medication_ids
        common_meds = interfering_meds & patient_medications
        if common_meds:
            names = ", ".join(common_meds.mapped("name"))
            self.prescription_id.warning_message = _("Warning: The medicine '%s' may interfere with the patient's current medications: %s.") % (self.product_id.name, names)

            return {
                'warning': {
                    'title': _("Interfering Medications"),
                    'message': _("The medicine '%s' may interfere with current medications: %s.")
                            % (self.product_id.name, names)
                }
            }
    @api.constrains('product_id', 'prescription_id')
    def _check_danger_diseases(self):
        for record in self:
            patient_diseases = record.prescription_id.case_id.medical_record_id.disease_ids
            dangerous_diseases = record.product_id.danger_disease_ids
            common_diseases = patient_diseases & dangerous_diseases
            if common_diseases:
                disease_names = ', '.join(common_diseases.mapped('name'))
                raise UserError(_("Warning: The medicine '%s' is contraindicated for the patient's diseases: %s.") % (record.product_id.name, disease_names))
    @api.constrains('product_id', 'prescription_id')
    def _check_cautiuse_diseases(self):
        for record in self:
            patient_diseases = record.prescription_id.case_id.medical_record_id.disease_ids
            cautiuse_diseases = record.product_id.cautiuse_disease_ids
            common_diseases = patient_diseases & cautiuse_diseases
            if common_diseases:
                disease_names = ', '.join(common_diseases.mapped('name'))
                record.prescription_id.warning_message = _("Caution: The medicine '%s' requires caution for the patient's diseases: %s.") % (record.product_id.name, disease_names)

    @api.model
    def create(self, vals):
        records = super(HmsPrescriptionLine, self).create(vals)
        for record in records:
            if record.is_dispensed:
                record.dispensed_date = fields.Date.context_today(self)
        return records