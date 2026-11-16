import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const WIZARD = "mrp.bom.import.wizard";

export class BomImportProgress extends Component {
    static template = "custom_bom.ImportProgress";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const params = this.props.action.params || {};
        this.wizardId = params.wizard_id;
        this.chunk = params.chunk || 15;
        this.state = useState({
            total: params.total || 0,
            processed: 0,
            created: 0,
            updated: 0,
            skipped: 0,
            newProducts: 0,
            error: "",
            finished: false,
        });
        onMounted(() => this.run());
    }

    get percent() {
        if (!this.state.total) {
            return this.state.finished ? 100 : 0;
        }
        return Math.min(100, Math.round((this.state.processed / this.state.total) * 100));
    }

    async run() {
        try {
            let start = 0;
            while (start < this.state.total) {
                const result = await this.orm.call(WIZARD, "import_chunk", [[this.wizardId], start, this.chunk]);
                this.state.processed += result.processed;
                this.state.created += result.created;
                this.state.updated += result.updated;
                this.state.skipped += result.skipped;
                this.state.newProducts += result.new_products;
                start += this.chunk;
                if (!result.processed) {
                    break;
                }
            }
            this.state.finished = true;
        } catch (error) {
            this.state.error =
                (error && error.data && error.data.message) || (error && error.message) || String(error);
        }
    }

    close() {
        this.action.doAction({ type: "ir.actions.client", tag: "reload" });
    }
}

registry.category("actions").add("custom_bom.import_progress", BomImportProgress);
