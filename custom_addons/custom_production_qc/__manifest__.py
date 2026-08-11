{
    "name": "Production Quality Control",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Production Quality Control Management",

    "depends": [
        "base",
        "mail",
        "mrp",
        "custom_production_planning",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/qc_template_views.xml",
        "views/qc_parameter_views.xml",
        "views/qc_schedule_views.xml",
        "views/production_machine_views.xml",
        "views/mrp_workorder_views.xml",
        "views/qc_menus.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}