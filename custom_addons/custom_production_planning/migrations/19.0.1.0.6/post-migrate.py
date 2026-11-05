def migrate(cr, version):
    """Baris hasil Split lama belum membawa Produk Jadi (brand) dari induknya."""
    cr.execute("""
        UPDATE mrp_production_plan_product_line child
           SET finished_product_id = parent.finished_product_id
          FROM mrp_production_plan_product_line parent
         WHERE child.parent_product_line_id = parent.id
           AND child.finished_product_id IS NULL
           AND parent.finished_product_id IS NOT NULL
    """)
