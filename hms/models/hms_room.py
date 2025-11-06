from odoo import models, fields, api, _


class HmsRoom(models.Model):
    _name = 'hms.room'
    _description = _('Hospital Room')

    name = fields.Char(string=_('Room Number'), readonly=1)
    floor = fields.Integer(string=_('Floor'))
    capacity = fields.Integer(string=_('Capacity'))
    department_id = fields.Many2one('hr.department', string=_('Department'))

    # تُحسب تلقائياً من حالة الأسرة (لا حاجة لتعديلها يدوياً)
    is_occupied = fields.Boolean(
        string=_('Occupied'),
        compute='_compute_is_occupied',
        store=True,
        readonly=True,
    )

    bed_ids = fields.One2many('hms.bed', 'room_id', string=_('Beds'))

    can_edit = fields.Boolean(string='Can Edit', compute='_compute_can_edit', store=False)

    # <<< جديد: علم للتحكّم بالزر >>>
    out_of_service = fields.Boolean(string=_('Out of Service'), default=False, tracking=True)
    beds_total = fields.Integer(string=_('Beds (Total)'), compute='_compute_bed_stats', store=True)
    beds_occupied = fields.Integer(string=_('Beds (Occupied)'), compute='_compute_bed_stats', store=True)
    occupancy_rate = fields.Float(string=_('Occupancy (%)'), compute='_compute_bed_stats', store=True)
    number_of_available_beds = fields.Integer(string=_('Beds (Available)'), compute='_compute_available_beds', store=True)
    can_mark_out_of_service = fields.Boolean(
        string="Can Mark Out of Service",
        compute="_compute_can_mark_out_of_service",
        store=False
    )
    @api.depends('beds_occupied')
    def _compute_can_mark_out_of_service(self):
        for room in self:
            room.can_mark_out_of_service = room.beds_occupied == 0
    @api.depends('bed_ids.state')
    def _compute_available_beds(self):
        for room in self:
            room.number_of_available_beds = sum(1 for b in room.bed_ids if b.state == 'available')

    @api.depends('bed_ids.state')
    def _compute_bed_stats(self):
        for room in self:
            total = len(room.bed_ids)
            occ = sum(1 for b in room.bed_ids if b.state == 'occupied')
            room.beds_total = total
            room.beds_occupied = occ
            room.occupancy_rate = (occ * 100.0 / total) if total else 0.0

    @api.depends('bed_ids.state')
    def _compute_is_occupied(self):
        for room in self:
            room.is_occupied = any(b.state == 'occupied' for b in room.bed_ids)
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.department_id:
                total_rooms = self.search_count([("department_id", "=", record.department_id.id)])
                record.name = f"{record.department_id.name} - Room {total_rooms}" or _("New Room")
                record.display_name = f"{record.department_id.name} - Room {total_rooms}" or _("New Room")
        return records


    # <<< جديد: أزرار الواجهة >>>
    def action_mark_out_of_service(self):
        """يظهر فقط لما الغرفة مش Out of Service"""
        self.write({'out_of_service': True})
        return True

    def action_back_in_service(self):
        """يظهر فقط لما الغرفة Out of Service"""
        self.write({'out_of_service': False})
        return True

    def _compute_can_edit(self):
        for room in self:
            room.can_edit = self.env.user.has_group('hms.group_hms_receptionist')

