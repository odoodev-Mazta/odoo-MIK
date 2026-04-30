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
            active_stage_index: 0 // Menyimpan urutan tahapan yang sedang diklik (0-8)
        });

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        const result = await this.orm.call("dashboard.timeline.mou", "get_timeline_data", []);
        if (result && result.length > 0) {
            this.state.all_mou = result;
            this.state.selected_mou = result[0];
            this.autoSelectActiveStage();
        }
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

    // Otomatis memilih tahapan yang sedang "Process", jika tidak ada pilih tahapan 0
    autoSelectActiveStage() {
        if (this.state.selected_mou) {
            const processIndex = this.state.selected_mou.stages.findIndex(s => s.status === 'process');
            this.state.active_stage_index = processIndex !== -1 ? processIndex : 0;
        }
    }
}

TimelineDashboard.template = "custom_mou.TimelineTemplate";
registry.category("actions").add("custom_timeline.main_action", TimelineDashboard);