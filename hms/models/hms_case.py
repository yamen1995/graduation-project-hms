from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
from odoo.tools import html2plaintext


class HmsCase(models.Model):
    _name = 'hms.case'
    _description = 'Patient Case'
    _inherit = ['mail.thread','mail.activity.mixin']

    name = fields.Char(
        string="Case ID", required=True, copy=False, readonly=True,
        default=lambda self: 'New'
    )

    medical_record_id = fields.Many2one(
        'hms.medical.record', string='Medical Record', required=True,
    )

    patient_id = fields.Many2one('res.partner', string='Patient',
                                  related='medical_record_id.patient_id', store=True)
    
    # Add insurance field - assuming it's stored on the patient
    insurance_id = fields.Many2one(
        'hms.insurance', string='Insurance',
        related='patient_id.insurance_id', readonly=True
    )
    insurance_coverage = fields.Float(
        string='Insurance Coverage (%)',
        related='insurance_id.coverage_percentage', readonly=True
    )

    main_doctor_id = fields.Many2one(
        'hr.employee', string='Main Doctor',
        domain="[('hms_role_id.name', '=', 'Doctor')]", tracking=True, required=True
    )
    nurse_id = fields.Many2many(
        'hr.employee', string='Nurses',
        domain="[('hms_role_id.name', '=', 'Nurse')]", tracking=True
    )
    consulting_doctor_ids = fields.Many2many(
        'hr.employee', 'hms_case_doctor_rel',
        'case_ids', 'doctor_id',
        string='Consulting Doctors',
        domain="[('hms_role_id.name', '=', 'Doctor')]"
    )

    appointment_id = fields.Many2one('hms.appointment', string='Related Appointment')

    # Diagnosis
    diagnosis_ids = fields.Many2many('hms.disease', string='Diagnosis')
    diagnosis_text = fields.Html(string="Diagnosis (Text)", placeholder="Enter diagnosis details here...")

    case_note_ids = fields.One2many('hms.note', 'case_id', string="Case Notes")

    admission_date = fields.Datetime(string='Admission Date' ,default=fields.Datetime.now)
    discharge_date = fields.Datetime(string='Discharge Date')

    stay_days = fields.Integer(string="Stay Days", compute="_compute_stay_days", store=True)


    bed_id = fields.Many2one(
        'hms.bed', string='Bed',
        domain="[('state', '=', 'available')]"
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string='Status', default='draft', tracking=True)

    prescription_ids = fields.One2many('hms.prescription', 'case_id', string="Prescriptions")
    lab_request_ids = fields.One2many('hms.lab.request', 'case_id', string="Lab Requests")
    lab_result_ids = fields.One2many(related="lab_request_ids.lab_result_ids", string="Lab Results")
    consumable_line_ids = fields.One2many('hms.consumable.line', 'case_id', string="Consumables")
    room_id = fields.Many2one('hms.room', string='Room')

    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    insurance_covered = fields.Float(string='Insurance Covered', compute='_compute_insurance_covered', store=True)
    patient_share = fields.Float(string='Patient Share', compute='_compute_patient_share', store=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)

    new_results = fields.Boolean(
        string="New Lab Results",
        default=False,
        help="True if there are new lab results for doctor to review"
    )
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, store=False)
    can_edit_diagnosis = fields.Boolean(compute='_compute_edit_rights', store=False)
    created_by = fields.Many2one('res.users', string='Created By',  store=True)
    can_edit_labs = fields.Boolean(compute='_compute_edit_rights', store=False)
    can_edit_consumables = fields.Boolean(compute='_compute_edit_rights', store=False)
    can_edit_prescriptions = fields.Boolean(compute='_compute_edit_rights', store=False)
    can_edit_team = fields.Boolean(compute='_compute_edit_rights', store=False)
    can_edit_logistics = fields.Boolean(compute='_compute_edit_rights', store=False)
    medical_history_note = fields.Html(
        string='Medical History', store=True, readonly=False,
    )
    vitals_note = fields.One2many('hms.vital.signs', 'case_id', string="Vitals Notes", help="vitals note for this case.", store=True)
    general_note = fields.Html(
        string='General Note', store=True, readonly=False,
    )
    disease_history = fields.Many2many('hms.disease', related='medical_record_id.disease_ids', string="Known Diseases", readonly=True)
    allergies = fields.Text(related='medical_record_id.allergies', string="Allergies", readonly=True)
    blood_type = fields.Selection(related='medical_record_id.blood_type', string="Blood Type", readonly=True)
    medication_ids = fields.Many2many('product.product', related='medical_record_id.medication_ids', string="Current Medications", readonly=True)
    consultation_note = fields.One2many('hms.consultation', 'case_id', string="Consultation Notes", help="consultation notes for this case.", store=True)
    insurance_id = fields.Many2one(
        'hms.insurance', string='Insurance',
        related='patient_id.insurance_id', readonly=True
    )
    insurance_coverage = fields.Float(
        string='Insurance Coverage (%)',
        related='insurance_id.coverage_percentage', readonly=True
    )
    insurance_covered = fields.Float(string='Insurance Covered', compute='_compute_insurance_covered', store=True)
    patient_share = fields.Float(string='Patient Share', compute='_compute_patient_share', store=True)
    can_approve_invoice = fields.Boolean(
    compute="_compute_can_approve_invoice", store=False
)
    sale_order_id = fields.Many2one("sale.order", string="Sale Order")
    doctor_task_id = fields.Many2one("project.task")
    nurse_task_id = fields.Many2one("project.task", string="Nurse Task")
    doctor_timesheet_ids = fields.One2many(related='doctor_task_id.timesheet_ids',readonly=False, string="Doctor Timesheets")
    nurse_timesheet_ids = fields.One2many(related='nurse_task_id.timesheet_ids',readonly=False, string="Nurse Timesheets")


    # ----------------------------
    # COMPUTES
    # ----------------------------
    def _compute_can_approve_invoice(self):
        for rec in self:
            rec.can_approve_invoice = bool(
                rec.invoice_id and rec.invoice_id.state == "draft"
            )



    @api.depends('admission_date', 'discharge_date')
    def _compute_stay_days(self):
        for case in self:
            if case.admission_date and case.discharge_date:
                delta = case.discharge_date.date() - case.admission_date.date()
                case.stay_days = delta.days + 1  # at least 1 day
            else:
                case.stay_days = 0

    @api.depends('total_cost', 'insurance_coverage')
    def _compute_insurance_covered(self):
        for case in self:
            if case.insurance_id and case.insurance_coverage > 0:
                case.insurance_covered = case.total_cost * (case.insurance_coverage / 100)
            else:
                case.insurance_covered = 0

    @api.depends('total_cost', 'insurance_covered')
    def _compute_patient_share(self):
        for case in self:
            case.patient_share = case.total_cost - case.insurance_covered

    @api.depends(
        'prescription_ids.prescription_line_ids.quantity',
        'lab_request_ids.lab_request_line_ids',
        'consumable_line_ids.quantity'
    )
    def _compute_total_cost(self):
        for case in self:
            prescription_cost = sum(
                line.product_id.list_price * line.quantity
                for prescription in case.prescription_ids
                for line in prescription.prescription_line_ids
            )
            lab_cost = sum(
                line.product_id.list_price
                for lab in case.lab_request_ids
                for line in lab.lab_request_line_ids
            )
            consumable_cost = sum(
                line.product_id.list_price * line.quantity
                for line in case.consumable_line_ids
            )
            case.total_cost = prescription_cost + lab_cost + consumable_cost
            
    @api.depends('user_id')
    def _compute_edit_rights(self):
        for rec in self:
            rec.can_edit_diagnosis = rec.user_id.has_group('hms.group_hms_doctor') or rec.user_id.has_group('base.group_system')
            rec.can_edit_labs = rec.user_id.has_group('hms.group_hms_doctor') or rec.user_id.has_group('hms.group_hms_lab') or rec.user_id.has_group('hms.group_hms_nurse') or rec.user_id.has_group('base.group_system')
            rec.can_edit_consumables = rec.user_id.has_group('hms.group_hms_nurse') or rec.user_id.has_group('base.group_system')
            rec.can_edit_prescriptions = rec.user_id.has_group('hms.group_hms_doctor') or rec.user_id.has_group('hms.group_hms_chemist') or rec.user_id.has_group('base.group_system')
            rec.can_edit_team = rec.user_id.has_group('hms.group_hms_receptionist') or rec.user_id.has_group('base.group_system')
            rec.can_edit_logistics = rec.user_id.has_group('hms.group_hms_receptionist') or rec.user_id.has_group('hms.group_hms_doctor') or rec.user_id.has_group('base.group_system')
            
    @api.onchange('main_doctor_id')
    def _onchange_main_doctor_id(self):
        """Filter rooms by the doctor's department"""
        if self.main_doctor_id and self.main_doctor_id.department_id:
            return {
                'domain': {
                    'bed_id': [('bed_id.department_id', '=', self.main_doctor_id.department_id.id)]
                }
            }
        return {'domain': {'bed_id': []}}

    
    @api.onchange('admission_date')
    def _onchange_date_update_available_doctors(self):
        for rec in self:
            if not rec.admission_date:
                continue
            all_doctors = self.env['hr.employee'].search([('hms_role_id.code', '=', 'doctor')])
            busy_doctors = self.env['hms.appointment'].search([('date', '=', rec.admission_date), ('state', '!=', 'canceled')]).mapped('doctor_id')
            available_doctors = all_doctors - busy_doctors
            return {'domain': {'doctor_id': [('id', 'in', available_doctors.ids)]}}
    # ----------------------------
    # CREATE / WRITE OVERRIDES
    # ----------------------------

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.patient_id:
            case_count = self.search_count([('patient_id', '=', record.patient_id.id)])
            record.name = f"CR/{record.patient_id.name}_#{case_count}"
        record.created_by = self.env.user
        if self.env.context.get("from_appointment_id"):
            appointment = self.env["hms.appointment"].browse(self.env.context["from_appointment_id"])
            appointment.case_id = record.id
            appointment.state = 'in_progress'
            record.appointment_id = appointment.id
            record.send_inbox_notification(appointment.doctor_id.user_id, _("Your patient scheduled for :%s name: %s has arrived at room: %s case : %s") % (appointment.date, record.patient_id.name, record.room_id.name if record.room_id else 'N/A', record.name), appointment.date + timedelta(hours=1))


        elif record.main_doctor_id and record.main_doctor_id.user_id:
            record.send_inbox_notification(record.sudo().main_doctor_id.user_id, _("You have a new patient: %s at room: %s case : %s") % (record.patient_id.name, record.room_id.name if record.room_id else 'N/A', record.name), record.admission_date + timedelta(hours=1))
        if not record.sale_order_id:
            so = self.env['sale.order'].create({
                'partner_id': record.patient_id.id,   # FIXED
                'origin': record.name,                # FIXED
            })
            record.sale_order_id = so.id 
            doctor_timesheet_product = self.env.ref("hms.doctor_timesheet_service")
            nurse_timesheet_product = self.env.ref("hms.nurse_timesheet_service")
    
            so_line = self.env['sale.order.line'].create({
                'order_id': so.id,
                'product_id': doctor_timesheet_product.id,
                'product_uom_qty': 1,
                'price_unit': record.main_doctor_id.hourly_rate if record.main_doctor_id.hourly_rate else doctor_timesheet_product.list_price,
            })
            if record.nurse_id:
                so_line_2 = self.env['sale.order.line'].create({
                    'order_id': so.id,
                    'product_id': nurse_timesheet_product.id,
                    'product_uom_qty': 1,
                    'price_unit': record.nurse_id[0].hourly_rate if record.nurse_id[0].hourly_rate else nurse_timesheet_product.list_price,
                })
            so.action_confirm()
            record.doctor_task_id = so_line.task_id.id
            if record.nurse_id:
                record.nurse_task_id = so_line_2.task_id.id
            
        record.bed_id.state = 'occupied'
        record.room_id = record.bed_id.room_id
        record._update_medical_record()


        return record

    def write(self, vals):

        old_beds = {case.id: case.bed_id for case in self}

        if 'state' in vals and vals['state'] == 'closed':
            for case in self:
                if not case.diagnosis_ids and not case.diagnosis_text:
                    raise UserError(_("You cannot close a case without a diagnosis (either textual or disease)."))
                
                
                
                
        
        res = super().write(vals)
        
        for case in self:
            new_bed = case.bed_id
            old_bed = old_beds.get(case.id)

            if 'bed_id' in vals:
                if old_bed and old_bed != new_bed and old_bed.state == 'occupied':
                    old_bed.state = 'available'
                if new_bed and new_bed.state != 'occupied':
                    if new_bed.state != 'available':
                        raise UserError(_("Selected bed is not available."))
                    new_bed.state = 'occupied'
                    case.room_id = new_bed.room_id

            if 'state' in vals and case.state == 'closed' and case.bed_id:
                case.bed_id.state = 'available'
            case._update_medical_record()

        return res

    # ----------------------------
    # ACTIONS
    # ----------------------------

    def action_activate(self):
        self.state = 'active'

    def action_reject(self):
        self.state = 'closed'

    def action_close(self):

        # Check if lab tests exist - ensure they are completed

        if self.lab_request_ids:
            pending_labs = self.lab_request_ids.filtered(
                lambda r: r.state != 'completed'
            )
            if pending_labs:
                lab_names = ", ".join(pending_labs.mapped('name'))
                raise UserError(_(
                    "Cannot close case with pending lab tests. "
                    "The following lab requests are not completed: %s. "
                    "Please ensure all lab tests are completed."
                ) % lab_names)

        # Check if prescriptions exist - ensure they are approved
        if self.prescription_ids:
            pending_prescriptions = self.prescription_ids.filtered(
                lambda p: p.state != 'dispensed'
            )
            if pending_prescriptions:
                prescription_names = ", ".join(pending_prescriptions.mapped('name'))
                raise UserError(_(
                    "Cannot close case with unapproved prescriptions. "
                    "The following prescriptions are not approved: %s. "
                    "Please ensure all prescriptions are approved."
                ) % prescription_names)

        
        
        self.state = 'closed'
        self.discharge_date =  fields.Datetime.now()
        self.send_inbox_notification(self.sudo().nurse_id.user_id, _(f"patient {self.patient_id.name} at room: {self.room_id.name if self.room_id else 'N/A'} was discharged"), self.discharge_date + timedelta(hours=1))
        self.send_inbox_notification(self.sudo().created_by.user_id, _(f"patient {self.patient_id.name} at room: {self.room_id.name if self.room_id else 'N/A'} was discharged"), self.discharge_date + timedelta(hours=1))

        # Compute stay_days when closing
        self._compute_stay_days()

        if self.stay_days and self.stay_days > 0:
            staydays_product = self.env.ref("hms.product_room_stay")
            self.env['sale.order.line'].create({
                'order_id': self.sale_order_id.id,
                'product_id': staydays_product.id,
                'product_uom_qty': self.stay_days,
                'price_unit': staydays_product.list_price,
            })
        if self.insurance_id and self.insurance_coverage > 0:
                insurance_discount = - (self.total_cost * (self.insurance_coverage / 100))
                
                # Get or create insurance product
                insurance_product = self.env['product.product'].search(
                    [('default_code', '=', 'INSURANCE_COVERAGE')], limit=1)
                
                if not insurance_product:
                    insurance_product = self.env['product.product'].create({
                        'name': 'Insurance Coverage',
                        'default_code': 'INSURANCE_COVERAGE',
                        'type': 'service',
                        'list_price': 0,
                    })
                self.env['sale.order.line'].create({
                    'order_id': self.sale_order_id.id,
                    'product_id': insurance_product.id,
                    'product_uom_qty': 1,
                    'price_unit': insurance_discount,
                })
        for line in self.consumable_line_ids:
            self.env['sale.order.line'].create({
                'order_id': self.sale_order_id.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'price_unit': line.product_id.list_price,
            })
            for picking in self.sale_order_id.picking_ids:
                    picking.button_validate()   
        if not self.invoice_id:
            invoice = self.sale_order_id._create_invoices()  # uses Odoo's sale.order method to generate invoice
            self.invoice_id = invoice.id

    def action_approve_invoice(self):
        for case in self:
            if case.invoice_id and case.invoice_id.state == 'draft':
                case.sudo().invoice_id.action_post()
               
    def mark_results_seen(self):
        for case in self:
            if self.env.user.has_group('hms.group_hms_doctor') and case.main_doctor_id.user_id.id == self.env.user.id:
                case.new_results = False

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            record_id = self.env.context.get('active_id')
            if record_id:
                self.browse(record_id).mark_results_seen()
        return res

    


    def send_inbox_notification(self, user_id, message_body, date_deadline):
        """Send hospital-specific inbox notification."""
        if not user_id:
            return

        self.sudo().activity_schedule(
            summary=f"Hospital Notification",
            note=f"<div>{message_body}",
            user_id=user_id.id,
            date_deadline= date_deadline,
        )
        


    @api.constrains('main_doctor_id', 'admission_date', 'state')
    def _check_doctor_case_overlap(self):
        for rec in self:
            if rec.main_doctor_id and rec.admission_date and rec.state != 'closed':
                # define 30-minute window
                window_start = rec.admission_date - timedelta(minutes=30)
                window_end = rec.admission_date + timedelta(minutes=30)

                # search other cases for the same doctor
                overlapping_cases = self.search([
                    ('id', '!=', rec.id),
                    ('main_doctor_id', '=', rec.main_doctor_id.id),
                    ('state', '!=', 'closed'),
                    ('admission_date', '>=', window_start),
                    ('admission_date', '<=', window_end),
                ])

                if overlapping_cases:
                    raise ValidationError(
                        _("Doctor %s is already assigned to another case (%s) "
                          "within 30 minutes of this admission time.")
                        % (rec.main_doctor_id.name, overlapping_cases[0].name)
                    )
    def action_print_case_summary(self):
        self.ensure_one()

        lang = (self.env.context.get('lang') or self.env.user.lang or 'en_US')
        is_ar = str(lang).lower().startswith('ar')

        candidates = (
            ['hms.action_report_case_summary_ar', 'hms.action_report_case_summary_en']
            if is_ar else
            ['hms.action_report_case_summary_en', 'hms.action_report_case_summary_ar']
        )

        for xmlid in candidates:
            try:
                report = self.env.ref(xmlid)
                forced_lang = 'ar' if xmlid.endswith('_ar') else 'en_US'
                return report.with_context(lang=forced_lang).report_action(self)
            except ValueError:
                continue

        raise UserError(_("Case Summary report action not found. Please install or update the HMS reports."))
    def _update_medical_record(self):
            for case in self:
                medrec = case.medical_record_id
                if not medrec:
                    continue

                # -----------------------
                # 1. Update disease history
                # -----------------------
                if case.diagnosis_ids:
                    medrec.sudo().write({
                        'disease_ids': [(4, d.id) for d in case.diagnosis_ids]
                    })
                if case.diagnosis_text:
                    existing_note = html2plaintext(medrec.sudo().allergies or "")
                    diagnosis_text = html2plaintext(case.diagnosis_text)

                    updated_note = f"{existing_note}\n{diagnosis_text}".strip()

                    medrec.sudo().write({
                        'allergies': updated_note
                    })

                # -----------------------
                # 2. Update medication history
                # -----------------------
                all_med_products = case.prescription_ids.mapped(
                    'prescription_line_ids.product_id'
                )

                if all_med_products:
                    # Assuming a many2many medication field on medical record
                    medrec.sudo().write({
                        'medication_ids': [(4, p.id) for p in all_med_products]
                    })

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice found for this case."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }