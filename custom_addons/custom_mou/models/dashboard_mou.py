from odoo import models, fields, api

class DashboardMou(models.AbstractModel):
    _name = 'dashboard.mou'
    _description = 'Dashboard for MOU'

    @api.model
    def get_dashboard_statistics(self):
        Mou = self.env['draft.maklon']
        MouSetup = self.env['mou.setup']

        # GET MOU DATA
        mou_records = Mou.search([])

        # Hanya MOU yang sudah confirmed
        confirmed_mous = mou_records.filtered(
            lambda mou: mou.state == 'mou'
        )

        # CHART 1
        # MOU (Signed) vs Draft
        mou_count = len(confirmed_mous)
        draft_count = len(
            mou_records.filtered(lambda mou: mou.state == 'draft')
        )

        chart_1 = {
            'labels': ['MOU (Signed)', 'Draft'],
            'data': [mou_count, draft_count],
        }

        # CHART 2
        # MOU vs CANCEL
        # Sementara Cancel = 0.
        cancel_count = 0

        chart_2 = {
            'labels': ['MOU', 'Cancel'],
            'data': [mou_count, cancel_count],
        }

        # CHART 3
        # SUDAH DP vs BELUM DP / PENDING
        dp_paid_count = 0
        dp_pending_count = 0

        # Cache setup supaya tidak search berulang kali
        setups = MouSetup.search([
            ('mou_id', 'in', confirmed_mous.ids),
            ('state', '=', 'dp'),
        ])

        # Group setup berdasarkan MOU
        setups_by_mou = {}

        for setup in setups:
            setups_by_mou.setdefault(
                setup.mou_id.id,
                []
            ).append(setup)

        for mou in confirmed_mous:
            mou_setups = setups_by_mou.get(mou.id, [])

            # Kalau ada setup DP yang sudah memiliki tanggal pembayaran
            is_dp_paid = any(
                setup.dp_payment_date
                for setup in mou_setups
            )

            if is_dp_paid:
                dp_paid_count += 1
            else:
                dp_pending_count += 1

        chart_3 = {
            'labels': [
                'Sudah DP',
                'Belum DP / Pending'
            ],
            'data': [
                dp_paid_count,
                dp_pending_count
            ],
        }

        # CHART 4
        # DUMMY UNTUK SEMENTARA
        chart_4 = {
            'labels': [
                'Aman (> 30 Hari)',
                'Mendesak (< 30 Hari)',
                'Overdue'
            ],
            'data': [60, 25, 10],
        }

        # TABLE DATA
        table_data = []

        # Cache semua setup yang diperlukan
        setup_by_mou = {}

        for setup in MouSetup.search([
            ('mou_id', 'in', mou_records.ids),
        ]):
            setup_by_mou.setdefault(
                setup.mou_id.id,
                []
            ).append(setup)

        for mou in mou_records:
            # STATUS CHART 1
            if mou.state == 'mou':
                status = 'MOU (Signed)'
            else:
                status = 'Draft'

            # STATUS CHART 2
            # Belum ada sumber Cancel
            cancel_status = 'MOU'

            # STATUS DP
            mou_setups = setup_by_mou.get(mou.id, [])

            is_dp_paid = any(
                setup.state == 'dp'
                and setup.dp_payment_date
                for setup in mou_setups
            )

            dp_status = (
                'Sudah DP'
                if is_dp_paid
                else 'Belum DP / Pending'
            )

            # DP AMOUNT
            dp_amount = sum(
                setup.dp_nilai or 0.0
                for setup in mou_setups
                if setup.state == 'dp'
            )

            # PRODUCT LINES
            if mou.maklon_line_ids:

                for line in mou.maklon_line_ids:
                    table_data.append({
                        'id': f'{mou.id}_{line.id}',

                        'tgl_draft': (
                            fields.Date.to_string(mou.tgl_draft)
                            if mou.tgl_draft
                            else '-'
                        ),

                        'tgl_mou': (
                            fields.Date.to_string(mou.tgl_start)
                            if mou.state == 'mou' and mou.tgl_start
                            else '-'
                        ),

                        'pelanggan': (
                            mou.nama_cust.name
                            if mou.nama_cust
                            else '-'
                        ),

                        'produk': (
                            line.product.display_name
                            if line.product
                            else '-'
                        ),

                        'qty': line.product_qty or 0,

                        # Sementara tetap dummy
                        'dp': '0%',
                        'bp': '100%',

                        'deadline_delivery': (
                            fields.Date.to_string(line.date_estimasi)
                            if line.date_estimasi
                            else '-'
                        ),

                        # Hidden/filter fields
                        'status': status,
                        'cancel_status': cancel_status,
                        'dp_status': dp_status,

                        # Chart 4 sementara dummy
                        'deadline_cat': 'Aman (> 30 Hari)',
                        'dp_amount': dp_amount,
                    })

            else:
                table_data.append({
                    'id': mou.id,

                    'tgl_draft': (
                        fields.Date.to_string(mou.tgl_draft)
                        if mou.tgl_draft
                        else '-'
                    ),

                    'tgl_mou': (
                        fields.Date.to_string(mou.tgl_start)
                        if mou.state == 'mou' and mou.tgl_start
                        else '-'
                    ),

                    'pelanggan': (
                        mou.nama_cust.name
                        if mou.nama_cust
                        else '-'
                    ),

                    'produk': '-',
                    'qty': 0,

                    'dp': '0%',
                    'bp': '100%',
                    'deadline_delivery': '-',

                    'status': status,
                    'cancel_status': cancel_status,
                    'dp_status': dp_status,
                    'deadline_cat': 'Aman (> 30 Hari)',

                    'dp_amount': dp_amount,
                })

        return {
            'stats': {
                'total_users': len(mou_records),
                'system_status': 'Active',
            },

            'chart_1': chart_1,
            'chart_2': chart_2,
            'chart_3': chart_3,
            'chart_4': chart_4,
            'table_data': table_data,
        }