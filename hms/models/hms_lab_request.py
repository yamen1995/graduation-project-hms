from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

class HmsLabRequest(models.Model):
    _name = 'hms.lab.request'
    _description = 'HMS Lab Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, default='New')
    lab_request_line_ids = fields.One2many('hms.lab.request.line', 'lab_request_id', string="Lab Request Lines")
    lab_result_ids = fields.One2many(
        'hms.lab.result', compute='_compute_lab_results',
        string="Lab Results", store=False
    )
    case_id = fields.Many2one('hms.case', string='Case', required=True)
    patient_id = fields.Many2one('res.partner', string='Patient', related='case_id.patient_id', store=True)
    date_requested = fields.Datetime(string='Date Requested', default=fields.Datetime.now, required=True)
    requested_by_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True)
    lab_technician_id = fields.Many2one('hr.employee', string='Lab Technician', domain="[('job_id.name', '=', 'Lab Technician')]", help="The lab technician responsible for this request.")
    urgency = fields.Selection([
        ('normal', _('Normal')),
        ('low', _('Low')),
        ('high', _('High')),
        ('urgent', _('Urgent'))
    ], string=_('Urgency'), default='normal', required=True)
    state = fields.Selection([
        ('draft', _('Draft')),
        ('requested', _('Requested')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled'))
    ], string=_('State'), default='draft', required=True, tracking=True)
    notes = fields.Html(string='Notes')
    medical_record_id = fields.Many2one(
    related="case_id.medical_record_id",
    string="Medical Record",
    store=True,  
    )


    @api.model
    def create(self, vals):
        record = super(HmsLabRequest, self).create(vals)
        

        if record.name == 'New':
            sequence = self.env['ir.sequence'].next_by_code('hms.lab.request') or 'New'
            if record.patient_id:
                record.name = f"{sequence}/{record.patient_id.name}"
            else:
                record.name = sequence
        lab = self.env['hr.employee'].search([('hms_role_id.name', '=', 'Lab Attendant')])
        for lab_tech in lab:
            record.send_inbox_notification(lab_tech.user_id, _("Lab request %s for case %s needs review.") % (record.name, record.case_id.name), fields.Datetime.now() + timedelta(days=1))

        return record


    @api.depends('lab_request_line_ids.lab_result_ids')
    def _compute_lab_results(self):
        for request in self:
            request.lab_result_ids = request.lab_request_line_ids.mapped('lab_result_ids')

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft requests can be confirmed."))
            record.state = 'requested'
            for line in record.lab_request_line_ids:
                    line_vals = {
                        'order_id': record.case_id.sale_order_id.id,
                        'product_id': line.product_id.id,
                        'product_uom_qty': 1,
                        'price_unit': line.product_id.list_price,
                    }

                    self.env['sale.order.line'].create(line_vals)

    def action_start(self):
        for record in self:
            if record.state != 'requested':
                raise UserError(_("Only requested requests can be marked as In Progress."))
            record.state = 'in_progress'

    def action_done(self):
        StockMove = self.env['stock.move'].sudo()
        for record in self:
            if record.state != 'in_progress':
                raise UserError(_("Only in-progress requests can be marked as Completed."))
            record.state = 'completed'
            location = self.env.ref('stock.stock_location_stock')
            for line in record.lab_request_line_ids:
                available_qty = self.env['stock.quant']._get_available_quantity(
                    line.product_id, location
                )
                if available_qty < 1:
                    raise UserError(_("Not enough stock for %s. Available: %s %s") %
                                    (line.product_id.name, available_qty, line.uom_id.name))
            try:
                sale_order = record.case_id.sale_order_id
                for picking in sale_order.picking_ids:
                    picking.button_validate()   
               
            except Exception as e:
                raise UserError(_("Error while dispensing test: %s") % str(e))

            record.send_inbox_notification(record.requested_by_id.user_id, _("Lab request %s for case %s has been completed.") % (record.name, record.case_id.name), fields.Datetime.now())

    def action_cancel(self):
        for record in self:
            if record.state == 'completed':
                raise UserError(_("You cannot cancel a completed request."))
            record.state = 'cancelled'
    
    def send_inbox_notification(self, user_id, message_body, date_deadline):
        """Schedule a mail.activity for the user so doctor sees it in their ToDos."""
        if not user_id:
            return
        try:
            self.activity_schedule(
                summary=_("Hospital Notification"),
                note=f"<div>{message_body}",
                user_id=user_id.id,
                date_deadline=date_deadline,
            )
        except Exception:
            # don't raise on notification failures
            _logger = __import__('logging').getLogger(__name__)
            _logger.exception("Failed to schedule activity for user %s", getattr(user_id, 'id', False))