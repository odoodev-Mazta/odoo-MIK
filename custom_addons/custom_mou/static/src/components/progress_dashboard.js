/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class ProgressDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.barChartRef = useRef("barChart");
        this.gaugeChartRef = useRef("gaugeChart");
        this.gaugeInstance = null;

        this.state = useState({
            bar_chart_data: {},
            mou_list: [], // Detail data untuk tracker
            all_master_data: [], // Backup seluruh data tabel bawah
            display_master_table: [], // Data yang benar-benar muncul di tabel bawah
            selected_mou: null,
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => {
            this.renderHorizontalBarChart();
            if (this.state.selected_mou) {
                this.renderGaugeChart();
            }
        });
    }

    async fetchData() {
        const result = await this.orm.call("dashboard.progress.mou", "get_progress_data", []);
        if (result) {
            this.state.bar_chart_data = result.bar_chart;
            this.state.mou_list = result.mou_list;
            this.state.all_master_data = result.master_table;
            this.state.display_master_table = result.master_table; // Awalnya tampil semua

            if (result.mou_list.length > 0) {
                this.state.selected_mou = result.mou_list[0];
            }
        }
    }

    // INTERAKSI 1: Dropdown Kanan diubah -> Tabel Bawah terfilter
    onChangeSelection(ev) {
        const selectedId = parseInt(ev.target.value);
        this.state.selected_mou = this.state.mou_list.find(m => m.id === selectedId);

        // Filter tabel bawah agar hanya menampilkan baris pelanggan yang dipilih
        this.state.display_master_table = this.state.all_master_data.filter(
            item => item.id === selectedId
        );

        this.updateGaugeChart();
    }

    // INTERAKSI 2: Tabel Bawah diklik -> Detail Kanan berubah
    selectMouFromTable(mouId) {
        this.state.selected_mou = this.state.mou_list.find(m => m.id === mouId);
        this.updateGaugeChart();
    }

    // FUNGSI TAMBAHAN: Untuk menampilkan kembali semua data di tabel bawah
    resetTable() {
        this.state.display_master_table = this.state.all_master_data;
    }

    // --- Logika Chart tetap sama ---
    renderHorizontalBarChart() {
        if (!this.barChartRef.el) return;
        const inlineDataLabels = {
            id: 'inlineDataLabels',
            afterDatasetsDraw(chart) {
                const { ctx } = chart;
                chart.data.datasets.forEach((dataset, i) => {
                    chart.getDatasetMeta(i).data.forEach((datapoint, index) => {
                        const value = dataset.data[index];
                        if (value > 0) {
                            ctx.font = 'bold 12px sans-serif';
                            ctx.fillStyle = 'black';
                            ctx.textAlign = 'center';
                            const centerX = datapoint.base + ((datapoint.x - datapoint.base) / 2);
                            ctx.fillText(value, centerX, datapoint.y);
                        }
                    });
                });
            }
        };

        new window.Chart(this.barChartRef.el, {
            type: 'bar',
            data: {
                labels: this.state.bar_chart_data.labels,
                datasets: [
                    { label: 'Done', data: this.state.bar_chart_data.done, backgroundColor: '#04BADE' },
                    { label: 'Not Yet / Proses', data: this.state.bar_chart_data.not_yet, backgroundColor: '#FFE135' }
                ]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: { x: { stacked: true }, y: { stacked: true } }
            },
            plugins: [inlineDataLabels]
        });
    }

    renderGaugeChart() {
        if (!this.gaugeChartRef.el) return;
        const progress = this.state.selected_mou.progress || 0;
        this.gaugeInstance = new window.Chart(this.gaugeChartRef.el, {
            type: 'doughnut',
            data: {
                labels: ['Progress', 'Sisa'],
                datasets: [{
                    data: [progress, 100 - progress],
                    backgroundColor: ['#1f77b4', '#e9ecef'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                circumference: 180,
                rotation: 270,
                cutout: '75%',
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: `Progress: ${progress}%`, position: 'bottom' }
                }
            }
        });
    }

    updateGaugeChart() {
        if (this.gaugeInstance && this.state.selected_mou) {
            // Pelindung error: Jika progress tidak ada, otomatis jadi 0
            const progress = this.state.selected_mou.progress || 0;

            this.gaugeInstance.data.datasets[0].data = [progress, 100 - progress];
            this.gaugeInstance.options.plugins.title.text = `Progress: ${progress}%`;
            this.gaugeInstance.update();
        }
    }
}

ProgressDashboard.template = "custom_mou.ProgressTemplate";
registry.category("actions").add("custom_progress_mou.main_action", ProgressDashboard);