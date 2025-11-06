# hms/models/account_move.py
from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_invoice_print(self):
        self.ensure_one()
        if self.move_type in ('out_invoice','out_refund','in_invoice','in_refund'):
            action = self.env.ref('hms.action_report_invoice_hms', raise_if_not_found=False)
            if action:
                return action.report_action(self)
        return super().action_invoice_print()
