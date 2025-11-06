from datetime import timedelta
from odoo import models, fields, _, api

class HmsBed(models.Model):
    _name = "hms.bed"
    _description = _("Hospital Bed")
    _order = "name"
    _rec_name = "name"  # خلّي Odoo يستخدم اسم العرض الافتراضي

    name = fields.Char(string=_("Bed Name/Number"), index=True, readonly=1)
    room_id = fields.Many2one("hms.room", string=_("Room"), ondelete="restrict", required=True)
    state = fields.Selection(
        [("available", _("Available")), ("occupied", _("Occupied")), ("maintenance", _("Maintenance"))],
        string=_("Status"), default="available", required=True
    )

    # يظهر القسم تلقائياً من الغرفة
    department_id = fields.Many2one(
        "hr.department", string=_("Department"),
        related="room_id.department_id", store=True, readonly=True
    )
    can_edit = fields.Boolean(string='Can Edit', compute='_compute_can_edit', store=False)


    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.department_id:
                total_beds = self.search_count([("room_id", "=", record.room_id.id),])
                record.name = f"{record.room_id.name} - bed {total_beds}" or _("New bed")
        return records



    
    def action_oof_bed(self):
        """Action to take when a bed is marked as out of service."""
        for bed in self:
            if bed.state != 'maintenance':
                bed.state = 'maintenance'
            rece = self.env['hr.employee'].search([('hms_role_id.name', '=', 'Receptionist')])
            for rec in rece:
                if rec.user_id:
                    bed.send_inbox_notification(
                    user_id=rec.user_id,
                    message_body=_("Bed %s is now out of service") % bed.name,
                    date_deadline=fields.Datetime.now() + timedelta(days=1)
                )
    
    def action_restore_bed(self):
        """Action to take when a bed is restored."""
        for bed in self:
            if bed.state == 'maintenance':
                bed.state = 'available'

    def send_inbox_notification(self, user_id, message_body, date_deadline):
        """Schedule a mail.activity for the user so doctor sees it in their ToDos."""
        if not user_id:
            return
        try:
            self.activity_schedule(
                activity_type_xmlid="hms.mail_activity_hms_notice",
                summary=_("Hospital Notification"),
                note=f"<div>{message_body}",
                user_id=user_id.id,
                date_deadline=date_deadline,
            )
        except Exception:
            # don't raise on notification failures
            _logger = __import__('logging').getLogger(__name__)
            _logger.exception("Failed to schedule activity for user %s", getattr(user_id, 'id', False))
        
    def _compute_can_edit(self):
        for room in self:
            room.can_edit = self.env.user.has_group('hms.group_hms_receptionist')

