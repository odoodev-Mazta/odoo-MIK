def migrate(cr, version):
    """Baris detail lama tanpa line_type diisi, agar constraint NOT NULL bisa dipasang."""
    cr.execute("""
        UPDATE usulan_usulan_dana_line
           SET line_type = CASE WHEN setup_item_id IS NOT NULL THEN 'setup' ELSE 'product' END
         WHERE line_type IS NULL
    """)
