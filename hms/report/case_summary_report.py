from odoo import models
from odoo.tools.translate import _
class ReportCaseSummaryEN(models.AbstractModel):
    _name = 'report.hms.report_case_summary'
    _description = 'Case Summary Report '
    def _get_report_values(self, docids, data=None):
        docs = self.env['hms.case'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hms.case',
            'docs': docs,
            '_': _,
        }