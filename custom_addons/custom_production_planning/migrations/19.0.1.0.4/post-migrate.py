def migrate(cr, version):
    """Tahap Coding yang sudah ada ikut menentukan batch dan expired (data master noupdate)."""
    cr.execute("""
        UPDATE mrp_production_stage stage
           SET set_batch = TRUE
          FROM ir_model_data data
         WHERE data.model = 'mrp.production.stage'
           AND data.res_id = stage.id
           AND data.module = 'custom_production_planning'
           AND data.name = 'stage_coding'
    """)
