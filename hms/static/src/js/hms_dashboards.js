import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { markup } from "@odoo/owl";

class HmsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.caseChartRef = useRef("caseChart");
        this.trendChartRef = useRef("trendChart");

        this.state = useState({
            kpi_data: {
                quick_actions: [],
                recent_patients: [],
            },
            chart_data: {},
        });

        onWillStart(async () => {
            // Fetch role-specific dashboard data
            const kpiData = await this.orm.call("hms.dashboard", "get_dashboard_data", []);
            this.state.kpi_data = kpiData;

            const chartData = await this.orm.call("hms.dashboard", "get_chart_data", []);
            this.state.chart_data = chartData;
        });

        onMounted(() => {
            this._renderCharts();
        });
    }

    _renderCharts() {
        const Chart = window.Chart;
        if (!Chart) return;

        // --- Case distribution ---
        // Case chart
if (this.caseChartRef.el && this.state.chart_data.case_labels?.length) {
    new Chart(this.caseChartRef.el, {
        type: "doughnut",
        data: {
            labels: this.state.chart_data.case_labels,
            datasets: [{
                data: this.state.chart_data.case_values,
                backgroundColor: [
                    '#22B8C7',
                    '#189AA7',
                    '#6F42C1',
                    '#5B36A3',
                    '#FFC107', // optional extra colors
                    '#DC3545'
                ]
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

// Trend chart
if (this.trendChartRef.el && this.state.chart_data.trend_labels?.length) {
    new Chart(this.trendChartRef.el, {
        type: "line",
        data: {
            labels: this.state.chart_data.trend_labels,
            datasets: [{
                label: this.state.chart_data.trend_title || 'Trend',
                data: this.state.chart_data.trend_values,
                borderColor: '#22B8C7',
                backgroundColor: 'rgba(34,184,199,0.1)', 
                fill: true,
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}
    }

    openAction(action_xml_id) {
        if (!action_xml_id) return;
        this.action.doAction(action_xml_id);
    }

    // Open case form by ID (doctor/nurse)
    async openCaseForm(caseId) {
        if (!caseId) return;
        const action = await this.orm.call('hms.dashboard', 'get_form_action', ['hms.case', caseId]);
        if (action && action.res_id) {
            await this.action.doAction(action);
        }
    }

    async openAppointmentForm(appointmentId) {
        if (!appointmentId) return;
        const action = await this.orm.call('hms.dashboard', 'get_form_action', ['hms.appointment', appointmentId]);
        if (action && action.res_id) {
            await this.action.doAction(action);
        }
    }

    async openPatientForm(patientId) {
        if (!patientId) return;
        const action = await this.orm.call('hms.dashboard', 'get_form_action', ['res.partner', patientId]);
        if (action && action.res_id) {
            await this.action.doAction(action);
        }
    }
    
    openForm = async (model, resId) => {
            if (!model || !resId) return;
            const action = await this.orm.call('hms.dashboard', 'get_form_action', [model, resId]);
            if (action && action.res_id) {
                await this.action.doAction(action);
            }
        }
    htmlToText(html) {
    const el = document.createElement("div");
    el.innerHTML = html || "";
    return el.textContent || el.innerText || "";
}
}



HmsDashboard.template = "hms.Dashboards";
registry.category("actions").add("hms.hms_dashboards_action", HmsDashboard);


