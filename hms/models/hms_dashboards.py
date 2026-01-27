from odoo import models, fields, api, _
from datetime import timedelta, datetime

class HmsDashboard(models.TransientModel):
    _name = 'hms.dashboard'
    _description = 'HMS Dashboard'

    name = fields.Char(string="Dashboard")

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        now = fields.Datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
                # Employee helper
        employee_id = user.employee_ids[0].id if user.employee_ids else False
        partner =  user.partner_id

        data = {
            'user_name': user.name,
            'user_login': user.login,
            'is_doctor': user.has_group('hms.group_hms_doctor'),
            'is_nurse': user.has_group('hms.group_hms_nurse'),
            'is_chemist': user.has_group('hms.group_hms_chemist'),
            'is_lab': user.has_group('hms.group_hms_lab_attendant'),
            'is_receptionist': user.has_group('hms.group_hms_receptionist'),
            'is_admin': user.has_group('base.group_system'),
            "user_avatar_url": f"/web/image/res.partner/{partner.id}/image_128" if partner else "/web/static/img/avatar.png",
            "user_email": partner.email or user.employee_id.work_email or user.email,
            "user_phone": partner.phone or user.employee_id.work_phone,
            "user_mobile": user.employee_id.mobile_phone,
            'activities': self._get_user_activities(),
        }


        # -------------------- Doctor --------------------

        if data.get('is_doctor') and employee_id:

           

            # KPI counts (confirmed appointments only)
            active_cases = self.env['hms.case'].search_count([
                ('main_doctor_id', '=', employee_id),
                ('state', '=', 'active')
            ])
            confirmed_appts_today = self.env['hms.appointment'].search_count([
                ('doctor_id', '=', employee_id),
                ('state', '=', 'confirmed'),
                ('date', '>=', start),
                ('date', '<', end)
            ])
            lab_results_received = self.env['hms.lab.result'].search_count([
                ('case_id.main_doctor_id', '=', employee_id),
                ('lab_request_line_id.lab_request_id.state', '=', 'Completed'),
            ])

            # Listings
            confirmed_appts = self.env['hms.appointment'].search([
                ('doctor_id', '=', employee_id),
                ('state', '=', 'confirmed'),
                ('date', '>=', start),
                ('date', '<', end)
            ], order='date asc')
            data['today_appointments'] = [{
                'id': a.id,
                'patient_name': a.patient_id.name,
                'date': a.date.isoformat() if a.date else '',
                'model': 'hms.appointment',
                'res_id': a.id,
            } for a in confirmed_appts]

            draft_cases = self.env['hms.case'].search([
                ('main_doctor_id', '=', employee_id),
                ('state', '=', 'draft')
            ], order='admission_date desc', limit=10)
            data['draft_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id
            } for c in draft_cases]

            open_cases = self.env['hms.case'].search([
                ('main_doctor_id', '=', employee_id),
                ('state', '=', 'active')
            ], order='admission_date desc', limit=10)
            data['active_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id,
            } for c in open_cases]

            consultation_cases = self.env['hms.case'].search([
                ('consulting_doctor_ids', '=', employee_id),
                ('state', 'in', ['draft', 'active'])
            ])
            data['consultation_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id
            } for c in consultation_cases]

            data['kpi'] = {
                'active_cases': active_cases,
                'appointments_today': confirmed_appts_today,
                'lab_results_received': lab_results_received,
                'consultation_cases': len(consultation_cases)
            }

        # -------------------- Nurse --------------------
        if data.get('is_nurse') and employee_id:

           

            assigned_cases = self.env['hms.case'].search_count([
                ('nurse_id', '=', employee_id),
                ('state', '=', 'active')
            ])
            appts_today = self.env['hms.appointment'].search_count([
                ('case_id.nurse_id', '=', employee_id),
                ('date', '>=', start),
                ('date', '<', end)
            ])
            pending_lab_results = self.env['hms.lab.result'].search_count([
                ('case_id.nurse_id', '=', employee_id),
                ('lab_request_id.state', '=', 'draft')
            ])


            # Draft & Active cases
            draft_cases = self.env['hms.case'].search([
                ('nurse_id', '=', employee_id),
                ('state', '=', 'draft')
            ], order='admission_date desc', limit=10)
            data['draft_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id
            } for c in draft_cases]

            open_cases = self.env['hms.case'].search([
                ('nurse_id', '=', employee_id),
                ('state', '=', 'active')
            ], order='admission_date desc', limit=10)
            data['active_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id,
            } for c in open_cases]

            # Today's appointments (confirmed)
            nurse_today_appts = self.env['hms.appointment'].search([
                ('case_id.nurse_id', '=', employee_id),
                ('state', '=', 'confirmed'),
                ('date', '>=', start),
                ('date', '<', end)
            ], order='date asc')
            data['today_appointments'] = [{
                'id': a.id,
                'patient_name': a.patient_id.name,
                'date': a.date.isoformat() if a.date else '',
                'model': 'hms.appointment',
                'res_id': a.id,
            } for a in nurse_today_appts]

        


            
            data['kpi'] = {
                'assigned_cases': assigned_cases,
                'appointments_today': appts_today,
                'pending_lab_results': pending_lab_results,
            }


        # -------------------- Lab --------------------
        if data['is_lab'] and employee_id:
            
            pending_requests_count = self.env['hms.lab.request'].search_count([
            ('state', '=', 'draft')
            ])
            results_to_validate = self.env['hms.lab.result'].search_count([
            ('lab_request_id.state', '=', 'completed')
            ])
            tests_today = self.env['hms.lab.request'].search_count([
            ('date_requested', '>=', start),
            ('date_requested', '<', end)
            ])
            open_cases = self.env['hms.case'].search([
                ('state', '=', 'active'),
                ('lab_request_ids', '!=', False)
            ], order='admission_date desc', limit=10)
            data['active_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id,
            } for c in open_cases]

                    
            data['kpi'] = {
            'pending_requests': pending_requests_count,
            'results_to_validate': results_to_validate,
            'tests_today': tests_today
            }
            

        # -------------------- Chemist --------------------
        if data['is_chemist']:
            prescriptions_to_dispense_count = self.env['hms.prescription'].search_count([
            ('state', '=', 'confirmed')
            ])
            open_cases = self.env['hms.case'].search([
                ('prescription_ids', '!=', False),
                ('state', '=', 'active')
            ], order='admission_date desc', limit=10)
            data['active_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id,
            } for c in open_cases]
            data['kpi'] = {'prescriptions_to_dispense': prescriptions_to_dispense_count}
            

        # -------------------- Reception/Admin --------------------

        if data['is_receptionist'] or data['is_admin']:
            
            patients_today = self.env['res.partner'].search_count([
                ('is_patient', '=', True),
                ('create_date', '>=', start),
                ('create_date', '<', end)
            ])
            appts_today = self.env['hms.appointment'].search_count([
                ('date', '>=', start),
                ('date', '<', end)
            ])
            open_cases = self.env['hms.case'].search_count([('state', '=', 'active')])
            admissions_today = self.env['hms.case'].search_count([
                ('state', '=', 'active'),
                ('admission_date', '>=', start),
                ('admission_date', '<', end)
            ])
            data['kpi'] = {
                'patients_today': patients_today,
                'appointments_today': appts_today,
                'open_cases': open_cases,
                'admissions_today': admissions_today
            }

            # Registered patients (from registration page, most recent first)
            reg_patients = self.env['res.partner'].sudo().search([
                ('is_patient', '=', True),
                ('outsider_patient', '=', True)
            ], order='create_date desc', limit=10)
            data['registered_patients'] = [
                {'id': p.id, 'name': p.name, 'date': p.create_date.strftime('%Y-%m-%d %H:%M') if p.create_date else '', 'model': 'res.partner',
                    'res_id': p.id,} for p in reg_patients
            ]

            # Appointments in draft state, sorted by date
            draft_appts = self.env['hms.appointment'].sudo().search([
                ('state', '=', 'draft')
            ], order='date asc', limit=10)
            data['draft_appointments'] = [
                {
                    'id': a.id,
                    'patient_name': a.patient_id.name,
                    'date': a.date.strftime('%Y-%m-%d %H:%M') if a.date else '',
                    'model': 'hms.appointment',
                    'res_id': a.id,
                } for a in draft_appts
            ]
            open_cases = self.env['hms.case'].search([
                ('state', '=', 'active')
            ], order='admission_date desc', limit=10)
            data['active_cases'] = [{
                'id': c.id,
                'name': c.name,
                'state': c.state,
                'date': c.admission_date.isoformat() if c.admission_date else '',
                'model': 'hms.case',
                'res_id': c.id,
            } for c in open_cases]


        # -------------------- Quick Actions --------------------
        quick_actions = []
        if data['is_admin'] or data['is_receptionist']:
            quick_actions += [
                {'label': _('New Patient'), 'action': 'hms.hms_patient_action'},
                {'label': _('Appointments'), 'action': 'hms.hms_appointment_action'},
                {'label': _('Billing/Invoices'), 'action': 'account.action_move_out_invoice_type'},
                {'label': _('Beds'), 'action': 'hms.action_hms_bed'},
                {'label': _('Rooms'), 'action': 'hms.action_hms_room'},
                
            ]
           
        if data['is_doctor']:
            quick_actions += [
                {'label': _('My Appointments'), 'action': 'hms.hms_appointment_action'},
                {'label': _('Prescribe Medication'), 'action': 'hms.action_prescription'},
                {'label': _('View Lab Results'), 'action': 'hms.action_lab_result'}
            ]
        if data['is_nurse']:
            quick_actions += [
                {'label': _('My Nurse Tasks'), 'action': 'hms.hms_case_action'},
                {'label': _('Patient Vitals'), 'action': 'hms.hms_patient_action'},
                {'label': _('Lab Results'), 'action': 'hms.action_lab_result'}
            ]
        if data['is_lab']:
            quick_actions += [
                {'label': _('Lab Requests'), 'action': 'hms.action_hms_lab_request'},
                {'label': _('Lab Results'), 'action': 'hms.action_lab_result'}
            ]
        if data['is_chemist']:
            quick_actions += [{'label': _('Dispense Medication'), 'action': 'hms.action_prescription'}]
        if data['is_admin']:
            quick_actions.append({'label': _('System Settings'), 'action': 'base_setup.action_general_configuration'})
            quick_actions.append({'label': _('Hospital Summary (30d)'), 'action': 'hms.action_report_admin_summary_30d'})
            quick_actions.append({
                'label': _('Medical Records (Last 7 Days)'),
                'action': 'hms.action_report_medrecs_last7',
            })    

        # Unique keys
        for i, qa in enumerate(quick_actions):
            qa['key'] = qa.get('action') or qa.get('label') or f'qa_{i}'
        data['quick_actions'] = quick_actions

        # Recent patients
        recent_patients = self.env['res.partner'].sudo().search([
            ('is_patient', '=', True)
        ], order='create_date desc', limit=6)
        data['recent_patients'] = [
            {'id': r.id, 'name': r.name, 'phone': r.phone or ''} for r in recent_patients
        ]

        return data

    @api.model
    def get_form_action(self, model_name, record_id):
        """
        Securely return a form view action dict for a given model/record, using sudo to avoid rights issues.
        """
        # Find form view action for the model
        form_action = self.env['ir.actions.act_window'].sudo().search([
            ('res_model', '=', model_name),
            ('view_mode', 'ilike', 'form'),
        ], limit=1)
        if not form_action:
            return {}
        # return a dict compatible for doAction in JS
        return {
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'res_id': int(record_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
            'id': form_action.id,
            'name': form_action.name,
        }

    @api.model
    def get_chart_data(self):
        user = self.env.user

        # Case distribution (common for all)
        case_data = self.env['hms.case'].read_group([], ['state'], 'state')
        case_labels = [d.get('state') or 'Undefined' for d in case_data]
        case_values = [d.get('state_count', 0) for d in case_data]

        today = fields.Date.context_today(self)
        days, counts = [], []
        chart_title = "No Data"

        # Role checks
        is_doctor_or_nurse = user.has_group('hms.group_hms_doctor') or user.has_group('hms.group_hms_nurse') or user.has_group('hms.group_hms_receptionist') or user.has_group('base.group_system')
        is_chemist = user.has_group('hms.group_hms_chemist')
        is_lab = user.has_group('hms.group_hms_lab_attendant')

        if is_doctor_or_nurse:
            # 14-day window (past 7 + future 7)
            chart_title = _("Appointments Trend")
            for i in range(-7, 8):
                day = today + timedelta(days=i)
                start_dt = fields.Datetime.to_string(datetime.combine(day, datetime.min.time()))
                end_dt = fields.Datetime.to_string(datetime.combine(day, datetime.max.time()))

                count = self.env['hms.appointment'].search_count([
                    ('date', '>=', start_dt),
                    ('date', '<=', end_dt)
                ])
                days.append(day.strftime('%b %d'))
                counts.append(count)

        elif is_chemist:
            # Only last 7 days
            chart_title = _("Prescriptions Trend")
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                start_dt = fields.Datetime.to_string(datetime.combine(day, datetime.min.time()))
                end_dt = fields.Datetime.to_string(datetime.combine(day, datetime.max.time()))

                count = self.env['hms.prescription'].search_count([
                    ('date', '>=', start_dt),
                    ('date', '<=', end_dt)
                ])
                days.append(day.strftime('%b %d'))
                counts.append(count)

        elif is_lab:
            # Only last 7 days
            chart_title = _("Lab Requests Trend")
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                start_dt = fields.Datetime.to_string(datetime.combine(day, datetime.min.time()))
                end_dt = fields.Datetime.to_string(datetime.combine(day, datetime.max.time()))

                count = self.env['hms.lab.request'].search_count([
                    ('date_requested', '>=', start_dt),
                    ('date_requested', '<=', end_dt)
                ])
                days.append(day.strftime('%b %d'))
                counts.append(count)

        return {
            'case_labels': case_labels,
            'case_values': case_values,
            'trend_labels': days,
            'trend_values': counts,
            'trend_title': chart_title,
        }
    def _get_user_activities(self):
        """Fetch activities for the current user, safely handling priority."""
        activities = self.env['mail.activity'].search([
            ('user_id', '=', self.env.user.id),
            ('date_deadline', '>=', fields.Date.today())
        ], order='date_deadline asc', limit=10)

        # Map selection values to display names and CSS classes
        priority_map = {
            '0': ('Normal', 'secondary'),
            '1': ('Low', 'info'),
            '2': ('High', 'warning'),
            '3': ('Very High', 'danger'),
        }

        activity_data = []
        for activity in activities:
            priority = None
            priority_name = ''
            priority_class = 'secondary'

            # Safety check
            if hasattr(activity, 'priority'):
                priority = activity.priority
                name, css = priority_map.get(priority, ('', 'secondary'))
                priority_name = name
                priority_class = css

            activity_data.append({
                'id': activity.id,
                'res_model': activity.res_model,
                'res_id': activity.res_id,
                'res_name': activity.res_name,
                'summary': activity.summary or _('Activity'),
                'note': activity.note or '',
                'date_deadline': fields.Date.to_string(activity.date_deadline),
                'priority': priority,
                'priority_name': priority_name,
                'priority_class': priority_class,
            })
        return activity_data
    @api.model
    def action_open_my_activities(self):
        """Action to open activities filtered by current user"""
        action = self.env.ref('mail.mail_activity_action').read()[0]
        action['context'] = {
            'search_default_user_id': self.env.user.id,
            'search_default_today': True,
        }
        action['domain'] = [('user_id', '=', self.env.user.id)]
        return action