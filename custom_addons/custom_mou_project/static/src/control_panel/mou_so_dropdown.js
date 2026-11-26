import { onWillStart, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ProjectTaskControlPanel } from "@project/views/project_task_control_panel/project_task_control_panel";

/**
 * Dropdown "Sales Order" di atas tampilan task Project MOU (seperti pemilih No. SO di Tracking MOU).
 * Hanya muncul untuk Project yang berasal dari MOU (konteks mou_so_mou_id). Memilih SO membuka ulang task
 * dengan chip "Per SO" untuk SO itu; "Semua SO" menampilkan semuanya.
 */
patch(ProjectTaskControlPanel.prototype, {
    setup() {
        super.setup();
        this.mouOrm = useService("orm");
        this.mouActionService = useService("action");
        this.mouSo = useState({ projectId: false, selected: 0, options: [] });
        onWillStart(async () => {
            const context = this.env.searchModel.globalContext || {};
            if (!context.mou_so_mou_id || !context.default_project_id) {
                return;
            }
            this.mouSo.projectId = context.default_project_id;
            this.mouSo.selected = context.search_default_mou_so_scope || 0;
            this.mouSo.options = await this.mouOrm.call("project.project", "get_mou_so_options", [
                [context.default_project_id],
            ]);
        });
    },

    async onChangeMouSo(ev) {
        const orderId = parseInt(ev.target.value) || 0;
        this.mouSo.selected = orderId;
        const action = await this.mouOrm.call("project.project", "action_view_tasks_for_so", [
            [this.mouSo.projectId],
            orderId,
        ]);
        await this.mouActionService.doAction(action, { clearBreadcrumbs: true });
    },
});
