# -*- coding: utf-8 -*-
from odoo import api, models, fields
from dateutil.relativedelta import relativedelta

class ReportMedRecsLast7(models.AbstractModel):
    _name = 'report.hms.report_medrecs_last7'  # لازم يطابق report_name في XML
    _description = 'HMS: Medical Records — last 7 days (latest case per patient)'

    @api.model
    def _get_report_values(self, docids, data=None):
        now = fields.Datetime.now()
        start = now - relativedelta(days=7)

        Case = self.env['hms.case'].sudo()
        cases = Case.search([
            '|',
            ('admission_date', '>=', start),
            ('create_date', '>=', start),
        ], order='admission_date desc, create_date desc, id desc')

        rows, seen = [], set()
        for c in cases:
            patient = getattr(c, 'patient_id', False)
            pid = patient.id if patient else False
            if not pid or pid in seen:
                continue
            seen.add(pid)
            rows.append({
                'patient': patient,                              # record: res.partner (مريض)
                'medical_record': getattr(c, 'medical_record_id', False),  # سجل طبي مرتبط
                'case': c,                                       # record: hms.case
                'admission': c.admission_date or c.create_date,  # datetime
            })

        return {
            'rows': rows,
            'start': start,
            'end': now,
            'company': self.env.company,
        }
