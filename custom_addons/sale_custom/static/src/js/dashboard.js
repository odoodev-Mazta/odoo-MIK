/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onMounted, useRef, useState } = owl;

export class MaztaOrderDashboard extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        
        this.state = useState({
            quotations: [],
            orders: [],
            toInvoice: [],
            products: [],
            maztaOrders: [],
            loading: true
        });

        this.overviewBarRef = useRef("overviewBar");
        this.overviewPieRef = useRef("overviewPie");

        onMounted(() => {
            this.loadAllSubMenus();
        });
    }

    async loadAllSubMenus() {
        let quotations = [], orders = [], toInvoice = [], products = [], maztaOrders = [];

        try {
            quotations = await this.orm.searchRead("sale.order", [["state", "in", ["draft", "sent"]]], ["name", "partner_id", "user_id", "state", "amount_total"]);
        } catch (e) { console.warn("Quotations error:", e); }

        try {
            orders = await this.orm.searchRead("sale.order", [["state", "in", ["sale", "done"]]], ["name", "partner_id", "user_id", "state", "amount_total"]);
        } catch (e) { console.warn("Orders error:", e); }

        try {
            toInvoice = await this.orm.searchRead("account.move", [["move_type", "in", ["out_invoice", "out_refund"]]], ["name", "partner_id", "amount_total", "payment_state", "state"]);
        } catch (e) { console.warn("Invoices error:", e); }

        try {
            products = await this.orm.searchRead("product.product", [], ["name", "lst_price"]);
        } catch (e) { console.warn("Products error:", e); }

        try {
            maztaOrders = await this.orm.searchRead("mazta.order", [], ["name", "partner_id", "user_id", "state", "amount_total"]);
        } catch (e) { 
            try {
                maztaOrders = await this.orm.searchRead("sale.order", [["state", "!=", "cancel"]], ["name", "partner_id", "user_id", "state", "amount_total"]);
            } catch (err) { console.warn("Mazta orders error:", err); }
        }

        this.state.quotations = quotations;
        this.state.orders = orders;
        this.state.toInvoice = toInvoice;
        this.state.products = products;
        this.state.maztaOrders = maztaOrders;
        this.state.loading = false;

        setTimeout(() => {
            this.renderOverviewCharts(quotations, orders, toInvoice, products, maztaOrders);
        }, 300);
    }

    renderOverviewCharts(quotations, orders, toInvoice, products, maztaOrders) {
        if (typeof Chart === "undefined") return;

        const qRev = quotations.reduce((sum, q) => sum + (q.amount_total || 0), 0);
        const oRev = orders.reduce((sum, o) => sum + (o.amount_total || 0), 0);
        const iVal = toInvoice.reduce((sum, i) => sum + (i.amount_total || 0), 0);
        const mRev = maztaOrders.reduce((sum, m) => sum + (m.amount_total || 0), 0);

        const totalVolume = quotations.length + orders.length + toInvoice.length + products.length + maztaOrders.length;
        const dataCounts = [quotations.length, orders.length, toInvoice.length, products.length, maztaOrders.length];

        // Bar Chart (Akumulasi Nilai)
        if (this.overviewBarRef && this.overviewBarRef.el) {
            new Chart(this.overviewBarRef.el, {
                type: 'bar',
                data: {
                    labels: ['Quotations', 'Sales Orders', 'To Invoice', 'Products', 'Mazta Orders'],
                    datasets: [{
                        label: 'Akumulasi Nilai / Jumlah',
                        data: [qRev, oRev, iVal, products.length, mRev],
                        backgroundColor: ['#ffc107', '#0d6efd', '#fd7e14', '#17a2b8', '#6f42c1'],
                        borderRadius: 6
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        // Doughnut Chart dengan Label Persentase Permanen & Tooltip
        if (this.overviewPieRef && this.overviewPieRef.el) {
            new Chart(this.overviewPieRef.el, {
                type: 'doughnut',
                data: {
                    labels: ['Quotations', 'Orders', 'To Invoice', 'Products', 'Mazta Orders'],
                    datasets: [{
                        data: dataCounts,
                        backgroundColor: ['#ffc107', '#0d6efd', '#fd7e14', '#17a2b8', '#6f42c1'],
                        borderWidth: 2
                    }]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                generateLabels: function(chart) {
                                    const data = chart.data;
                                    if (data.labels.length && data.datasets.length) {
                                        return data.labels.map(function(label, i) {
                                            const value = data.datasets[0].data[i];
                                            const percentage = totalVolume > 0 ? ((value / totalVolume) * 100).toFixed(1) : 0;
                                            return {
                                                text: `${label}: ${value} (${percentage}%)`,
                                                fillStyle: data.datasets[0].backgroundColor[i],
                                                hidden: false,
                                                index: i
                                            };
                                        });
                                    }
                                    return [];
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const value = context.raw || 0;
                                    const percentage = totalVolume > 0 ? ((value / totalVolume) * 100).toFixed(1) : 0;
                                    return ` ${context.label}: ${value} item (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    }
}

MaztaOrderDashboard.template = "sale_custom.MaztaOrderDashboardTemplate";
registry.category("actions").add("mazta_order_dashboard_tag", MaztaOrderDashboard);