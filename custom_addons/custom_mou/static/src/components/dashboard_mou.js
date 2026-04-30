/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class DashboardMou extends Component {
    setup() {
        this.orm = useService("orm");

        this.chart1Ref = useRef("chart1");
        this.chart2Ref = useRef("chart2");
        this.chart3Ref = useRef("chart3");
        this.chart4Ref = useRef("chart4");

        this.state = useState({
            stats: { total_users: 0, system_status: 'Loading...' },
            chart_1: {}, chart_2: {}, chart_3: {},
            all_data: [], // <--- MENYIMPAN SEMUA DATA (Master Data)
            table_data: [], // <--- DATA YANG DITAMPILKAN DI TABEL
            active_filter: "Semua Data" // <--- STATUS FILTER SAAT INI
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => {
            // Memanggil fungsi dengan tambahan argumen 'filterKey'
            this.renderDoughnutChart(this.chart1Ref.el, this.state.chart_1, "status", "MOU vs Draft");
            this.renderDoughnutChart(this.chart2Ref.el, this.state.chart_2, "cancel_status", "MOU vs Cancel");
            this.renderDoughnutChart(this.chart3Ref.el, this.state.chart_3, "dp_status", "MOU vs Down Payment");
            this.renderDoughnutChart(this.chart4Ref.el, this.state.chart_4, "deadline_cat", "Deadline");
        });
    }

    async fetchData() {
        const result = await this.orm.call(
            "dashboard.mou",
            "get_dashboard_statistics",
            []
        );
        if (result) {
            this.state.stats = result.stats;
            this.state.chart_1 = result.chart_1;
            this.state.chart_2 = result.chart_2;
            this.state.chart_3 = result.chart_3;
            this.state.chart_4 = result.chart_4;

            // Simpan data dari backend ke dua state yang berbeda
            this.state.all_data = result.table_data;
            this.state.table_data = result.table_data;
        }
    }

    // Fungsi untuk memfilter data berdasarkan klik di chart
    filterData(key, label) {
        this.state.active_filter = label;
        this.state.table_data = this.state.all_data.filter(item => {
            return item[key] === label;
        });
    }

    // Fungsi untuk mereset filter kembali ke awal
    resetFilter() {
        this.state.active_filter = "Semua Data";
        this.state.table_data = this.state.all_data;
    }

    // Tambahkan parameter 'filterKey'
    renderDoughnutChart(canvasElement, chartData, filterKey, title) {
        if (!canvasElement || !chartData.data) return;

        new window.Chart(canvasElement, {
            type: 'doughnut',
            data: {
                labels: chartData.labels,
                datasets: [{
                    data: chartData.data,
                    backgroundColor: [
                        '#1f77b4', '#ff7f0e', '#d62728', '#2ca02c', '#9467bd'
                    ],
                    borderWidth: 2,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                // Menangkap event klik pada chart
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = chartData.labels[index];
                        this.filterData(filterKey, label);
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: title,
                        font: { size: 16 }
                    },
                    legend: {
                        position: 'bottom',
                    }
                }
            }
        });
    }
}

DashboardMou.template = "custom_mou.MainTemplate";
registry.category("actions").add("custom_mou.main_action", DashboardMou);