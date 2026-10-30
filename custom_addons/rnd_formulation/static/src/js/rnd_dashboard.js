/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class RndFormulaDashboard extends Component {
    static template = "rnd_lab.RndDashboardTemplate";

    setup() {
        this.orm = useService("orm");
        this.statusChartRef = useRef("statusChart");
        this.statePieChartRef = useRef("statePieChart");

        // Simpan instance chart di sini
        this.statusChartInstance = null;
        this.statePieChartInstance = null;

        this.state = useState({
            loading: true,
            formulas: [],
            trials: [],
            passCount: 0,
            successRate: 0,
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadDashboardData();
        });

        onMounted(() => {
            if (!this.state.loading) {
                this.renderCharts();
            }
        });
    }

    async loadDashboardData() {
        const formulas = await this.orm.searchRead("rnd.formula", [], ["name", "state"]);
        const trials = await this.orm.searchRead(
            "rnd.formula.trial", 
            [], 
            ["trial_number", "formula_id", "target_qty", "total_qty", "result_status"],
            { limit: 10, order: "id desc" }
        );

        const passCount = trials.filter(t => t.result_status === 'pass').length;
        const successRate = trials.length > 0 ? ((passCount / trials.length) * 100).toFixed(1) : 0;

        this.state.formulas = formulas;
        this.state.trials = trials;
        this.state.passCount = passCount;
        this.state.successRate = successRate;
        this.state.loading = false;
        
        setTimeout(() => this.renderCharts(), 0);
    }

    renderCharts() {
        // 1. Render Bar Chart (Status Pengujian)
        if (this.statusChartRef.el) {
            // HANCURKAN CHART LAMA JIKA SUDAH ADA
            if (this.statusChartInstance) {
                this.statusChartInstance.destroy();
            }

            const pass = this.state.trials.filter(t => t.result_status === 'pass').length;
            const under = this.state.trials.filter(t => t.result_status === 'under').length;
            const over = this.state.trials.filter(t => t.result_status === 'over').length;

            this.statusChartInstance = new Chart(this.statusChartRef.el, {
                type: 'bar',
                data: {
                    labels: ['Belum Pas (Under)', 'Sesuai (Pass)', 'Kelebihan (Over)'],
                    datasets: [{
                        label: 'Jumlah Pengujian',
                        data: [under, pass, over],
                        backgroundColor: ['#ffc107', '#198754', '#dc3545']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        // 2. Render Pie Chart (Proporsi Formulasi)
        if (this.statePieChartRef.el) {
            // HANCURKAN CHART LAMA JIKA SUDAH ADA
            if (this.statePieChartInstance) {
                this.statePieChartInstance.destroy();
            }

            const draft = this.state.formulas.filter(f => f.state === 'draft').length;
            const inProgress = this.state.formulas.filter(f => f.state === 'in_progress').length;
            const done = this.state.formulas.filter(f => f.state === 'done').length;

            this.statePieChartInstance = new Chart(this.statePieChartRef.el, {
                type: 'pie',
                data: {
                    labels: ['Draft', 'Dalam Pengujian', 'Selesai (PAS)'],
                    datasets: [{
                        data: [draft, inProgress, done],
                        backgroundColor: ['#6c757d', '#0d6efd', '#198754']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }
}

registry.category("actions").add("rnd_formula_dashboard_tag", RndFormulaDashboard);