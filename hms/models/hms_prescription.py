from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HmsPrescription(models.Model):
    _name = 'hms.prescription'
    _description = _('HMS Prescription')
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string=_('Name'), required=True, default='New')
    case_id = fields.Many2one('hms.case', string=_('Case'), required=True)
    patient_id = fields.Many2one('res.partner', string=_('Patient'), related='case_id.patient_id', store=True)
    date = fields.Date(string=_('Date'), default=fields.Datetime.now, required=True)
    state = fields.Selection([
        ('draft', _('Draft')),                           
        ('confirmed', _('Confirmed')),
        ('dispensed', _('Dispensed')),
        ('cancelled', _('Cancelled'))
    ], string=_('State'), default='draft', required=True, tracking=True)
    prescription_line_ids = fields.One2many('hms.prescription.line', 'prescription_id', string=_('Prescription Lines'))
    is_dispensed = fields.Boolean(string=_('Is Dispensed'), store=True)
    notes = fields.One2many('hms.note', 'prescription_id', string='Notes')
    medical_record_id = fields.Many2one(
    related="case_id.medical_record_id",
    string="Medical Record",
    store=True,  
)

    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'
            cem = self.env['hr.employee'].sudo().search([('hms_role_id.code', '=', 'chemist')])
            for chemist in cem:
                record.send_inbox_notification(chemist.user_id, _("Prescription %s for case %s needs to be dispensed.") % (record.name, record.case_id.name), fields.Datetime.now() + timedelta(days=1))


    def action_dispense(self):
        StockMove = self.env['stock.move'].sudo()
        for record in self:
            # Get pharmacy location
            pharmacy_location = self.env.ref('stock.stock_location_stock')

            if not pharmacy_location:
                # Fallback to any internal location if no pharmacy found
                pharmacy_location = self.env['stock.location'].sudo().search(
                    [('usage', '=', 'internal')],
                    limit=1
                )
            if not pharmacy_location:
                raise UserError(_("No pharmacy or internal location configured. Please configure a stock location first."))

            # Check available quantity for all prescription lines before proceeding
            for line in record.prescription_line_ids:
                available_qty = self.env['stock.quant']._get_available_quantity(
                    line.product_id, pharmacy_location
                )
                if available_qty < line.quantity:
                    raise UserError(_("Not enough stock for %s. Available: %s %s") %
                                    (line.product_id.name, available_qty, line.uom_id.name))

            # Proceed with dispensing
            try:
                picking_type = self.env.ref('stock.picking_type_out', raise_if_not_found=False)
                if not picking_type:
                    raise UserError(_("Please configure a picking type for dispensing."))

                for line in record.prescription_line_ids:
                    move_vals = {
                        'name': _("Dispense %s") % line.product_id.name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'product_uom': line.product_id.uom_id.id,
                        'location_id': pharmacy_location.id,
                        'location_dest_id': picking_type.default_location_dest_id.id,
                        'picking_type_id': picking_type.id,
                        'state': 'draft',
                    }
                    stock_move = StockMove.create(move_vals)
                    stock_move._action_confirm()
                    stock_move._action_assign()
                    stock_move._action_done()
                    stock_move.picking_id.button_validate()
                    line.stock_move_id = stock_move.id
                    line.is_dispensed = True
                    line.dispensed_date = fields.Date.context_today(self)

                # Update prescription status
                record.is_dispensed = True
                record.state = 'dispensed'

                # Send email notification
                template = self.env.ref('hms.email_template_prescription_ready', raise_if_not_found=False)
                if template:
                    template.send_mail(record.id, force_send=True)

                # Notify patient via portal if email exists
                if record.patient_id.email:
                    self.env['mail.message'].create({
                        'body': _("Your prescription %s has been dispensed and is ready for pickup.") % record.name,
                        'subject': _("Prescription Ready"),
                        'message_type': 'notification',
                        'partner_ids': [(4, record.patient_id.id)],
                        'model': self._name,
                        'res_id': record.id,
                    })

            except Exception as e:
                raise UserError(_("Error while dispensing medication: %s") % str(e))

        return True

    def action_cancel(self):
        for record in self:
            record.state = 'cancelled'

    def action_reset_to_draft(self):
        for record in self:
            record.state = 'draft'

    def print_prescription_report(self):                                                                  
         return self.env.ref('hms.action_report_prescription').report_action(self) 

    @api.model
    def create(self, vals):
        # Create the record first
        record = super(HmsPrescription, self).create(vals)

        # If name is default, generate and update it
        if record.name == 'New':
            sequence = self.env['ir.sequence'].next_by_code('hms.prescription') or 'New'
            if record.patient_id:
                record.name = f"{sequence}/{record.patient_id.name}"
            else:
                record.name = sequence
        cem = self.env['hr.employee'].search([('hms_role_id.code', '=', 'Chemist')])
        for chemist in cem:
            record.send_inbox_notification(chemist.user_id, _("Prescription %s for case %s needs to be validated.") % (record.name, record.case_id.name), fields.Datetime.now() + timedelta(days=1))

        return record



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