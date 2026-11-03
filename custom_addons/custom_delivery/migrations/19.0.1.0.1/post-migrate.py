def migrate(cr, version):
    """Delivery Order lama dari SO ber-MOU: isi No MOU dari SO-nya.

    Memakai SQL, bukan ORM: saat migrasi ini jalan, modul lain (custom_mou)
    belum diupgrade sehingga kolom baru di sale_order belum ada dan ORM gagal memuatnya.
    """
    cr.execute("""
        UPDATE stock_picking picking
           SET mou_id = so.mou_id
          FROM sale_order so
         WHERE picking.sale_id = so.id
           AND picking.mou_id IS NULL
           AND so.mou_id IS NOT NULL
    """)
