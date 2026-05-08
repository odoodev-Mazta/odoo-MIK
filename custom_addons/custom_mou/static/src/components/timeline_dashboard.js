/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TimelineDashboard extends Component {
    setup() {
        this.orm = useService("orm");

        this.state = useState({
            all_mou: [],
            selected_mou: null,
            active_stage_index: 0
        });

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        const result = await this.orm.call("dashboard.timeline.mou", "get_timeline_data", []);
        if (result && result.length > 0) {
            this.state.all_mou = this.buildTimelineData(result);
            this.state.selected_mou = this.state.all_mou[0];
            this.autoSelectActiveStage();
        }
    }

    buildTimelineData(rawData) {
        return rawData.map(mou => {
            // Definisikan struktur tahapan awal
            let stages = [
                { code: 'mou', name: '1. MOU', status: 'waiting', color: 'secondary', details: [] },
                { code: 'biaya_registrasi', name: '2. Biaya Registrasi', status: 'waiting', color: 'secondary', details: [] },
                { code: 'dp', name: '3. DP', status: 'waiting', color: 'secondary', details: [] },
                { code: 'nie', name: '4. NIE', status: 'waiting', color: 'secondary', details: [] },
                { code: 'pengadaan', name: '5. Pengadaan', status: 'waiting', color: 'secondary', details: [] },
                { code: 'produksi', name: '6. Produksi', status: 'waiting', color: 'secondary', details: [] },
                { code: 'qc', name: '7. QC', status: 'waiting', color: 'secondary', details: [] },
                { code: 'bp', name: '8. BP', status: 'waiting', color: 'secondary', details: [] },
                { code: 'delivery', name: '9. Delivery', status: 'waiting', color: 'secondary', details: [] },
            ];

            // Masukkan data awal MOU
            stages.find(s => s.code === 'mou').details.push({
                label: 'MOU Disahkan',
                date: this.formatDate(mou.tgl_draft),
                is_done: true
            });

            // Ekstrak data dari Setup Transaksi untuk tahapan 2 sampai 5
            mou.setups.forEach(setup => {
                const isFree = setup.is_free;

                // Fungsi bantu untuk memformat detail
                const addSetupDetail = (stageCode, labelPrefix, dueDate, payDate, value) => {
                    let stage = stages.find(s => s.code === stageCode);
                    if (stage) {
                        let desc = isFree ? "Biaya: Free" : `Biaya: ${this.formatCurrency(value)}`;
                        stage.details.push({
                            label: `${labelPrefix} (${setup.name}) - ${desc}`,
                            date: payDate ? `Lunas: ${this.formatDate(payDate)}` : `Jatuh Tempo: ${this.formatDate(dueDate)}`,
                            is_done: !!payDate || isFree // Jika lunas atau free, dianggap selesai
                        });
                    }
                };

                // Lempar detail sesuai stage setup saat ini
                // Karena setup memiliki "state" (posisi tahapan saat ini),
                // kita bisa menggunakannya sebagai acuan sampai mana progress berjalan.

                if (setup.reg_due_date || setup.reg_payment_date || setup.state === 'biaya_registrasi') {
                    addSetupDetail('biaya_registrasi', 'Tagihan Registrasi', setup.reg_due_date, setup.reg_payment_date, setup.reg_nilai);
                }

                if (setup.dp_due_date || setup.dp_payment_date || setup.state === 'dp') {
                    addSetupDetail('dp', 'Tagihan DP', setup.dp_due_date, setup.dp_payment_date, setup.dp_nilai);
                }

                if (setup.nie_due_date || setup.nie_payment_date || setup.state === 'nie') {
                    addSetupDetail('nie', 'Tagihan NIE', setup.nie_due_date, setup.nie_payment_date, setup.nie_nilai);
                }

                if (setup.peng_due_date || setup.peng_payment_date || setup.state === 'pengadaan') {
                    addSetupDetail('pengadaan', 'Tagihan Pengadaan', setup.peng_due_date, setup.peng_payment_date, setup.peng_nilai);
                }
            });

            // Hitung Status (Done/Process/Waiting)
            let doneCount = 0;
            stages.forEach((stage, i) => {
                if (stage.details.length > 0) {
                    stage.status = 'done';
                    stage.color = 'success';
                    doneCount++;
                } else if (i === 0 || stages[i - 1].status === 'done') {
                    stage.status = 'process';
                    stage.color = 'primary';
                } else {
                    stage.status = 'waiting';
                    stage.color = 'secondary';
                }
            });

            const progressPercent = Math.round((doneCount / stages.length) * 100);

            return {
                id: mou.id,
                pelanggan: mou.pelanggan,
                no_mou: mou.no_mou,
                progress: progressPercent,
                stages: stages
            };
        });
    }

    formatDate(dateString) {
        if (!dateString) return '-';
        const [year, month, day] = dateString.split('-');
        return `${day}-${month}-${year}`;
    }

    formatCurrency(value) {
        if (!value) return 'Rp 0';
        return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(value);
    }

    onChangeSelection(ev) {
        const selectedId = parseInt(ev.target.value);
        this.state.selected_mou = this.state.all_mou.find(m => m.id === selectedId);
        this.autoSelectActiveStage();
    }

    // Fungsi klik titik stepper
    selectStage(index) {
        this.state.active_stage_index = index;
    }

    autoSelectActiveStage() {
        if (this.state.selected_mou) {
            const processIndex = this.state.selected_mou.stages.findIndex(s => s.status === 'process');
            this.state.active_stage_index = processIndex !== -1 ? processIndex : 0;
        }
    }
}

TimelineDashboard.template = "custom_mou.TimelineTemplate";
registry.category("actions").add("custom_timeline.main_action", TimelineDashboard);