def migrate(cr, version):
    """PO lama: bentuk rincian Customer PR dari MOU/PR di bagian atas PO (satu baris per produk)."""
    cr.execute("""
        INSERT INTO purchase_order_customer_line
               (order_id, sequence, request_id, mou_id, customer_id, sale_order_id, product_id, qty, uom_id)
        SELECT po.id, 10, po.purchase_request_id, po.mou_id, po.customer_id, po.sale_order_id,
               line.product_id, SUM(line.product_qty), line.product_uom_id
          FROM purchase_order po
          JOIN purchase_order_line line ON line.order_id = po.id
         WHERE (po.mou_id IS NOT NULL OR po.purchase_request_id IS NOT NULL)
           AND line.display_type IS NULL
           AND line.product_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM purchase_order_customer_line existing WHERE existing.order_id = po.id)
         GROUP BY po.id, po.purchase_request_id, po.mou_id, po.customer_id, po.sale_order_id,
                  line.product_id, line.product_uom_id
    """)
