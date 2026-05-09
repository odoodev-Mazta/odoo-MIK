/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class NIEReportingDashboard extends Component {
    setup() {
        // useService("orm") adalah cara baru untuk memanggil method Python (menggantikan rpc)
        this.orm = useService("orm");

        // useState membuat komponen otomatis render ulang jika data berubah
        this.state = useState({
            progress: { start_reg: 0, revisi: 0, ditolak: 0, teregist: 0 },
            table_data: []
        });

        // Dipanggil sebelum template di-render
        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        // Memanggil method 'get_dashboard_data' dari model 'nie.registrasi'
        const result = await this.orm.call(
            "nie.registrasi",
            "get_dashboard_data",
            []
        );
        // Masukkan hasil dari Python ke dalam state
        Object.assign(this.state, result);
    }
}

NIEReportingDashboard.template = "modul_nie.ReportingDashboardTemplate";
registry.category("actions").add("nie_module.action_nie_dashboard_reporting", NIEReportingDashboard);