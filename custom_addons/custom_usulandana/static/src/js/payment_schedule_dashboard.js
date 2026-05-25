/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class PaymentScheduleDashboard extends Component {

    setup() {

        this.orm = useService("orm");
        this.action = useService("action");

        this.months = [
            { number: 1, name: "Jan" },
            { number: 2, name: "Feb" },
            { number: 3, name: "Mar" },
            { number: 4, name: "Apr" },
            { number: 5, name: "Mei" },
            { number: 6, name: "Jun" },
            { number: 7, name: "Jul" },
            { number: 8, name: "Agu" },
            { number: 9, name: "Sep" },
            { number: 10, name: "Okt" },
            { number: 11, name: "Nov" },
            { number: 12, name: "Des" },
        ];

        this.state = useState({
            year: new Date().getFullYear(),
            month: new Date().getMonth() + 1,
            data: {},
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async openSchedulePopup(fullDate) {
        if (!fullDate) return;

        const action = await this.orm.call(
            "usulan.payment.schedule",
            "action_open_calendar_popup",
            [fullDate]
        );

        if (action) {
            await this.action.doAction(action);
        }
    }

    async loadData() {
        this.state.data = await this.orm.call(
            "usulan.payment.schedule",
            "get_schedule_dashboard",
            [this.state.year, this.state.month]
        );
    }

    async selectMonth(month) {
        this.state.month = month;
        await this.loadData();
    }
}

PaymentScheduleDashboard.template =
    "custom_usulandana.PaymentScheduleDashboard";

registry.category("actions").add(
    "payment_schedule_dashboard",
    PaymentScheduleDashboard
);