from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta

class MedicalNote(models.Model):
    _name = 'hms.note'
    _description = 'Medical Note'
    _order = 'create_date desc'

    name= fields.Char(string="Title", required=True, default="New")

    case_id = fields.Many2one('hms.case', string="Case")
    medical_record_id = fields.Many2one('hms.medical.record', string="Medical Record")
    lab_request_id = fields.Many2one(
    'hms.lab.request',
    string="Lab Request",
    domain="[('case_id', '=', case_id)]"
)
    prescription_id = fields.Many2one('hms.prescription', string="Prescription", domain="[('case_id', '=', case_id)]")
    lab_result_id = fields.Many2one('hms.lab.result', string="Lab Result", domain="[('case_id', '=', case_id)]")    
    role = fields.Selection([
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('receptionist', 'Receptionist'),
        ('lab', 'Lab Technician'),
        ('other', 'Other'),
    ], string="Author Role", readonly=True, default=lambda self: self._default_role())
    note_type = fields.Selection([
        ('general', 'General'),
        ('medical_history', 'Medical History'),
        ('consultation', 'Consultation'),
        ('lab_result', 'Lab Result'),
        ('prescription', 'Prescription'),
        ('vitals', 'Vitals'),
    ], string="Note Type", default='general')
    user_id = fields.Many2one('res.users', string="Author", readonly=True)
    note = fields.Html("Note")
    note_acc = fields.Html("Note", readonly=True)
    create_date = fields.Datetime("Date", readonly=True,default=fields.Datetime.now() )
    is_important = fields.Boolean("Important")
    show_in_portal = fields.Boolean("Visible to Patient")

    @api.model
    def _default_role(self):
        """Detect the user’s role automatically based on groups."""
        user = self.env.user
        if user.has_group('hms.group_hms_doctor'):
            return 'doctor'
        elif user.has_group('hms.group_hms_nurse'):
            return 'nurse'
        elif user.has_group('hms.group_hms_receptionist'):
            return 'receptionist'
        elif user.has_group('hms.group_hms_lab'):
            return 'lab'
        return 'other'

    @api.constrains('note_type', 'medical_record_id')
    def _check_unique_medical_history(self):
        """ Ensure only one Medical History per patient """
        for note in self:
            if note.note_type == 'medical_history' and note.medical_record_id:
                existing = self.search([
                    ('id', '!=', note.id),
                    ('note_type', '=', 'medical_history'),
                    ('medical_record_id', '=', note.medical_record_id.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _("A Medical History already exists for this patient’s record.")
                    )
    @api.constrains('note_type', 'case_id')
    def _check_unique_vitals(self):
        """For nurse vitals, only one entry per case per timestamp."""
        for note in self:
            if note.note_type == 'vitals' and note.case_id:
                existing = self.search([
                    ('id', '!=', note.id),
                    ('note_type', '=', 'vitals'),
                    ('case_id', '=', note.case_id.id),
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _("Vitals for this case already recorded at this time.")
                    )

    @api.model_create_multi
    def create(self, vals_list):
        cleaned_vals_list = []
        note_entries = []

        for vals in vals_list:
            vals = dict(vals)  # make mutable copy

            # extract note if exists
            note_entry = vals.pop('note', None)
            note_entries.append(note_entry)

            cleaned_vals_list.append(vals)

        # create all records at once
        records = super().create(cleaned_vals_list)

        # post-processing per record
        for record, note_entry in zip(records, note_entries):

            # assign creator
            record.user_id = self.env.user

            # append note if provided
            if note_entry:
                record._append_note(note_entry)

            # send notifications if important
            if record.is_important and record.case_id:
                doctor_user = record.case_id.main_doctor_id.user_id
                nurse_user = record.case_id.nurse_id.user_id

                msg = f"Important {record.note_type} note added by {record.role}.{record.user_id.name} : {record.note}"

                record.send_inbox_notification(
                    doctor_user,
                    msg,
                    fields.Datetime.now() + timedelta(minutes=30),
                )
                record.send_inbox_notification(
                    nurse_user,
                    msg,
                    fields.Datetime.now() + timedelta(minutes=30),
                )

        return records

    def write(self, vals):
        note_entry = vals.pop('note', None)
        res = super().write(vals)
        if note_entry:
            for rec in self:
                rec._append_note(note_entry)
                if rec.is_important and rec.case_id:
                    rec.send_inbox_notification(rec.case_id.main_doctor_id.user_id, f"Important {rec.note_type} note added by {rec.role}.{rec.user_id.name} : {rec.note}", fields.Datetime.now + timedelta(minutes=30))
                    rec.send_inbox_notification(rec.case_id.nurse_id.user_id, f"Important {rec.note_type} note added by {rec.role}.{rec.user_id.name} : {rec.note}", fields.Datetime.now + timedelta(minutes=30))
        return res

    def _append_note(self, entry_text):
        """Append new entry to accumulated note with author, role, timestamp."""
        entry_text = entry_text.strip()
        if not entry_text:
            return
        entry_header = f" {self.env.user.name} ({fields.Datetime.now()}):"
        entry_body = entry_text
        new_content = f"{entry_header}\n{entry_body}\n-----------------------\n"
        self.note_acc = (self.note_acc or "") + new_content
        self.note = False  
    


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