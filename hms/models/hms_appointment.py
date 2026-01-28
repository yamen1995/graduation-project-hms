
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta, datetime

class HmsAppointment(models.Model):
    _name = 'hms.appointment'
    _description = _('Patient Appointment')
    _inherit = ['mail.activity.mixin']

    name = fields.Char(string="Appointment Reference", required=True, copy=False, readonly=True, tracking=True)
    case_id = fields.Many2one('hms.case', string='Case', tracking=True)
    patient_id = fields.Many2one('res.partner', string='Patient', required=True, domain="[('is_patient','=',True)]", tracking=True)
    doctor_id = fields.Many2one(
        'hr.employee', string='Doctor',
        domain="[('hms_role_id.code', '=', 'doctor')]",
        required=True,
        tracking=True
    )
    date = fields.Datetime(string='Appointment Date', required=True, default=fields.Datetime.now, tracking=True)
    expected_end = fields.Datetime(string='Expected End', tracking=True, default=lambda self: fields.Datetime.now() + timedelta(minutes=30))
    state = fields.Selection([
        ('draft', _('Draft')),
        ('confirmed', _('Confirmed')),
        ('in_progress', _('In Progress')),
        ('done', _('Done')),
        ('canceled', _('Canceled')),
        ('no_show', _('No Show')),
    ], string=_('Status'), default='draft', tracking=True)
    cancel_reason = fields.Text(string='Cancel Reason')
    no_show_reason = fields.Text(string='No Show Reason')
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user, readonly=True)
    department_id = fields.Many2one(
    "hr.department", 
    string="Department", 
    store=True
)
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event', readonly=True)
    urgency = fields.Selection([('routine','Routine'), ('urgent','Urgent'), ('emergency','Emergency')], string='Urgency', default='routine')
    reason = fields.Text(string='Reason for Appointment')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    # ----------------------------
    # Core Workflow Methods
    # ----------------------------

    def action_confirm(self):
        """Keep appointments as bookings only. Confirm appointment and create calendar event."""
        for appt in self:
            appt.state = 'confirmed'
            appt._create_or_update_calendar_event()
            template = self.env.ref('hms.email_template_appointment_confirmation')
            template.send_mail(self.id, force_send=True)
            # notify the doctor via activity
            if appt.doctor_id and appt.doctor_id.user_id:
                appt.send_inbox_notification(appt.doctor_id.user_id, _("You have an appointment with %s at %s") % (appt.patient_id.name, appt.date), appt.date - timedelta(hours=1))

    def action_in_progress(self):
        """
        When appointment is started:
        - Ensure medical record exists (open wizard if not)
        - If there's no case, open the case form with defaults so receptionist/doctor can create the actual case.
        - If case exists, set appointment state to in_progress.
        """
        for appointment in self:
            if appointment.state != 'confirmed':
                raise UserError(_("Only confirmed appointments can be started."))

            medical_record = appointment.patient_id.medical_record_id
            if not medical_record:
                # open wizard to create medical record and continue from appointment
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Create Medical Record'),
                    'res_model': 'medical.record.wizard',
                    'view_mode': 'form',
                    'view_id': self.env.ref('hms.view_medical_record_wizard_form').id,
                    'target': 'new',
                    'context': {'default_patient_id': appointment.patient_id.id , 'from_appointment_id': appointment.id},
                }

            # If no case, open a case form prefilled with defaults
            if not appointment.case_id:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "hms.case",
                    "view_mode": "form",
                    "target": "current",
                    "context": {
                        "default_medical_record_id": medical_record.id,
                        "default_main_doctor_id": appointment.doctor_id.id if appointment.doctor_id else False,
                        "default_admission_date": appointment.date,
                        "from_appointment_id": appointment.id,
                    },
                }

            # case exists: proceed
            appointment.state = 'in_progress'
            

    def action_done(self):
        """
        Mark appointment done. If linked case has a task, mark task done and create a timesheet entry draft.
        The case is the source of truth for work/time (project/task/timesheet).
        """
        for appointment in self:
            if appointment.state not in ('draft', 'confirmed', 'in_progress'):
                raise UserError(_("Only draft, confirmed, or in-progress appointments can be marked as done."))
            appointment.state = 'done'

    def action_cancel(self, reason=None):
        for appointment in self:
            appointment.state = 'canceled'
            appointment.cancel_reason = reason or _('Canceled by user.')
            template = self.sudo().env.ref('hms.email_template_appointment_cancellation')
            template.send_mail(self.id, force_send=True)
            if appointment.doctor_id and appointment.doctor_id.user_id:
                appointment.send_inbox_notification(appointment.sudo().doctor_id.user_id, _("Appointment with %s at %s was canceled") % (appointment.patient_id.name, appointment.date), appointment.date)

    @api.model
    def _auto_mark_no_show(self):
        now = fields.Datetime.now()
        appointments = self.search([
            ('state', '=', 'confirmed'),
            ('expected_end', '<', now)
        ])
        for appointment in appointments:
            appointment.state = 'no_show'
            appointment.no_show_reason = _('Patient did not attend the appointment (auto-detected).')

    # ----------------------------
    # Doctor Availability - helpers
    # ----------------------------
    @api.onchange("department_id")
    def _onchange_department_id(self):
        if self.department_id:
            return {
                "domain": {
                    "doctor_id": [
                        ("hms_role_id.code", "=", "doctor"),
                        ("department_id", "=", self.department_id.id)
                    ]
                }
            }
        return {
            "domain": {"doctor_id": [("hms_role_id.code", "=", "doctor")]}
        }

    @api.onchange('doctor_id')
    def _onchange_doctor_id(self):
        # Suggest next free slot based on doctor's working calendar (30-minute slots)
        for rec in self:
            if not rec.doctor_id:
                continue
            calendar = rec.doctor_id.resource_calendar_id
            if not calendar:
                continue
            today = fields.Datetime.now()
            appointments = self.env['hms.appointment'].search([('doctor_id', '=', rec.doctor_id.id), ('state', '!=', 'canceled')])
            next_date = None
            for day_offset in range(0, 30):
                date_candidate = today + timedelta(days=day_offset)
                weekday = str(date_candidate.weekday())
                working_intervals = calendar.attendance_ids.filtered(lambda a: a.dayofweek == weekday)
                for interval in working_intervals:
                    start_hour = int(interval.hour_from)
                    end_hour = int(interval.hour_to)
                    slot_time = date_candidate.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                    while slot_time.hour < end_hour:
                        if not appointments.filtered(lambda a: a.date == slot_time):
                            next_date = slot_time
                            break
                        slot_time += timedelta(minutes=30)
                    if next_date:
                        break
                if next_date:
                    break
            if next_date:
                rec.date = next_date

    @api.onchange('date')
    def _onchange_date_update_available_doctors(self):
        for rec in self:
            if not rec.date:
                continue
            all_doctors = self.env['hr.employee'].search([('hms_role_id.code', '=', 'doctor')])
            busy_doctors = self.env['hms.appointment'].search([('date', '=', rec.date), ('state', '!=', 'canceled')]).mapped('doctor_id')
            available_doctors = all_doctors - busy_doctors
            rec.expected_end = rec.date + timedelta(minutes= 30)
            return {'domain': {'doctor_id': [('id', 'in', available_doctors.ids)]}}

    @api.constrains('doctor_id', 'date')
    def _check_doctor_availability(self):
        for rec in self:
            if rec.doctor_id and rec.date:
                calendar = rec.doctor_id.resource_calendar_id
                if calendar:
                    weekday = rec.date.weekday()
                    attendances = calendar.attendance_ids.filtered(lambda a: a.dayofweek == str(weekday))
                    if not any(a.hour_from*3600 <= rec.date.hour*3600 + rec.date.minute*60 <= a.hour_to*3600 for a in attendances):
                        raise ValidationError(_("Doctor %s is not working at the selected time.") % rec.doctor_id.name)
                start_time = rec.date
                end_time = rec.date + timedelta(minutes=30)
                overlapping = self.search([('id', '!=', rec.id), ('doctor_id', '=', rec.doctor_id.id),
                                          ('date', '>=', start_time), ('date', '<=', end_time), ('state', '!=', 'canceled')], limit=1)
                if overlapping:
                    raise ValidationError(_("Doctor %s is already booked between %s and %s.") %
                                          (rec.doctor_id.name, start_time, end_time))

    # ----------------------------
    # Calendar Integration
    # ----------------------------
    def _prepare_calendar_event_vals(self):
        self.ensure_one()
        return {
            'name': _("Appointment: %s") % self.patient_id.name,
            'start': self.date,
            'stop': self.expected_end or (self.date + timedelta(minutes=30)),
            'user_id': self.doctor_id.user_id.id if self.doctor_id.user_id else False,
            'partner_ids': [(4, self.patient_id.id)],
        }

    def _create_or_update_calendar_event(self):
        for appt in self:
            vals = appt._prepare_calendar_event_vals()
            if appt.calendar_event_id:
                appt.calendar_event_id.sudo().write(vals)
            else:
                event = self.env['calendar.event'].sudo().create(vals)
                appt.calendar_event_id = event.id

    # ----------------------------
    # Create / Write Overrides
    # ----------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            patient = (
                self.env['res.partner'].browse(vals.get('patient_id'))
                if vals.get('patient_id')
                else None
            )

            patient_name = (
                patient.name.replace(" ", "")
                if patient and patient.name
                else "Unknown"
            )

            appointment_date = vals.get('date') or fields.Datetime.now()
            if isinstance(appointment_date, str):
                appointment_date = fields.Datetime.from_string(appointment_date)

            date_part = appointment_date.strftime("%Y%m%d")
            seq = self.env['ir.sequence'].sudo().next_by_code('hms.appointment') or "0000"

            vals['name'] = f"AP/{patient_name}_{date_part}_{seq}"

        appointments = super().create(vals_list)

        for appointment in appointments:
            appointment._create_or_update_calendar_event()

        return appointments

    def write(self, vals):
        res = super().write(vals)
        if 'date' in vals or 'doctor_id' in vals:
            self._create_or_update_calendar_event()
        return res

    def send_inbox_notification(self, user_id, message_body, date_deadline):
        """Schedule a mail.activity for the user so doctor sees it in their ToDos."""
        if not user_id:
            return
        try:
            self.activity_schedule(
                summary=_("Hospital Notification"),
                note=f"{message_body}",
                user_id=user_id,
                date_deadline=date_deadline,
            )
        except Exception:
            # don't raise on notification failures
            _logger = __import__('logging').getLogger(__name__)
            _logger.exception("Failed to schedule activity for user %s", getattr(user_id, 'id', False))