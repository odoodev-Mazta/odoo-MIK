/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";

export class EcatalogueCarousel extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.carouselRef = useRef("carouselContainer");

        // Tambahkan activeIndex di state untuk tahu card mana yang di tengah
        this.state = useState({
            products: [],
            activeIndex: 0,
            isManager: false,
            selectedProduct: null,
        });

        this.isDown = false;
        this.startX = 0;
        this.scrollLeft = 0;

        this.onScroll = this.onScroll.bind(this);
        this.onWheel = this.onWheel.bind(this);
        this.onMouseDown = this.onMouseDown.bind(this);
        this.onMouseLeave = this.onMouseLeave.bind(this);
        this.onMouseUp = this.onMouseUp.bind(this);
        this.onMouseMove = this.onMouseMove.bind(this);

        onWillStart(async () => {
            this.state.isManager = await user.hasGroup("custom_ecatalogue.group_ecatalogue_manager");
            await this.loadProducts();
        });

        onMounted(() => {
            const container = this.carouselRef.el;
            if (container) {
                container.addEventListener('scroll', this.onScroll);

                // Event Wheel dengan passive: false agar preventDefault() berfungsi di browser modern
                container.addEventListener('wheel', this.onWheel, { passive: false });

                // Event Drag Mouse
                container.addEventListener('mousedown', this.onMouseDown);
                container.addEventListener('mouseleave', this.onMouseLeave);
                container.addEventListener('mouseup', this.onMouseUp);
                container.addEventListener('mousemove', this.onMouseMove);

                setTimeout(() => this.onScroll(), 100);
            }
        });

        onWillUnmount(() => {
            const container = this.carouselRef.el;
            if (container) {
                container.removeEventListener('scroll', this.onScroll);
                container.removeEventListener('wheel', this.onWheel);
                container.removeEventListener('mousedown', this.onMouseDown);
                container.removeEventListener('mouseleave', this.onMouseLeave);
                container.removeEventListener('mouseup', this.onMouseUp);
                container.removeEventListener('mousemove', this.onMouseMove);
            }
        });
    }

    // ==========================================
    // LOGIKA EVENT MOUSE DRAG & WHEEL
    // ==========================================
    onWheel(ev) {
        if (!this.carouselRef.el) return;
        const isVerticalScroll = Math.abs(ev.deltaY) > Math.abs(ev.deltaX);
        if (isVerticalScroll) {
            ev.preventDefault(); // Mengubah scroll atas-bawah menjadi kiri-kanan
            this.carouselRef.el.scrollLeft += ev.deltaY;
        }
    }

    onMouseDown(ev) {
        const container = this.carouselRef.el;
        this.isDown = true;

        // Matikan sementara snap CSS saat di-drag agar tidak tersendat (jitter)
        container.style.scrollSnapType = 'none';
        container.style.cursor = 'grabbing';

        this.startX = ev.pageX - container.offsetLeft;
        this.scrollLeft = container.scrollLeft;
    }

    onMouseLeave() {
        this.isDown = false;
        const container = this.carouselRef.el;
        // Kembalikan efek snap dan cursor saat mouse dilepas atau keluar area
        container.style.scrollSnapType = 'x mandatory';
        container.style.cursor = 'grab';
    }

    onMouseUp() {
        this.isDown = false;
        const container = this.carouselRef.el;
        container.style.scrollSnapType = 'x mandatory';
        container.style.cursor = 'grab';
    }

    onMouseMove(ev) {
        if (!this.isDown) return;
        ev.preventDefault(); // Mencegah blok teks biru (text-highlight) saat mouse ditarik

        const container = this.carouselRef.el;
        const x = ev.pageX - container.offsetLeft;

        // Angka * 2 adalah kecepatan geser. Kamu bisa naikkan ke 3 jika ingin lebih sensitif
        const walk = (x - this.startX) * 2;
        container.scrollLeft = this.scrollLeft - walk;
    }

    // ==========================================
    // LOGIKA STATE & SCROLL BAWAAN
    // ==========================================
    onScroll() {
        const container = this.carouselRef.el;
        if (!container) return;

        const containerCenter = container.offsetWidth / 2;
        let closestIndex = 0;
        let minDistance = Infinity;

        const cards = container.querySelectorAll('.carousel-slide');
        cards.forEach((card, index) => {
            const cardCenter = (card.offsetLeft - container.scrollLeft) + (card.offsetWidth / 2);
            const distance = Math.abs(containerCenter - cardCenter);

            if (distance < minDistance) {
                minDistance = distance;
                closestIndex = index;
            }
        });

        if (this.state.activeIndex !== closestIndex) {
            this.state.activeIndex = closestIndex;
        }
    }

    openDetail(product) {
        this.state.selectedProduct = product;
    }
    closeDetail() {
        this.state.selectedProduct = null;
    }

    async createDraftMOU() {
        const masterProductId = this.state.selectedProduct.product_id[0];

        this.closeDetail();

        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Draft MOU",
            res_model: "draft.maklon",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_product: masterProductId,
            }
        });
    }

//    async createQuotation() {
//        const masterProductId = this.state.selectedProduct.product_id[0];
//
//        this.closeDetail();
//
//        this.action.doAction({
//            type: "ir.actions.act_window",
//            name: "New Quotation",
//            res_model: "sale.order",
//            views: [[false, "form"]],
//            target: "current",
//            context: {
//                default_order_line: [[0, 0, {
//                    'product_id': masterProductId,
//                }]]
//            }
//        });
//    }

    async loadProducts() {
        this.state.products = await this.orm.searchRead(
            "ecatalogue.product",
            [],
            ["id", "name", "product_id","image_512", "image_1920", "manfaat",
             "kandungan", "price", "ukuran_ecatalogue", "moq_ecatalogue",
             "total_maklon", "jenis_kemasan", "berat_bersih", "masa_produksi"]
        );
    }

    async deleteProduct(productId) {
        await this.orm.unlink("ecatalogue.product", [productId]);
        await this.loadProducts();
    }

    openAddProductDialog() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ecatalogue.product",
            views: [[false, "form"]],
            target: "new",
        }, {
            onClose: () => {
                this.loadProducts();
            }
        });
    }
}

EcatalogueCarousel.template = "custom_ecatalogue.EcatalogueCarouselTemplate";

registry.category("actions").add("custom_ecatalogue.dashboard", EcatalogueCarousel);