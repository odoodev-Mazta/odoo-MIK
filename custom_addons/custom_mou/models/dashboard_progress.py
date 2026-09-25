from odoo import models, fields, api

class DashboardProgress(models.AbstractModel):
    _name = 'dashboard.progress.mou'
    _description = 'Dashboard Progress MOU'

    # ============================================================
    # HELPER STATUS
    # ============================================================

    def _get_stage_status(self, timeline):
        """
        Mengambil status setiap tahapan MOU berdasarkan data
        yang sudah dikumpulkan oleh dashboard.timeline.mou.

        Return:
            Done
            Process
            Not Yet
        """

        container = timeline.get('container') or {}
        registrasi = timeline.get('registrasi') or {}
        pr_data = timeline.get('pr_data') or []
        production_data = timeline.get('production_data') or []
        delivery_data = timeline.get('delivery_data') or []

        # ========================================================
        # 1. BIAYA REGISTRASI
        # ========================================================

        reg_payment = container.get('reg_actual_date')

        if reg_payment:
            reg_status = 'Done'
        elif container.get('reg_due_date'):
            reg_status = 'Process'
        else:
            reg_status = 'Not Yet'

        # ========================================================
        # 2. DP
        # ========================================================

        dp_payment = container.get('dp_actual_date')

        if dp_payment:
            dp_status = 'Done'
        elif container.get('dp_due_date'):
            dp_status = 'Process'
        else:
            dp_status = 'Not Yet'

        # ========================================================
        # 3. NIE
        # ========================================================

        nie_data = registrasi.get('nie', [])

        if nie_data:
            total_nie = len(nie_data)
            done_nie = sum(
                1 for nie in nie_data
                if nie.get('is_done')
            )

            if done_nie == total_nie:
                nie_status = 'Done'
            elif done_nie > 0:
                nie_status = 'Process'
            else:
                nie_status = 'Process'
        else:
            # fallback menggunakan container
            nie_count = container.get('nie_count', 0)
            nie_done = container.get('nie_done', 0)

            if nie_count and nie_done >= nie_count:
                nie_status = 'Done'
            elif nie_count:
                nie_status = 'Process'
            else:
                nie_status = 'Not Yet'

        # ========================================================
        # 4. BAHAN BAKU
        # ========================================================

        bahan_status = self._get_procurement_status(
            pr_data,
            jenis='bahan'
        )

        # ========================================================
        # 5. KEMASAN
        # ========================================================

        kemasan_status = self._get_procurement_status(
            pr_data,
            jenis='kemasan'
        )

        # ========================================================
        # 6. PRODUKSI
        # ========================================================

        if production_data:
            total_production = len(production_data)

            done_production = sum(
                1 for production in production_data
                if production.get('is_done')
            )

            if done_production == total_production:
                production_status = 'Done'
            elif done_production > 0:
                production_status = 'Process'
            else:
                production_status = 'Process'
        else:
            production_status = 'Not Yet'

        # ========================================================
        # 7. DELIVERY
        # ========================================================

        if delivery_data:
            pickings = delivery_data.get('picking', [])

            if pickings:
                total_delivery = len(pickings)

                done_delivery = sum(
                    1 for picking in pickings
                    if picking.get('is_done')
                )

                if done_delivery == total_delivery:
                    delivery_status = 'Done'
                elif done_delivery > 0:
                    delivery_status = 'Process'
                else:
                    delivery_status = 'Process'
            else:
                delivery_status = 'Not Yet'
        else:
            delivery_status = 'Not Yet'

        return {
            'reg': reg_status,
            'dp': dp_status,
            'nie': nie_status,
            'bahan': bahan_status,
            'kemasan': kemasan_status,
            'produksi': production_status,
            'delivery': delivery_status,
        }

    # ============================================================
    # PROCUREMENT STATUS
    # ============================================================

    def _get_procurement_status(self, pr_data, jenis=None):
        """
        Menentukan status procurement.

        Saat ini menggunakan data PR/PO/Receipt yang sudah
        dikumpulkan oleh dashboard.timeline.mou.

        jenis:
            bahan
            kemasan
        """

        if not pr_data:
            return 'Not Yet'

        # --------------------------------------------------------
        # Untuk sementara seluruh PR dianggap procurement.
        #
        # Nanti ketika field klasifikasi Bahan Baku/Kemasan
        # sudah tersedia, filter bisa diperketat di sini.
        # --------------------------------------------------------

        relevant_pr = pr_data

        if not relevant_pr:
            return 'Not Yet'

        # Sudah diterima
        delivered = any(
            pr.get('delivered')
            for pr in relevant_pr
        )

        if delivered:
            return 'Done'

        # Sudah ada PR / PO → Process
        has_process = any(
            pr.get('pr_is_done')
            or pr.get('po_id')
            for pr in relevant_pr
        )

        if has_process:
            return 'Process'

        return 'Not Yet'

    # ============================================================
    # PROGRESS
    # ============================================================

    def _calculate_progress(self, statuses):
        """
        Progress berdasarkan jumlah tahapan yang Done.

        7 tahapan:
        Registrasi
        DP
        NIE
        Bahan Baku
        Kemasan
        Produksi
        Delivery
        """

        stages = [
            'reg',
            'dp',
            'nie',
            'bahan',
            'kemasan',
            'produksi',
            'delivery',
        ]

        done_count = sum(
            1 for stage in stages
            if statuses.get(stage) == 'Done'
        )

        return round((done_count / len(stages)) * 100)

    # ============================================================
    # MAIN METHOD
    # ============================================================

    @api.model
    def get_progress_data(self):

        stages = [
            'Biaya Register',
            'DP',
            'NIE',
            'Bahan Baku',
            'Kemasan',
            'Produksi',
            'Delivery',
        ]

        # ========================================================
        # AMBIL DATA DARI DASHBOARD TIMELINE
        # ========================================================

        timeline_data = self.env[
            'dashboard.timeline.mou'
        ].get_timeline_data()

        mou_list = []
        master_table_data = []

        # ========================================================
        # PROSES SETIAP MOU
        # ========================================================

        for timeline in timeline_data:

            statuses = self._get_stage_status(timeline)

            progress = self._calculate_progress(statuses)

            mou_id = timeline.get('id')

            pelanggan = timeline.get(
                'pelanggan',
                'Unknown Customer'
            )

            no_mou = timeline.get(
                'no_mou',
                '-'
            )

            # ====================================================
            # DETAIL STAGES
            # ====================================================

            container = timeline.get('container') or {}
            registrasi = timeline.get('registrasi') or {}

            nie_data = registrasi.get('nie', [])

            # ----------------------------------------------------
            # Deadline
            # ----------------------------------------------------

            deadlines = {
                'Biaya Register':
                    container.get('reg_due_date'),

                'DP':
                    container.get('dp_due_date'),

                'NIE':
                    container.get('nie_due_date'),

                'Bahan Baku':
                    None,

                'Kemasan':
                    None,

                'Produksi':
                    None,

                'Delivery':
                    None,
            }

            stage_data = []

            for stage_name, stage_key in [
                ('Biaya Register', 'reg'),
                ('DP', 'dp'),
                ('NIE', 'nie'),
                ('Bahan Baku', 'bahan'),
                ('Kemasan', 'kemasan'),
                ('Produksi', 'produksi'),
                ('Delivery', 'delivery'),
            ]:

                status = statuses[stage_key]

                stage_data.append({
                    'tahapan': stage_name,
                    'deadline': deadlines.get(stage_name) or '-',

                    'is_dana_masuk': (
                        status == 'Done'
                        and stage_name in (
                            'Biaya Register',
                            'DP',
                            'NIE',
                        )
                    ),

                    'tgl_dana': (
                        container.get('reg_actual_date')
                        if stage_name == 'Biaya Register'
                        else container.get('dp_actual_date')
                        if stage_name == 'DP'
                        else container.get('nie_actual_date')
                        if stage_name == 'NIE'
                        else '-'
                    ),

                    'is_start': status != 'Not Yet',

                    'tgl_start': '-',

                    'is_done': status == 'Done',

                    'tgl_done': (
                        container.get('reg_actual_date')
                        if stage_name == 'Biaya Register'
                        else container.get('dp_actual_date')
                        if stage_name == 'DP'
                        else container.get('nie_actual_date')
                        if stage_name == 'NIE'
                        else '-'
                    ),

                    'overdue': (
                        'Ontime'
                        if status == 'Done'
                        else '-'
                    ),
                })

            # ====================================================
            # MOU LIST
            # ====================================================

            mou_list.append({
                'id': mou_id,
                'no_mou': no_mou,
                'pelanggan': pelanggan,

                # Ambil brand dari draft.maklon tidak tersedia
                # langsung di timeline sekarang.
                # Nanti kita bisa tambahkan.
                'brand': timeline.get('brand', '-'),

                'progress': progress,

                'stages': stage_data,

                # optional untuk debugging / future
                'statuses': statuses,
            })

            # ====================================================
            # MASTER TABLE
            # ====================================================

            master_table_data.append({
                'id': mou_id,
                'pelanggan': pelanggan,

                'reg': statuses['reg'],
                'dp': statuses['dp'],
                'nie': statuses['nie'],
                'bahan': statuses['bahan'],
                'kemasan': statuses['kemasan'],
                'produksi': statuses['produksi'],
                'delivery': statuses['delivery'],
            })

        # ========================================================
        # BAR CHART
        # ========================================================

        done_data = []
        not_yet_data = []

        status_keys = [
            'reg',
            'dp',
            'nie',
            'bahan',
            'kemasan',
            'produksi',
            'delivery',
        ]

        for stage_key in status_keys:

            done_count = sum(
                1
                for row in master_table_data
                if row.get(stage_key) == 'Done'
            )

            not_yet_count = sum(
                1
                for row in master_table_data
                if row.get(stage_key) != 'Done'
            )

            done_data.append(done_count)
            not_yet_data.append(not_yet_count)

        bar_chart_data = {
            'labels': stages,
            'done': done_data,
            'not_yet': not_yet_data,
        }

        return {
            'bar_chart': bar_chart_data,
            'mou_list': mou_list,
            'master_table': master_table_data,
        }