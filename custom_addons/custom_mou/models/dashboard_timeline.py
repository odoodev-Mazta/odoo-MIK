from odoo import models,fields,api

class DashboardTimeline(models.Model):
    _name = 'dashboard.timeline.mou'
    _description = 'Timeline Progress MOU'

    @api.model
    def get_timeline_data(self):
        mous = self.env['draft.maklon'].search([('state', '=', 'mou')])
        timeline_list = []

        for mou in mous:
            # Ambil nama pelanggan dengan aman (mencegah res.partner(73,))
            pelanggan_name = "Unknown Customer"
            if mou.nama_cust:
                # Cek jika ini Many2one, ambil .name. Jika Char, langsung pakai.
                pelanggan_name = mou.nama_cust.name if hasattr(mou.nama_cust, 'name') else mou.nama_cust

            # Kumpulkan Setup Transaksi
            setups = self.env['mou.setup'].search([('mou_id', '=', mou.id)])
            setup_data = []
            for setup in setups:
                setup_data.append({
                    'id': setup.id,
                    'name': setup.name,
                    'state': setup.state,
                    'is_free': setup.is_free,

                    # Registrasi
                    'reg_due_date': fields.Date.to_string(setup.reg_due_date),
                    'reg_payment_date': fields.Date.to_string(setup.reg_payment_date),
                    'reg_nilai': setup.reg_nilai,

                    # DP
                    'dp_due_date': fields.Date.to_string(setup.dp_due_date),
                    'dp_payment_date': fields.Date.to_string(setup.dp_payment_date),
                    'dp_nilai': setup.dp_nilai,

                    # NIE
                    'nie_due_date': fields.Date.to_string(setup.nie_due_date),
                    'nie_payment_date': fields.Date.to_string(setup.nie_payment_date),
                    'nie_nilai': setup.nie_nilai,

                    # Pengadaan
                    'peng_due_date': fields.Date.to_string(setup.peng_due_date),
                    'peng_payment_date': fields.Date.to_string(setup.peng_payment_date),
                    'peng_nilai': setup.peng_nilai,
                })

            timeline_list.append({
                'id': mou.id,
                'pelanggan': pelanggan_name,
                'no_mou': mou.draft_name or '-',
                'tgl_draft': fields.Date.to_string(mou.tgl_draft) if mou.tgl_draft else fields.Date.to_string(
                    fields.Date.today()),
                'setups': setup_data,
            })

        return timeline_list

    # @api.model
    # def get_timeline_data(self):
    #     mous = self.env['draft.maklon'].search([('state', '=', 'mou')])
    #     timeline_list = []
    #
    #     for mou in mous:
    #         stages = [
    #             {'code': 'mou', 'name': '1. MOU', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #             {'code': 'biaya_registrasi', 'name': '2. Biaya Registrasi', 'status': 'waiting', 'color': 'secondary',
    #              'details': []},
    #             {'code': 'dp', 'name': '3. DP', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #             {'code': 'nie', 'name': '4. NIE', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #             {'code': 'pengadaan', 'name': '5. Pengadaan', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #             {'code': 'produksi', 'name': '6. Produksi', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #             {'code': 'qc', 'name': '7. QC', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #             {'code': 'bp', 'name': '8. BP', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #             {'code': 'delivery', 'name': '9. Delivery', 'status': 'waiting', 'color': 'secondary', 'details': []},
    #         ]
    #
    #         all_activities = []
    #
    #         all_activities.append({
    #             'date': fields.Date.to_date(mou.tgl_draft) if mou.tgl_draft else fields.Date.today(),
    #             'stage_code': 'mou',
    #             'label': 'MOU Disahkan',
    #             'is_done': True,
    #             'attachment_name': False
    #         })
    #
    #         setups = self.env['mou.setup'].search([('mou_id', '=', mou.id)])
    #         for setup in setups:
    #             all_activities.append({
    #                 'date': fields.Date.to_date(setup.date),
    #                 'stage_code': setup.state,
    #                 'label': setup.keterangan or f'Setup Transaksi: {setup.name}',
    #                 'is_done': True,
    #                 'attachment_name': False
    #             })
    #
    #         payments = self.env['account.payment'].search([('mou_id', '=', mou.id), ('state', '=', 'posted')])
    #         for pay in payments:
    #             all_activities.append({
    #                 'date': fields.Date.to_date(pay.date),
    #                 'stage_code': 'dp',
    #                 'label': f'Pembayaran: {pay.name} ({pay.amount})',
    #                 'is_done': True,
    #                 'attachment_name': False
    #             })
    #
    #         all_activities.sort(key=lambda x: x['date'] if x['date'] else fields.Datetime.now())
    #
    #         for act in all_activities:
    #             for stage in stages:
    #                 if stage['code'] == act['stage_code']:
    #                     date_str = act['date'].strftime('%d-%m-%Y') if act['date'] else '-'
    #                     stage['details'].append({
    #                         'label': act['label'],
    #                         'date': date_str,
    #                         'is_done': act['is_done'],
    #                         'attachment_name': act['attachment_name']
    #                     })
    #
    #         done_count = 0
    #         for i, stage in enumerate(stages):
    #             if len(stage['details']) > 0:
    #                 stage['status'] = 'done'
    #                 stage['color'] = 'success'
    #                 done_count += 1
    #             elif i == 0 or stages[i - 1]['status'] == 'done':
    #                 stage['status'] = 'process'
    #                 stage['color'] = 'primary'
    #             else:
    #                 stage['status'] = 'waiting'
    #                 stage['color'] = 'secondary'
    #
    #         progress_percent = int((done_count / len(stages)) * 100)
    #
    #         timeline_list.append({
    #             'id': mou.id,
    #             'pelanggan': mou.nama_cust or 'Unknown Customer',
    #             'no_mou': mou.draft_name,
    #             'progress': progress_percent,
    #             'deadline': '-',
    #             'stages': stages
    #         })
    #
    #     return timeline_list