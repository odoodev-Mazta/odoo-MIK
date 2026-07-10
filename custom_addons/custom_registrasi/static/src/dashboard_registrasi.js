/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class DashboardRegistrasi extends Component {
    static template = "custom_registrasi.DashboardRegistrasi";

    setup() {
        this.orm = useService("orm");

        this.chartNieRef   = useRef("chartNie");
        this.chartHalalRef = useRef("chartHalal");
        this.chartBrandRef = useRef("chartBrand");

        this.state = useState({
            loading: true,
            all_nie:   [],
            all_halal: [],
            all_brand: [],
            table_nie:   [],
            table_halal: [],
            table_brand: [],
            nie:   {},
            halal: {},
            brand: {},
            active_filter_nie:   'Semua Data',
            active_filter_halal: 'Semua Data',
            active_filter_brand: 'Semua Data',
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async fetchData() {
        const data = await this.orm.call(
            'registrasi.dashboard',
            'get_dashboard_data',
            []
        );
        this.state.nie   = data.nie;
        this.state.halal = data.halal;
        this.state.brand = data.brand;

        this.state.all_nie   = data.table_nie   || [];
        this.state.all_halal = data.table_halal || [];
        this.state.all_brand = data.table_brand || [];
        this.state.table_nie   = data.table_nie   || [];
        this.state.table_halal = data.table_halal || [];
        this.state.table_brand = data.table_brand || [];

        this.state.loading = false;
    }

    renderCharts() {
        this._renderDonut(
            this.chartNieRef.el,
            {
                labels: ['NIE Issued', 'Proses', 'Draft', 'Failed', 'Expired'],
                data: [
                    this.state.nie.issued,
                    this.state.nie.process,
                    this.state.nie.draft,
                    this.state.nie.failed,
                    this.state.nie.expired,
                ],
            },
            'state_label',
            'Status NIE'
        );

        this._renderDonut(
            this.chartHalalRef.el,
            {
                labels: ['Aktif', 'Proses', 'Hampir Exp', 'Expired', 'Ditolak'],
                data: [
                    this.state.halal.aktif,
                    this.state.halal.process,
                    this.state.halal.soon,
                    this.state.halal.expired,
                    this.state.halal.ditolak,
                ],
            },
            'state_label',
            'Status Halal'
        );

        this._renderDonut(
            this.chartBrandRef.el,
            {
                labels: ['Approved', 'Proses', 'Draft', 'Rejected'],
                data: [
                    this.state.brand.approved,
                    this.state.brand.process,
                    this.state.brand.draft,
                    this.state.brand.rejected,
                ],
            },
            'state_label',
            'Status Brand'
        );
    }

    _renderDonut(canvas, chartData, filterKey, title) {
        if (!canvas || !chartData.data) return;
        new window.Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: chartData.labels,
                datasets: [{
                    data: chartData.data,
                    backgroundColor: ['#198754','#0d6efd','#6c757d','#dc3545','#6f42c1'],
                    borderWidth: 2,
                    hoverOffset: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                onClick: (evt, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = chartData.labels[index];
                        this.filterData(filterKey, label, title);
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: title,
                        font: { size: 14 },
                    },
                    legend: { position: 'bottom' },
                },
            },
        });
    }

    filterData(filterKey, label, section) {
        if (section === 'Status NIE') {
            this.state.active_filter_nie = label;
            this.state.table_nie = this.state.all_nie.filter(r => r[filterKey] === label);
        } else if (section === 'Status Halal') {
            this.state.active_filter_halal = label;
            this.state.table_halal = this.state.all_halal.filter(r => r[filterKey] === label);
        } else if (section === 'Status Brand') {
            this.state.active_filter_brand = label;
            this.state.table_brand = this.state.all_brand.filter(r => r[filterKey] === label);
        }
    }

    resetFilter(section) {
        if (section === 'nie') {
            this.state.active_filter_nie = 'Semua Data';
            this.state.table_nie = this.state.all_nie;
        } else if (section === 'halal') {
            this.state.active_filter_halal = 'Semua Data';
            this.state.table_halal = this.state.all_halal;
        } else if (section === 'brand') {
            this.state.active_filter_brand = 'Semua Data';
            this.state.table_brand = this.state.all_brand;
        }
    }
}

registry.category("actions").add("dashboard_registrasi_action", DashboardRegistrasi);