import {
    Component,
    useState,
    useRef,
    onMounted,
    onWillStart,
    onWillUnmount,
    onWillUpdateProps,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

/* =========================================================
   CHILD COMPONENT: single Chart.js doughnut
   ========================================================= */

class ProductionDonutChart extends Component {
    static template = "custom_production_planning.ProductionDonutChart";
    static props = {
        title: String,
        total: Number,
        segments: Array,
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onMounted(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            this.renderChart(this.props);
        });

        onWillUpdateProps((nextProps) => {
            this.updateChart(nextProps);
        });

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    getChartData(props) {
        const hasData = props.total > 0;

        return {
            labels: hasData ? props.segments.map((s) => s.label) : ["No data"],
            datasets: [
                {
                    data: hasData ? props.segments.map((s) => s.count) : [1],
                    backgroundColor: hasData
                        ? props.segments.map((s) => s.color)
                        : ["#e5e7eb"],
                    borderWidth: 2,
                    borderColor: "#ffffff",
                    hoverOffset: hasData ? 4 : 0,
                },
            ],
        };
    }

    getChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "70%",
            animation: { duration: 300 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: this.props.total > 0,
                    callbacks: {
                        label: (context) => {
                            const value = context.parsed;
                            const total = context.dataset.data.reduce(
                                (a, b) => a + b,
                                0
                            );
                            const pct = total
                                ? Math.round((value / total) * 100)
                                : 0;
                            return ` ${context.label}: ${value} (${pct}%)`;
                        },
                    },
                },
            },
        };
    }

    renderChart(props) {
        if (!this.canvasRef.el) {
            return;
        }
        const ctx = this.canvasRef.el.getContext("2d");
        this.chart = new Chart(ctx, {
            type: "doughnut",
            data: this.getChartData(props),
            options: this.getChartOptions(),
        });
    }

    updateChart(props) {
        if (!this.chart) {
            return;
        }
        const data = this.getChartData(props);
        this.chart.data.labels = data.labels;
        this.chart.data.datasets = data.datasets;
        this.chart.update();
    }
}

/* =========================================================
   PARENT COMPONENT: dashboard
   ========================================================= */

const DONUT_COLORS = [
    "#2563eb",
    "#f59e0b",
    "#16a34a",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#db2777",
    "#65a30d",
];

const STATE_LABELS = {
    running: "Running",
    planned: "Planned",
    done: "Done",
    cancel: "Cancelled",
};

// Config for every donut chart shown at the top of the dashboard.
// Add/remove entries here to control how many donuts are rendered.
const DONUT_CONFIGS = [
    {
        title: "MO Status",
        field: "state",
        order: ["running", "planned", "done", "cancel"],
        labels: STATE_LABELS,
    },
    {
        title: "Work Order Status",
        field: "workorder_status",
        order: null,
        labels: {},
    },
];

export class ProductionDashboard extends Component {
    static template = "custom_production_planning.ProductionDashboard";
    static components = { ProductionDonutChart };

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            data: [],
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.data = await this.orm.searchRead(
            "mrp.production.dashboard",
            [],
            [
                "mo_name",
                "product_id",
                "customer_id",
                "current_workorder",
                "next_workorder",
                "workorder_progress",
                "workorder_status",
                "state",
                "planned_start",
                "planned_end",
            ]
        );
    }

    formatLabel(config, key) {
        if (config.labels[key]) {
            return config.labels[key];
        }
        if (!key) {
            return "Unknown";
        }
        return key.charAt(0).toUpperCase() + key.slice(1);
    }

    buildDonut(config) {
        const counts = {};
        for (const record of this.state.data) {
            const key = record[config.field] || "unknown";
            counts[key] = (counts[key] || 0) + 1;
        }

        let keys = config.order
            ? config.order.filter((k) => counts[k] !== undefined)
            : Object.keys(counts);

        for (const k of Object.keys(counts)) {
            if (!keys.includes(k)) {
                keys.push(k);
            }
        }

        const total = this.state.data.length;

        const segments = keys.map((key, index) => {
            const count = counts[key];
            const percentage = total ? Math.round((count / total) * 100) : 0;

            return {
                key,
                label: this.formatLabel(config, key),
                count,
                percentage,
                color: DONUT_COLORS[index % DONUT_COLORS.length],
            };
        });

        return {
            title: config.title,
            total,
            segments,
        };
    }

    get donutCards() {
        return DONUT_CONFIGS.map((config) => this.buildDonut(config));
    }

    refresh() {
        return this.loadDashboard();
    }
}

registry
    .category("actions")
    .add("production_dashboard", ProductionDashboard);