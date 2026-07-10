from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DesignRejectWizard(models.TransientModel):
    _name = 'design.reject.wizard'
    _description = 'Wizard Penolakan Design'

    usulan_id = fields.Many2one('design.usulan', string='Usulan Design', required=True)
    reason = fields.Text(string='Alasan Penolakan', required=True)

    def action_confirm_reject(self):
        rec = self.usulan_id
        if rec.state not in ('approval_marketing', 'approval_client', 'approval_ro', 'upload_form'):
            raise UserError(_('Record ini tidak bisa di-reject pada state saat ini.'))
        rec.write({
            'state': 'reject',
            'reject_reason': self.reason,
            'rejected_by': self.env.user.id,
            'rejected_date': fields.Datetime.now(),
        })
        rec.message_post(body=_('❌ Ditolak oleh %s.\nAlasan: %s') % (self.env.user.name, self.reason))
        return {'type': 'ir.actions.act_window_close'}
