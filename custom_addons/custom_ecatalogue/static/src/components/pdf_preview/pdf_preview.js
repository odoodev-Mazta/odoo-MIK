import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { url } from "@web/core/utils/urls";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { BinaryField } from "@web/views/fields/binary/binary_field";

export class PdfPreviewDialog extends Component {
    static template = "custom_ecatalogue.PdfPreviewDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: String,
        fileUrl: String,
        onDownload: Function,
    };

    get viewerUrl() {
        return `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(this.props.fileUrl)}`;
    }

    get downloadLabel() {
        return _t("Download");
    }

    get closeLabel() {
        return _t("Tutup");
    }
}

patch(BinaryField.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
    },

    async onFileDownload() {
        const { record, name } = this.props;
        if (!record.resId || !this.fileName.toLowerCase().endsWith(".pdf")) {
            return super.onFileDownload();
        }
        const fileUrl = url("/web/content", {
            model: record.resModel,
            id: record.resId,
            field: name,
        });
        const response = await fetch(fileUrl, { method: "HEAD" });
        if (!response.ok) {
            this.notification.add(
                _t("File %s tidak ditemukan di server. Silakan upload ulang.", this.fileName),
                { type: "danger" }
            );
            return;
        }
        this.dialogService.add(PdfPreviewDialog, {
            title: this.fileName,
            fileUrl,
            onDownload: () => super.onFileDownload(),
        });
    },
});
