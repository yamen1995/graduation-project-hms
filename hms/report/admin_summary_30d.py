# -*- coding: utf-8 -*-
from odoo import api, models, fields
from dateutil.relativedelta import relativedelta

# ↓↓↓ إضافات مهمة لدوال التنسيق ↓↓↓
from odoo.tools.misc import (
    format_date as odoo_format_date,
    format_datetime as odoo_format_datetime,
    formatLang as odoo_format_lang,
)

class ReportAdminSummary30d(models.AbstractModel):
    _name = 'report.hms.report_admin_summary_30d'
    _description = 'HMS: Admin Summary (last 30 days)'

    @api.model
    def _get_report_values(self, docids, data=None):
        now = fields.Datetime.now()
        start = now - relativedelta(days=30)

        Partner = self.env['res.partner'].sudo()
        Case = self.env['hms.case'].sudo()
        Appt = self.env['hms.appointment'].sudo()
        Pres = self.env['hms.prescription'].sudo()
        LabReq = self.env['hms.lab.request'].sudo()
        LabRes = self.env['hms.lab.result'].sudo()

        # KPIs
        kpis = {
            'patients_new': Partner.search_count([
                ('is_patient', '=', True),
                ('create_date', '>=', start), ('create_date', '<=', now)
            ]),
            'admissions': Case.search_count([
                ('admission_date', '>=', start), ('admission_date', '<=', now)
            ]),
            'discharges': Case.search_count([
                ('discharge_date', '>=', start), ('discharge_date', '<=', now)
            ]),
            'active_cases': Case.search_count([('state', '=', 'active')]),
            'appointments_confirmed': Appt.search_count([
                ('date', '>=', start), ('date', '<=', now),
                ('state', '=', 'confirmed')
            ]),
            'prescriptions': Pres.search_count([
                ('date', '>=', start), ('date', '<=', now)
            ]),
            'lab_requests': LabReq.search_count([
                ('date_requested', '>=', start), ('date_requested', '<=', now)
            ]),
            'lab_results': LabRes.search_count([
                ('create_date', '>=', start), ('create_date', '<=', now)
            ]),
        }

        # Top 5 Doctors by Admissions
        top_doctors = []
        try:
            groups = Case.read_group(
                [('admission_date', '>=', start), ('admission_date', '<=', now)],
                ['id:count'], ['main_doctor_id'], limit=5, orderby='id_count desc'
            )
            for g in groups:
                if g.get('main_doctor_id'):
                    top_doctors.append({
                        'doctor_id': int(g['main_doctor_id'][0]),
                        'doctor_name': g['main_doctor_id'][1],
                        'count': g.get('id_count', 0),
                    })
        except Exception:
            top_doctors = []

        # Average Length of Stay
        los_days = 0.0
        los_count = 0
        closed_cases = Case.search([
            ('discharge_date', '>=', start), ('discharge_date', '<=', now),
            ('admission_date', '!=', False)
        ], limit=5000)
        for c in closed_cases:
            try:
                delta = (c.discharge_date or c.create_date) - (c.admission_date or c.create_date)
                if delta:
                    los_days += (delta.total_seconds() / 86400.0)
                    los_count += 1
            except Exception:
                continue
        avg_los = round(los_days / los_count, 2) if los_count else 0.0

        return {
            'start': start,
            'end': now,
            'company': self.env.company,
            'kpis': kpis,
            'avg_los': avg_los,
            'top_doctors': top_doctors,

            # ↓↓↓ نمرّر دوال التنسيق للقالب QWeb ↓↓↓
            'format_date':      lambda d, date_format=None, lang_code=False: odoo_format_date(self.env, d, date_format=date_format, lang_code=lang_code),
            'format_datetime':  lambda dt, tz=False, lang_code=False: odoo_format_datetime(self.env, dt, tz=tz or (self.env.user.tz or False), lang_code=lang_code),
            'formatLang':       lambda value, digits=None, grouping=True, monetary=False, currency=None: odoo_format_lang(self.env, value, digits=digits, grouping=grouping, monetary=monetary, currency_obj=currency),
        }
