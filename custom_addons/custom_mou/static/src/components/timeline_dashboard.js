import { Component, useState, onWillStart, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class TimelineDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this._donutInstances = {};

        this.state = useState({
            all_mou: [],
            selected_mou: null,
            selected_so_id: null,
            active_stage_index: 0,
            accordion_open: {},
        });

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
            await this.fetchData();
        });

        onMounted(() => {
            this._renderDonut();
        });

        onPatched(() => {
            this._renderDonut();
        });

        // ── Tambah ini ──
        onWillUnmount(() => {
            Object.values(this._donutInstances).forEach(chart => {
                if (chart) chart.destroy();
            });
            this._donutInstances = {};
        });
    }

    // ─── Render donut chart setelah DOM siap ────────────────────────────────

    _renderDonut() {
    if (!this.state.selected_mou) return;
    const mou = this.state.selected_mou;
    const canvasId = `donut_${mou.id}`;
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // ── Destroy via Chart.getChart() — lebih reliable dari instance cache ──
    // eslint-disable-next-line no-undef
    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
        existingChart.destroy();
    }
    // Bersihkan cache instance lama juga
    if (this._donutInstances[mou.id]) {
        delete this._donutInstances[mou.id];
    }

    const done    = parseInt(canvas.dataset.done    || 0);
    const process = parseInt(canvas.dataset.process || 0);
    const waiting = parseInt(canvas.dataset.waiting || 0);
    const pct     = parseInt(canvas.dataset.pct     || 0);

    // eslint-disable-next-line no-undef
    this._donutInstances[mou.id] = new Chart(canvas, {
        type: "doughnut",
        data: {
            labels: ["Selesai", "Proses", "Menunggu"],
            datasets: [{
                data: [done, process, waiting],
                backgroundColor: ["#198754", "#0d6efd", "#dee2e6"],
                borderColor:     ["#198754", "#0d6efd", "#bdbdbd"],
                borderWidth: 1,
                hoverOffset: 4,
            }],
        },
        options: {
            responsive: false,
            cutout: "68%",
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ` ${ctx.label}: ${ctx.raw} tahapan`,
                    },
                },
            },
        },
        plugins: [{
            id: "centerLabel",
            afterDraw(chart) {
                const { ctx, chartArea: { width, height, left, top } } = chart;
                const cx = left + width  / 2;
                const cy = top  + height / 2;
                ctx.save();
                ctx.textAlign    = "center";
                ctx.textBaseline = "middle";
                ctx.font         = "500 18px sans-serif";
                ctx.fillStyle    = "#198754";
                ctx.fillText(`${pct}%`, cx, cy - 6);
                ctx.font         = "11px sans-serif";
                ctx.fillStyle    = "#6c757d";
                ctx.fillText("progress", cx, cy + 11);
                ctx.restore();
            },
        }],
    });
}

    // ─── Helper: persentase stage Registrasi ────────────────────────────────

    /**
     * Dipakai dari template XML:  getRegistrasiPct(stage)
     * Menghitung % selesai dari gabungan details + sub_registrasi.
     */
    getRegistrasiPct(stage) {
        if (!stage) return 0;
        const sub = stage.sub_registrasi || {};
        const allItems = [
            ...(stage.details            || []),
            ...(sub.brand                || []),
            ...(sub.nie                  || []),
            ...(sub.halal                || []),
        ];
        if (allItems.length === 0) return 0;
        const doneCount = allItems.filter(i => i.is_done).length;
        return Math.round((doneCount / allItems.length) * 100);
    }

    // ─── Fetch & Build ───────────────────────────────────────────────────────

    async fetchData() {
        const result = await this.orm.call("dashboard.timeline.mou", "get_timeline_data", []);
        if (result && result.length > 0) {
            this.state.all_mou = this.buildTimelineData(result);
            this.state.selected_mou = this.state.all_mou[0];

            result.forEach(mou => {
                this.state.accordion_open[mou.id] = {
                    // Registrasi
                    brand: false,
                    nie: false,
                    halal: false,
                    // Pengadaan
                    peng_pr: false,
                    peng_po: false,
                    peng_delivered: false,
                    delivery_pk: false,
                    delivery_retur: false,
                };
            });

            this.autoSelectActiveStage();
        }
    }

    // computed properties pelanggan dan mou

    get uniquePelanggan() {
        const seen = new Set(); 
        return this.state.all_mou.filter(m => {
            if (seen.has(m.pelanggan)) return false;
            seen.add(m.pelanggan);
            return true;
        });
    }

    get mouForSelectedPelanggan() {
        if (!this.state.selected_mou) return [];
        return this.state.all_mou.filter(
            m => m.pelanggan === this.state.selected_mou.pelanggan
        );
    }

    // ─── Build Timeline ──────────────────────────────────────────────────────

    buildTimelineData(rawData) {
        return rawData.map(mou => {
            const c = mou.container || {};

            let stages = [
                { code: 'mou',               name: '1. MOU',               details: [], sub_registrasi: null },
                { code: 'biaya_registrasi',   name: '2. Biaya Registrasi',  details: [], sub_registrasi: null },
                { code: 'dp',                 name: '3. DP',                details: [], sub_registrasi: null },
                { code: 'registrasi',         name: '4. Registrasi',        details: [], sub_registrasi: { brand: [], nie: [], halal: [] } },
                { code: 'pengadaan',          name: '5. Pengadaan',         details: [], sub_registrasi: null },
                { code: 'produksi',           name: '6. Produksi',          details: [], sub_registrasi: null },
                { code: 'qc',                 name: '7. QC',                details: [], sub_registrasi: null },
                { code: 'bp',                 name: '8. BP',                details: [], sub_registrasi: null },
                { code: 'delivery',           name: '9. Delivery',          details: [], sub_registrasi: null },
            ];

            // ── Stage 1: MOU ──────────────────────────────────────────────
            stages.find(s => s.code === 'mou').details.push({
                label: 'MOU Disahkan',
                date: this.formatDate(mou.tgl_draft),
                is_done: true,
            });

            // ── Stage 2: Biaya Registrasi ─────────────────────────────────
            const regStage = stages.find(s => s.code === 'biaya_registrasi');
            mou.setups.forEach(setup => {
                if (setup.reg_due_date || setup.reg_payment_date) {
                    const isFree = setup.is_free;
                    regStage.details.push({
                        label: `Tagihan Registrasi (${setup.name}) — ${isFree ? 'Free' : this.formatCurrency(setup.reg_nilai)}`,
                        date: setup.reg_payment_date
                            ? `Lunas: ${this.formatDate(setup.reg_payment_date)}`
                            : `Jatuh Tempo: ${this.formatDate(setup.reg_due_date)}`,
                        is_done: !!setup.reg_payment_date || isFree,
                    });
                }
            });
            if (regStage.details.length === 0 && c.reg_due_date) {
                regStage.details.push({
                    label: `Tagihan Registrasi — ${this.formatCurrency(c.reg_nilai)}`,
                    date: c.reg_actual_date
                        ? `Lunas: ${this.formatDate(c.reg_actual_date)}`
                        : `Jatuh Tempo: ${this.formatDate(c.reg_due_date)}`,
                    is_done: !!c.reg_actual_date,
                });
            }

            // ── Stage 3: DP ───────────────────────────────────────────────
            const dpStage = stages.find(s => s.code === 'dp');
            mou.setups.forEach(setup => {
                if (setup.dp_due_date || setup.dp_payment_date) {
                    const isFree = setup.is_free;
                    dpStage.details.push({
                        label: `Tagihan DP (${setup.name}) — ${isFree ? 'Free' : this.formatCurrency(setup.dp_nilai)}`,
                        date: setup.dp_payment_date
                            ? `Lunas: ${this.formatDate(setup.dp_payment_date)}`
                            : `Jatuh Tempo: ${this.formatDate(setup.dp_due_date)}`,
                        is_done: !!setup.dp_payment_date || isFree,
                    });
                }
            });
            if (dpStage.details.length === 0 && c.dp_due_date) {
                dpStage.details.push({
                    label: `Tagihan DP — ${this.formatCurrency(c.dp_nilai)}`,
                    date: c.dp_actual_date
                        ? `Lunas: ${this.formatDate(c.dp_actual_date)}`
                        : `Jatuh Tempo: ${this.formatDate(c.dp_due_date)}`,
                    is_done: !!c.dp_actual_date,
                });
            }

            // ── Stage 4: Registrasi ───────────────────────────────────────
            const registrasiStage = stages.find(s => s.code === 'registrasi');
            mou.setups.forEach(setup => {
                if (setup.nie_due_date || setup.nie_payment_date) {
                    const isFree = setup.is_free;
                    registrasiStage.details.push({
                        label: `Tagihan NIE (${setup.name}) — ${isFree ? 'Free' : this.formatCurrency(setup.nie_nilai)}`,
                        date: setup.nie_payment_date
                            ? `Lunas: ${this.formatDate(setup.nie_payment_date)}`
                            : `Jatuh Tempo: ${this.formatDate(setup.nie_due_date)}`,
                        is_done: !!setup.nie_payment_date || isFree,
                    });
                }
            });
            if (registrasiStage.details.length === 0 && c.nie_due_date) {
                registrasiStage.details.push({
                    label: `Tagihan NIE — ${this.formatCurrency(c.nie_nilai)}`,
                    date: c.nie_actual_date
                        ? `Lunas: ${this.formatDate(c.nie_actual_date)}`
                        : `Jatuh Tempo: ${this.formatDate(c.nie_due_date)}`,
                    is_done: !!c.nie_actual_date,
                });
            }

            // Sub-registrasi (accordion detail)
            const reg = mou.registrasi;
            if (reg) {
                (reg.brand || []).forEach(item => {
                    registrasiStage.sub_registrasi.brand.push({
                        label: `${item.brand} (${item.name})`,
                        owner: item.owner,
                        status_label: item.status_label,
                        date: item.tgl_terbit
                            ? `NIE Terbit: ${this.formatDate(item.tgl_terbit)}`
                            : 'Belum ada NIE',
                        is_done: item.is_done,
                    });
                });

                (reg.nie || []).forEach(item => {
                    registrasiStage.sub_registrasi.nie.push({
                        label: `${item.brand} — ${item.product_name} (${item.name})`,
                        status_label: item.status_label,
                        nie_number: item.nie_number,
                        date: item.tgl_terbit
                            ? `NIE Terbit: ${this.formatDate(item.tgl_terbit)}`
                            : item.tgl ? `Submit: ${this.formatDate(item.tgl)}` : '-',
                        masa_berakhir: item.masa_berakhir
                            ? `Berlaku s/d: ${this.formatDate(item.masa_berakhir)}`
                            : null,
                        is_done: item.is_done,
                    });
                });

                (reg.halal || []).forEach(item => {
                    registrasiStage.sub_registrasi.halal.push({
                        label: `${item.brand} — ${item.product_name} (${item.name})`,
                        status_label: item.status_label,
                        nomor_sertifikat: item.nomor_sertifikat,
                        date: item.tgl_terbit
                            ? `Terbit: ${this.formatDate(item.tgl_terbit)}`
                            : item.tgl ? `Pengajuan: ${this.formatDate(item.tgl)}` : '-',
                        masa_berakhir: item.masa_berakhir
                            ? `Berlaku s/d: ${this.formatDate(item.masa_berakhir)}`
                            : null,
                        is_done: item.is_done,
                        is_expired: item.is_expired,
                        sisa_hari: item.sisa_hari,
                    });
                });

                registrasiStage.sub_summary = {
                    brand: {
                        total: c.brand_count || registrasiStage.sub_registrasi.brand.length,
                        done:  c.brand_done  || registrasiStage.sub_registrasi.brand.filter(i => i.is_done).length,
                    },
                    nie: {
                        total: c.nie_count || registrasiStage.sub_registrasi.nie.length,
                        done:  c.nie_done  || registrasiStage.sub_registrasi.nie.filter(i => i.is_done).length,
                    },
                    halal: {
                        total: c.halal_count || registrasiStage.sub_registrasi.halal.length,
                        done:  c.halal_done  || registrasiStage.sub_registrasi.halal.filter(i => i.is_done).length,
                    },
                };
            }

            // ── Stage 5: Pengadaan ────────────────────────────────────────────
            const pengStage = stages.find(s => s.code === 'pengadaan');

            // Tagihan pengadaan dari setup
            mou.setups.forEach(setup => {
                if (setup.peng_due_date || setup.peng_payment_date) {
                    const isFree = setup.is_free;
                    pengStage.details.push({
                        label: `Tagihan Pengadaan (${setup.name}) — ${isFree ? 'Free' : this.formatCurrency(setup.peng_nilai)}`,
                        date: setup.peng_payment_date
                            ? `Lunas: ${this.formatDate(setup.peng_payment_date)}`
                            : `Jatuh Tempo: ${this.formatDate(setup.peng_due_date)}`,
                        is_done: !!setup.peng_payment_date || isFree,
                    });
                }
            });
            if (pengStage.details.length === 0 && c.peng_due_date) {
                pengStage.details.push({
                    label: `Tagihan Pengadaan — ${this.formatCurrency(c.peng_nilai)}`,
                    date: c.peng_actual_date
                        ? `Lunas: ${this.formatDate(c.peng_actual_date)}`
                        : `Jatuh Tempo: ${this.formatDate(c.peng_due_date)}`,
                    is_done: !!c.peng_actual_date,
                });
            }

            // ── Sub Pengadaan: accordion per PR ──────────────────────────────
            pengStage.sub_pengadaan = {
                pr: [],
                po: [],
                delivered: [],
            };

            // Hindari data ganda
            const poSeen = new Set();
            const deliveredMap = new Map();

            (mou.pr_data || []).forEach(pr => {

                // ==========================
                // PURCHASE REQUEST
                // ==========================
                pengStage.sub_pengadaan.pr.push({
                    label: pr.name,
                    product_summary: pr.product_summary,
                    date: pr.date_usulan
                        ? this.formatDate(pr.date_usulan)
                        : '-',
                    is_done: pr.pr_is_done,
                    is_urgent: pr.is_urgent,
                    state_label: pr.state_label,
                    amount: this.formatCurrency(pr.total_amount),
                });

                // ==========================
                // PURCHASE ORDER (UNIQUE)
                // ==========================
                if (
                    pr.po_name &&
                    !poSeen.has(pr.po_name)
                ) {

                    poSeen.add(pr.po_name);

                    pengStage.sub_pengadaan.po.push({
                        label: pr.po_name,
                        date: pr.po_date
                            ? this.formatDate(pr.po_date)
                            : '-',
                        is_done: pr.po_is_done,
                        pr_ref: pr.name,
                        po_state: pr.po_state,
                    });
                }

                // ==========================
                // ARRIVED / DELIVERED (UNIQUE)
                // ==========================
                console.log(
                    "DELIVERY",
                    pr.delivered_name,
                    pr.name
                );
                if (pr.delivered_name) {

                    if (!deliveredMap.has(pr.delivered_name)) {

                        deliveredMap.set(pr.delivered_name, {
                            label: pr.delivered_name,
                            date: pr.delivered_date
                                ? this.formatDate(pr.delivered_date)
                                : '-',
                            is_done: pr.delivered,
                            pr_ref: pr.name,
                        });

                    }

                }

                if (pr.po_name && !poSeen.has(pr.po_name)) {

                poSeen.add(pr.po_name);

                pengStage.sub_pengadaan.po.push({
                    label: pr.po_name,
                    date: pr.po_date
                        ? this.formatDate(pr.po_date)
                        : '-',
                    is_done: pr.po_is_done,
                    pr_ref: pr.name,
                    po_state: pr.po_state,
                });
                }

                pengStage.sub_pengadaan.delivered.push({
                    label: pr.delivered_name || '-',
                    date: pr.delivered_date ? this.formatDate(pr.delivered_date) : '-',
                    is_done: pr.delivered,
                    pr_ref: pr.name,
                });
            });

            // Summary badge
            pengStage.sub_summary_pengadaan = {
                pr: {
                    total: pengStage.sub_pengadaan.pr.length,
                    done:  pengStage.sub_pengadaan.pr.filter(i => i.is_done).length,
                },
                po: {
                    total: pengStage.sub_pengadaan.po.length,
                    done:  pengStage.sub_pengadaan.po.filter(i => i.is_done).length,
                },
                delivered: {
                    total: pengStage.sub_pengadaan.delivered.length,
                    done:  pengStage.sub_pengadaan.delivered.filter(i => i.is_done).length,
                },
            };

            // ── Stage 8: BP (Balance Payment) ────────────────────────────
            const bpStage = stages.find(s => s.code === 'bp');
            mou.setups.forEach(setup => {
                if (setup.bp_due_date || setup.bp_payment_date) {
                    const isFree = setup.is_free;
                    bpStage.details.push({
                        label: `Tagihan BP (${setup.name}) — ${isFree ? 'Free' : this.formatCurrency(setup.bp_nilai)}`,
                        date: setup.bp_payment_date
                            ? `Lunas: ${this.formatDate(setup.bp_payment_date)}`
                            : `Jatuh Tempo: ${this.formatDate(setup.bp_due_date)}`,
                        is_done: !!setup.bp_payment_date || isFree,
                    });
                }
            });
            if (bpStage.details.length === 0 && c.bp_due_date) {
                bpStage.details.push({
                    label: `Tagihan BP — ${this.formatCurrency(c.bp_nilai)}`,
                    date: c.bp_actual_date
                        ? `Lunas: ${this.formatDate(c.bp_actual_date)}`
                        : `Jatuh Tempo: ${this.formatDate(c.bp_due_date)}`,
                    is_done: !!c.bp_actual_date,
                });
            }

            // ── Stage 9: Delivery ────────────────────────────────────────
            const deliveryStage = stages.find(s => s.code === 'delivery');
            deliveryStage.sub_delivery = { picking: [], retur: [] };

            (mou.delivery_data?.picking || []).forEach(pk => {
                deliveryStage.sub_delivery.picking.push({
                    label: pk.name,
                    state_label: pk.state_label,
                    is_done: pk.is_done,
                    date: pk.date_done
                        ? `Selesai: ${this.formatDate(pk.date_done)}`
                        : pk.scheduled_date
                            ? `Estimasi: ${this.formatDate(pk.scheduled_date)}`
                            : '-',
                    lines: (pk.lines || []).map(l => ({
                        label: `${l.product} — ${l.qty} ${l.uom}`,
                        kemasan: l.kemasan,
                    })),
                });

                deliveryStage.details.push({
                    label: `Pengiriman ${pk.name}`,
                    date: pk.date_done
                        ? this.formatDate(pk.date_done)
                        : (pk.scheduled_date ? `Estimasi: ${this.formatDate(pk.scheduled_date)}` : '-'),
                    is_done: pk.is_done,
                });
            });

            (mou.delivery_data?.retur || []).forEach(rt => {
                deliveryStage.sub_delivery.retur.push({
                    label: rt.name,
                    state_label: rt.state_label,
                    is_done: rt.is_done,
                    origin: rt.origin_picking,
                    date: rt.date_done
                        ? `Selesai: ${this.formatDate(rt.date_done)}`
                        : rt.scheduled_date
                            ? `Estimasi: ${this.formatDate(rt.scheduled_date)}`
                            : '-',
                    lines: (rt.lines || []).map(l => `${l.product} — ${l.qty} ${l.uom}`),
                });
                // Catatan: retur TIDAK dipush ke deliveryStage.details,
                // supaya tidak dianggap "tagihan/kiriman utama" dalam
                // perhitungan status stage — cuma info tambahan.
            });

            deliveryStage.sub_summary_delivery = {
                picking: {
                    total: deliveryStage.sub_delivery.picking.length,
                    done:  deliveryStage.sub_delivery.picking.filter(i => i.is_done).length,
                },
                retur: {
                    total: deliveryStage.sub_delivery.retur.length,
                    done:  deliveryStage.sub_delivery.retur.filter(i => i.is_done).length,
                },
            };

            // ── Stage 6–9: Placeholder siap sambung ──────────────────────
            // stages.find(s => s.code === 'produksi').details.push({ ... })
            // stages.find(s => s.code === 'qc').details.push({ ... })
            // stages.find(s => s.code === 'bp').details.push({ ... })
            // stages.find(s => s.code === 'delivery').details.push({ ... })

            // ── Hitung status tiap stage ──────────────────────────────────
            stages.forEach((stage, i) => {
                const result = this._computeStageStatus(stage, i, stages);
                stage.status   = result.status;
                stage.color    = result.color;
                stage.progress = result.progress;
            });

            // Progress keseluruhan
            const doneCount    = stages.filter(s => s.status === 'done').length;
            const processCount = stages.filter(s => s.status === 'process').length;
            const progressPercent = Math.round(
                ((doneCount + processCount * 0.5) / stages.length) * 100
            );

            return {
                id: mou.id,
                pelanggan: mou.pelanggan,
                no_mou: mou.no_mou,
                deadline: mou.deadline ? this.formatDate(mou.deadline) : null,
                progress: progressPercent,
                stages,
                sale_orders: mou.sale_orders || [],
            };
        });
    }

    // ─── Logika Status Stage ─────────────────────────────────────────────────

    _computeStageStatus(stage, index, allStages) {
    if (stage.code === 'mou') {
        return { status: 'done', color: 'success', progress: 'full' };
    }

    if (index > 0 && allStages[index - 1].status === 'waiting') {
        return { status: 'waiting', color: 'secondary', progress: 'none' };
    }

    if (stage.code === 'registrasi') {
        const sub = stage.sub_registrasi || {};
        const allItems = [
            ...stage.details,
            ...(sub.brand || []),
            ...(sub.nie   || []),
            ...(sub.halal || []),
        ];
        if (allItems.length === 0) return { status: 'waiting', color: 'secondary', progress: 'none' };
        if (allItems.every(i => i.is_done))  return { status: 'done',    color: 'success', progress: 'full' };
        if (allItems.some(i => i.is_done))   return { status: 'process', color: 'warning', progress: 'partial' };
        return                                      { status: 'process', color: 'primary', progress: 'none' };
    }

    if (stage.code === 'pengadaan') {
        const sub = stage.sub_pengadaan || {};
        const allItems = [
            ...stage.details,
            ...(sub.pr        || []),
            ...(sub.po        || []),
            ...(sub.delivered || []),
        ];
        if (allItems.length === 0) return { status: 'waiting', color: 'secondary', progress: 'none' };
        if (allItems.every(i => i.is_done))  return { status: 'done',    color: 'success', progress: 'full' };
        if (allItems.some(i => i.is_done))   return { status: 'process', color: 'warning', progress: 'partial' };
        return                                      { status: 'process', color: 'primary', progress: 'none' };
    }

    if (stage.code === 'delivery') {
        const sub = stage.sub_delivery || {};
        const allItems = [
            ...stage.details,
            ...(sub.picking || []),
        ];
        if (allItems.length === 0) return { status: 'waiting', color: 'secondary', progress: 'none' };
        if (allItems.every(i => i.is_done))  return { status: 'done',    color: 'success', progress: 'full' };
        if (allItems.some(i => i.is_done))   return { status: 'process', color: 'warning', progress: 'partial' };
        return                                      { status: 'process', color: 'primary', progress: 'none' };
    }
    
    if (stage.details.length === 0) return { status: 'waiting', color: 'secondary', progress: 'none' };
    if (stage.details.every(d => d.is_done)) return { status: 'done',    color: 'success', progress: 'full' };
    if (stage.details.some(d => d.is_done))  return { status: 'process', color: 'warning', progress: 'partial' };
    return                                          { status: 'process', color: 'primary', progress: 'none' };
}

    // ─── Accordion ───────────────────────────────────────────────────────────

    toggleAccordion(mouId, subKey) {
        if (!this.state.accordion_open[mouId]) {
            this.state.accordion_open[mouId] = { brand: false, nie: false, halal: false, delivery_pk: false};
        }
        this.state.accordion_open[mouId][subKey] = !this.state.accordion_open[mouId][subKey];
    }

    isAccordionOpen(mouId, subKey) {
        return this.state.accordion_open[mouId]?.[subKey] || false;
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    formatDate(dateString) {
        if (!dateString) return '-';
        const [year, month, day] = dateString.split('-');
        return `${day}-${month}-${year}`;
    }

    formatCurrency(value) {
        if (!value) return 'Rp 0';
        return new Intl.NumberFormat('id-ID', {
            style: 'currency',
            currency: 'IDR',
            minimumFractionDigits: 0,
        }).format(value);
    }

    // ─── UI Interaction ───────────────────────────────────────────────────────

    onChangePelanggan(ev) {
        const pelanggan = ev.target.value;
        // Ambil MOU 
        const firstMou = this.state.all_mou.find(m => m.pelanggan === pelanggan);
        if (firstMou) {
            this.state.selected_mou = firstMou;
            this.state.selected_so_id = null;
            this.autoSelectActiveStage();
        }
    }

    onChangeMou(ev) {
        const selectedId = parseInt(ev.target.value);
        const found = this.state.all_mou.find(m => m.id === selectedId);
        if (found) {
            this.state.selected_mou = found;
            this.state.selected_so_id = null;
            this.autoSelectActiveStage();
        }
    }

    onChangeSo(ev) {
        const value = ev.target.value;
        this.state.selected_so_id = value ? parseInt(value) : null;
    }

    get selectedSaleOrder() {
        if (!this.state.selected_mou || !this.state.selected_so_id) return null;
        return (this.state.selected_mou.sale_orders || []).find(
            so => so.id === this.state.selected_so_id
        );
    }

    get displayStages() {
        if (!this.state.selected_mou) return [];
        const stages = this.state.selected_mou.stages;
        const so = this.selectedSaleOrder;

        // Tidak ada SO dipilih, atau SO yang dipilih bukan repeat order → tampilan normal
        if (!so || !so.is_repeat_order) {
            return stages;
        }

        // Repeat Order: MOU, Biaya Registrasi, Registrasi otomatis "Selesai"
        const forcedDoneCodes = ['mou', 'biaya_registrasi', 'registrasi'];

        // Mapping timeline_stage SO → code stage dashboard
        const stageCodeMap = {
            reg: 'biaya_registrasi', dp: 'dp', nie: 'registrasi',
            peng: 'pengadaan', bp: 'bp',
        };

        return stages.map(stage => {
            if (forcedDoneCodes.includes(stage.code)) {
                return { ...stage, status: 'done', progress: 'full' };
            }
            // Stage yang cocok dengan tahapan SO ini → progress ikut status SO itu
            if (stageCodeMap[so.timeline_stage] === stage.code) {
                return { ...stage, status: so.is_paid ? 'done' : 'process' };
            }
            return stage;
        });
    }

    selectStage(index) {
        this.state.active_stage_index = index;
    }

    autoSelectActiveStage() {
        if (!this.state.selected_mou) return;
        const stages = this.state.selected_mou.stages;
        const processIndex = stages.findIndex(s => s.status === 'process');
        if (processIndex !== -1) {
            this.state.active_stage_index = processIndex;
            return;
        }
        let lastDone = 0;
        stages.forEach((s, i) => { if (s.status === 'done') lastDone = i; });
        this.state.active_stage_index = lastDone;
    }
}

TimelineDashboard.template = "custom_mou.TimelineTemplate";
registry.category("actions").add("custom_timeline.main_action", TimelineDashboard);