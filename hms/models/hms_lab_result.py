from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HmsLabResult(models.Model):
    _name = 'hms.lab.result'
    _description = _('HMS Lab Result')
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string=_('Name'), required=True, default='New')
    case_id = fields.Many2one('hms.case', string=_('Case'), required=True)
    lab_request_line_id = fields.Many2one('hms.lab.request.line',string=_('Lab Test'),domain="[('lab_request_id.case_id', '=', case_id)]",required=True)
    lab_request_id = fields.Many2one('hms.lab.request',string=_('Lab Request'),compute='_compute_lab_request_and_patient',store=True)
    patient_id = fields.Many2one('res.partner', string='Patient', related='case_id.patient_id', store=True)
    date_result = fields.Datetime(string=_('Result Date'), default=fields.Datetime.now, required=True)
    lab_technician_id = fields.Many2one('hr.employee', string=_('Lab Technician'), related='lab_request_id.lab_technician_id', store=True)
    lab_request_state = fields.Selection(related='lab_request_id.state', string=_('Lab Request State'), store=True)
    recommendations = fields.Text(string=_('Recommendations'))
    attachment_ids = fields.Binary(string=_('Result Attachments'))
    notes = fields.One2many('hms.note', 'lab_result_id', string='Notes')


    def print_lab_result_report(self):
        return self.env.ref('hms.report_lab_result_document').report_action(self) 


    @api.model
    def create(self, vals):
        record = super(HmsLabResult, self).create(vals)

        if record.name == 'New':
            sequence = self.env['ir.sequence'].next_by_code('hms.lab.result') or 'New'
            if record.patient_id:
                record.name = f"{sequence}/{record.patient_id.name}"
            else:
                record.name = sequence

        return record


    @api.depends('lab_request_line_id')
    def _compute_lab_request_and_patient(self):
        for rec in self:
            lab_line = rec.lab_request_line_id
            if lab_line:
                rec.lab_request_id = lab_line.lab_request_id
                rec.patient_id = lab_line.lab_request_id.patient_id
            else:
                rec.lab_request_id = False
                rec.patient_id = False

