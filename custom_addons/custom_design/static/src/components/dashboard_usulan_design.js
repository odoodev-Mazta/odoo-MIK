/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DesignUsulanDashboard extends Component {
    setup() {
        this.orm = useService("orm");

        this.state = useState({
            stats: {
                total: 0,
                done: 0,
                progress_pct: 0,
                ontime: 0,
                ontime_pct: 0,
            },
            designs: []
        });

        // Tambahkan variabel ini untuk menyimpan data asli agar tidak hilang saat di-filter
        this.allDesigns = [];

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.stats = {
            total: 100,
            done: 66,
            progress_pct: 66,
            ontime: 33,
            ontime_pct: 50,
        };

        // Simpan dummy data ke dalam this.allDesigns terlebih dahulu
        this.allDesigns = [
            { id: 1, date: '2026-04-21', partner_id: [1, 'PT. Maju Jaya'], brand: 'Logitech', state: 'progress', attachment: true },
            { id: 2, date: '2026-04-20', partner_id: [2, 'CV. Makmur Abadi'], brand: 'Razer', state: 'done', attachment: false },
            { id: 3, date: '2026-04-18', partner_id: [3, 'IndoTech Solutions'], brand: 'Corsair', state: 'draft', attachment: true },
            { id: 4, date: '2026-04-15', partner_id: [1, 'PT. Maju Jaya'], brand: 'SteelSeries', state: 'done', attachment: true },
            { id: 5, date: '2026-04-10', partner_id: [4, 'Toko Komputer Sejahtera'], brand: 'Asus ROG', state: 'progress', attachment: false }
        ];

        // Salin data ke state agar tampil di tabel pertama kali
        this.state.designs = [...this.allDesigns];
    }

    // Fungsi pencarian yang sudah diperbarui untuk DUMMY DATA
    onSearchInput(ev) {
        // Ambil teks yang diketik dan ubah ke huruf kecil semua agar pencariannya tidak case-sensitive
        const searchQuery = ev.target.value.toLowerCase();

        if (searchQuery) {
            // Filter data secara lokal menggunakan JavaScript
            this.state.designs = this.allDesigns.filter(design => {
                // Ambil nama pelanggan dari index [1]
                const namaPelanggan = design.partner_id ? design.partner_id[1].toLowerCase() : "";
                const namaBrand = design.brand ? design.brand.toLowerCase() : "";

                // Kembalikan true jika kata kunci ada di nama Pelanggan ATAU Brand
                return namaPelanggan.includes(searchQuery) || namaBrand.includes(searchQuery);
            });
        } else {
            // Jika search bar dihapus/kosong, kembalikan semua data seperti semula
            this.state.designs = [...this.allDesigns];
        }
    }
}

DesignUsulanDashboard.template = "design_module.Dashboard";
registry.category("actions").add("design_module.action_design_dashboard", DesignUsulanDashboard);