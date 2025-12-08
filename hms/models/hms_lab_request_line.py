import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

class HmsLabRequestLine(models.Model):
    _name = 'hms.lab.request.line'
    _description = _('HMS Lab Request Line')

    name = fields.Char(string=_('Name'), required=True, default='New')
    lab_request_id = fields.Many2one('hms.lab.request', string=_('Lab Request'), required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string=_('Test Name'), required=True, domain=[('is_lab_test', '=', True)]
    )
    lab_result_ids = fields.Many2many(
        'hms.lab.result',
        'lab_request_line_id',
        string=_('Lab Results'),
    )
    value = fields.Char(
        string=_('Value'),
    )
    uom_id = fields.Many2one(
        'uom.uom', string=_('Unit of Measure'),
    )
    normal_range = fields.Char(
        string=_('Normal Range'),
    )
    is_abnormal = fields.Boolean(string=_('Is Abnormal'), compute='_compute_is_abnormal', store=True)
    stock_move_id = fields.Many2one('stock.move', string=_('Stock Move'))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id or not self.lab_request_id:
            return

        patient_diseases = self.lab_request_id.case_id.medical_record_id.disease_ids
        patient_medications = self.lab_request_id.case_id.medical_record_id.medication_ids
        cautions = self.product_id.cautiuse_disease_ids
        common_caution = cautions & patient_diseases
        if common_caution:
            names = ", ".join(common_caution.mapped("name"))
            warning = {
                'title': _("Caution Advised"),
                'message': _("The lab test '%s' result might get affected by patient conditions: %s.")
                        % (self.product_id.name, names)
            }
            return {
                'warning': warning
            }
        enterfering_meds = self.product_id.interfering_medication_ids
        common_medications = enterfering_meds & patient_medications
        if common_medications:
            names = ", ".join(common_medications.mapped("name"))
            warning = {
                'title': _("Caution Advised"),
                'message': _("The lab test '%s' result might get affected by patient medications: %s.")
                        % (self.product_id.name, names)
            }
            return {
                'warning': warning
            }

    @api.constrains('value')
    def _check_value_is_numeric_and_positive(self):
        for record in self:
            if record.value:
                try:
                    value_float = float(record.value)
                    if value_float < 0:
                        raise ValidationError(_("The entered value cannot be negative."))
                except ValueError:
                    raise ValidationError(_("You must enter a valid numeric value in the 'value' field."))

    @api.constrains('normal_range')
    def _check_normal_range_format(self):
        for record in self:
            if record.normal_range:
                # Use regular expression to allow only numeric values and one dash
                pattern = r'^\s*[\d.]+\s*-\s*[\d.]+\s*$'
                if not re.match(pattern, record.normal_range):
                    raise ValidationError(_("Normal range must only contain numbers and a single dash (e.g. '3.5 - 7.2'). Letters or other characters are not allowed."))

                # Try to convert both sides to float and validate logical order
                try:
                    parts = record.normal_range.split('-')
                    min_val = float(parts[0].strip())
                    max_val = float(parts[1].strip())
                    if min_val >= max_val:
                        raise ValidationError(_("Minimum value must be less than maximum value in normal range."))
                except ValueError:
                    raise ValidationError(_("Both values in normal range must be valid numbers."))

    @api.depends('value', 'normal_range')
    def _compute_is_abnormal(self):
        for record in self:
            record.is_abnormal = False
            if record.value and record.normal_range:
                try:
                    value_float = float(record.value)

                    # Try to parse normal_range if formatted as 'min - max'
                    if '-' in record.normal_range:
                        parts = record.normal_range.split('-')
                        if len(parts) == 2:
                            min_val = float(parts[0].strip())
                            max_val = float(parts[1].strip())
                            record.is_abnormal = not (min_val <= value_float <= max_val)
                        else:
                            record.is_abnormal = False
                    else:
                        # Handle fixed normal value (less commonly used)
                        try:
                            normal_val = float(record.normal_range.strip())
                            tolerance = normal_val * 0.1
                            record.is_abnormal = abs(value_float - normal_val) > tolerance
                        except ValueError:
                            record.is_abnormal = False
                except (ValueError, TypeError):
                    record.is_abnormal = False


    @api.model
    def create(self, vals):
        # Create the record first
        record = super(HmsLabRequestLine, self).create(vals)
        record.name = f"{record.product_id.name}"


        return record


