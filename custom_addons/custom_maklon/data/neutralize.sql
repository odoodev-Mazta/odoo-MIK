-- Dijalankan Odoo.sh saat database dinetralkan (build staging/dev dari produksi):
-- kosongkan parameter integrasi supaya staging TIDAK mengirim kabar ke / menerima
-- request dari Mazta Finance produksi.
UPDATE ir_config_parameter
   SET value = ''
 WHERE key IN ('mazta.base_url', 'mazta.token', 'mazta.secret');
