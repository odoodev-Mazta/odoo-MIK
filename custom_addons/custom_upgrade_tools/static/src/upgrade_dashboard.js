import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "custom.upgrade.run";

const STATE_LABELS = {
    pending: "Menunggu",
    running: "Berjalan...",
    done: "Selesai",
    failed: "Gagal",
    skipped: "Ditunda",
};

const RUN_LABELS = {
    running: "Berjalan",
    done: "Selesai",
    failed: "Ada yang Gagal",
};

export class CustomUpgradeDashboard extends Component {
    static template = "custom_upgrade_tools.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.stateLabels = STATE_LABELS;
        this.runLabels = RUN_LABELS;
        this.state = useState({
            run: null,
            history: [],
            moduleCount: 0,
            processing: false,
            waitingSeconds: 0,
            openErrors: {},
        });
        this.stopped = false;

        onWillStart(() => this.load());
        onWillUnmount(() => {
            this.stopped = true;
        });
    }

    get percent() {
        const run = this.state.run;
        if (!run || !run.total) {
            return 0;
        }
        return Math.round(((run.done + run.failed + run.skipped) / run.total) * 100);
    }

    async load(runId = null) {
        const data = await this.orm.call(MODEL, "get_dashboard_data", [], { run_id: runId });
        this.state.run = data.run;
        this.state.history = data.history;
        this.state.moduleCount = data.module_count;
    }

    async start() {
        const runId = await this.orm.call(MODEL, "action_start", []);
        await this.load(runId);
        await this.processQueue();
    }

    async retryFailed() {
        await this.orm.call(MODEL, "action_retry_failed", [[this.state.run.id]]);
        await this.load(this.state.run.id);
        await this.processQueue();
    }

    async processQueue() {
        if (this.state.processing) {
            return;
        }
        this.state.processing = true;
        try {
            while (!this.stopped && this.state.run && this.state.run.state === "running") {
                // Tandai modul berikutnya di layar selama server mengupgrade.
                const next = this.state.run.lines.find((line) => ["pending", "running"].includes(line.state));
                if (next) {
                    next.state = "running";
                }
                const result = await this.orm.call(MODEL, "action_process_next", [[this.state.run.id]]);
                await this.load(this.state.run.id);
                if (result && result.wait) {
                    await this.countdown(result.wait);
                }
            }
        } catch (error) {
            this.notification.add(
                "Koneksi ke server terputus. Upgrade di server mungkin masih berjalan; buka ulang halaman ini lalu klik Lanjutkan.",
                { type: "danger", sticky: true }
            );
            throw error;
        } finally {
            this.state.processing = false;
            this.state.waitingSeconds = 0;
        }
        if (this.stopped || !this.state.run) {
            return;
        }
        if (this.state.run.state === "done") {
            this.notification.add("Semua modul custom berhasil diupgrade. Tekan Ctrl+Shift+R untuk memuat tampilan terbaru.", {
                type: "success",
                sticky: true,
            });
        } else if (this.state.run.state === "failed") {
            this.notification.add("Ada modul yang gagal. Lihat error-nya, perbaiki, lalu klik Coba Lagi yang Gagal.", {
                type: "warning",
                sticky: true,
            });
        }
    }

    async countdown(seconds) {
        for (let left = seconds; left > 0 && !this.stopped; left--) {
            this.state.waitingSeconds = left;
            await new Promise((resolve) => setTimeout(resolve, 1000));
        }
        this.state.waitingSeconds = 0;
    }

    toggleError(lineId) {
        this.state.openErrors[lineId] = !this.state.openErrors[lineId];
    }

    async openHistory(runId) {
        if (!this.state.processing) {
            await this.load(runId);
        }
    }

    badgeClass(state) {
        return {
            pending: "text-bg-light",
            running: "text-bg-primary",
            done: "text-bg-success",
            failed: "text-bg-danger",
            skipped: "text-bg-warning",
        }[state] || "text-bg-light";
    }
}

registry.category("actions").add("custom_upgrade_tools.dashboard", CustomUpgradeDashboard);
