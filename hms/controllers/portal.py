from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from datetime import datetime, timedelta, time

class PortalPatientController(http.Controller):

    def _get_patient_id(self):
        """Get patient (res.partner) ID for current user"""
        user = request.env.user
        
        patient = request.env['res.partner'].search([
            ('user_id', '=', user.id),
            ('is_patient', '=', True)
        ], limit=1)
        return patient.id if patient else None

    
    @http.route('/my/appointments', type='http', auth='user', website=True)
    def my_appointments(self, **kw):
        # Get appointments for current user
        appointments = request.env['hms.appointment'].search([
            ('patient_id', '=', request.env.user.partner_id.id)
        ])
        return request.render('hms.portal_my_appointments', {
            'appointments': appointments
        })
    
    @http.route('/my/labs', type='http', auth='user', website=True)
    def my_labs(self, **kw):
        # Get lab results for current user
        lab_results = request.env['hms.lab.result'].search([
            ('patient_id', '=', request.env.user.partner_id.id)
        ])
        return request.render('hms.portal_my_lab_results', {
            'lab_results': lab_results
        })
    
    @http.route('/my/medical_record', type='http', auth='user', website=True)
    def my_medical_record(self, **kw):
        # Get medical record for current user
        medical_record = request.env['hms.medical.record'].search([
            ('patient_id', '=', request.env.user.partner_id.id)
        ], limit=1)
        
        if not medical_record:
            # Handle case where no medical record exists
            return request.redirect('/my/home')

        return request.render('hms.portal_my_medical_record', {
            'medical_record': medical_record
        })
    
    @http.route('/my/cases', type='http', auth='user', website=True)
    def my_cases(self, **kw):
        # Get cases for current user
        cases = request.env['hms.case'].search([
            ('patient_id', '=', request.env.user.partner_id.id)
        ])
        return request.render('hms.portal_my_cases', {
            'cases': cases
        })
    
    @http.route('/my/cases/<int:case_id>', type='http', auth='user', website=True)
    def case_details(self, case_id, **kw):
        # Get case details
        case = request.env['hms.case'].browse(case_id)
        if case.patient_id.id != request.env.user.partner_id.id:
            return request.redirect('/my/home')

        return request.render('hms.portal_case_details', {
            'case': case
        })
    
    @http.route('/my/prescriptions', type='http', auth='user', website=True)
    def my_prescriptions(self, **kw):
        # Get prescriptions for current user
        prescriptions = request.env['hms.prescription'].search([
            ('patient_id', '=', request.env.user.partner_id.id)
        ])
        return request.render('hms.portal_my_prescriptions', {
            'prescriptions': prescriptions
        })
    
    @http.route('/my/prescriptions/<int:prescription_id>', type='http', auth='user', website=True)
    def prescription_details(self, prescription_id, **kw):
        # Get prescription details
        prescription = request.env['hms.prescription'].browse(prescription_id)
        if prescription.patient_id.id != request.env.user.partner_id.id:
            return request.redirect('/my/home')

        return request.render('hms.portal_prescription_details', {
            'prescription': prescription
        })
    
      # ------------------------------------------------------------
    # Main entry point (button in portal dashboard)
    # ------------------------------------------------------------
    @http.route('/my/appointment/request', type='http', auth='user', website=True)
    def portal_appointment_request(self, **kwargs):
        """Render the appointment request page (main entry)."""
        partner = request.env.user.partner_id
        departments = request.env['hr.department'].sudo().search([('is_hospital' , '=', True)])
        my_doctors = request.env['hr.employee'].sudo().search([('hms_role_id.code', '=', 'doctor' ),('case_ids.patient_id', '=', partner.id)])

        return request.render('hms.portal_appointment_request', {
            'departments': departments,
            'my_doctors': my_doctors,
        })

    # ------------------------------------------------------------
    # General Appointment Request
    # ------------------------------------------------------------
    @http.route('/my/appointment/request/general', type='http', auth='user', methods=['POST'], website=True)
    def appointment_request_general(self, **post):
        partner = request.env.user.partner_id
        department_id = int(post.get('department'))
        date_str = post.get('appointment_date')
        time_str = post.get('appointment_time')

        dt_start = datetime.combine(
            datetime.strptime(date_str, '%Y-%m-%d').date(),
            datetime.strptime(time_str, '%H:%M').time()
        )
        end1 = dt_start + timedelta(minutes=30)


        # pick first doctor in that department
        doctor = request.env['hr.employee'].sudo().search([('department_id', '=', department_id)], limit=1)

        appointment = request.env['hms.appointment'].sudo().create({
            'patient_id': partner.id,
            'doctor_id': doctor.id if doctor else False,
            'department_id': department_id,
            'date': dt_start,
            'expected_end' : end1,
            'state': 'draft',
        })
        rece = request.env['hr.employee'].sudo().search([('hms_role_id.code', '=', 'receptionist')])
        for rec in rece:
            appointment.sudo().send_inbox_notification(rec.user_id, _("New appointment request from %s") % partner.name, fields.Datetime.now() + timedelta(days=1))

        return request.render('hms.portal_appointment_request_confirmation', {
            'appointment_request': appointment,
        })

    # ------------------------------------------------------------
    # My Doctor Appointment Request
    # ------------------------------------------------------------
    @http.route('/my/appointment/request/mydoctor', type='http', auth='user', methods=['POST'], website=True)
    def appointment_request_mydoctor(self, **post):
        partner = request.env.user.partner_id
        doctor_id = int(post.get('doctor_id'))
        doctor = request.env['hr.employee'].sudo().browse(doctor_id)

        # Dummy slot: tomorrow at 9:00
        calendar = doctor.resource_calendar_id
        today = fields.Datetime.now()
        appointments = request.env['hms.appointment'].search([('doctor_id', '=', doctor.id), ('state', '!=', 'canceled')])
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
        end = next_date + timedelta(minutes=30)

        appointment = request.env['hms.appointment'].sudo().create({
            'patient_id': partner.id,
            'doctor_id': doctor.id,
            'department_id': doctor.department_id.id if doctor.department_id else False,
            'date': next_date,
            'expected_end' : end,
            'state': 'draft',
        })
        rece = request.env['hr.employee'].sudo().search([('hms_role_id.code', '=', 'receptionist')])
        for rec in rece:
            appointment.send_inbox_notification(rec.user_id, _("New appointment request from %s") % partner.name, fields.Datetime.now() + timedelta(days=1))

        return request.render('hms.portal_appointment_request_confirmation', {
            'appointment_request': appointment,
        })

    # ------------------------------------------------------------
    # Generic Submit (manual form)
    # ------------------------------------------------------------
    @http.route('/my/appointment/request/submit', type='http', auth='user', methods=['POST'], website=True)
    def appointment_request_submit(self, **post):
        partner = request.env.user.partner_id
        doctor_id = int(post.get('doctor_id'))
        appointment_date = post.get('appointment_date')
        appointment_time = post.get('appointment_time')

        dt_start = datetime.strptime(f"{appointment_date} {appointment_time}", '%Y-%m-%d %H:%M')
        end1 = dt_start + timedelta(minutes=30)

        appointment = request.env['hms.appointment'].sudo().create({
            'patient_id': partner.id,
            'doctor_id': doctor_id,
            'date': dt_start,
            'expected_end' : end1,
            'reason': post.get('reason'),
            'urgency': post.get('urgency'),
            'state': 'draft',
        })
        rece = self.env['hr.employee'].sudo().search([('hms_role_id.code', '=', 'receptionist')])
        for rec in rece:
            appointment.send_inbox_notification(rec.user_id, _("New appointment request from %s") % partner.name, fields.Datetime.now() + timedelta(days=1))

        return request.render('hms.portal_appointment_request_confirmation', {
            'appointment_request': appointment,
        })
    def send_inbox_notification(self, user_id, message_body, date_deadline):
        """Schedule a mail.activity for the user so doctor sees it in their ToDos."""
        if not user_id:
            return
        try:
            self.activity_schedule(
                summary=_("Hospital Notification"),
                note=message_body,
                user_id=user_id,
                date_deadline=date_deadline,
            )
        except Exception:
            # don't raise on notification failures
            _logger = __import__('logging').getLogger(__name__)
            _logger.exception("Failed to schedule activity for user %s", getattr(user_id, 'id', False))
