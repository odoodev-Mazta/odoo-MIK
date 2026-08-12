{
    "name": "Custom Production Planning",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "author": "William Purba",

    "depends": [
        "mrp",
        "sale_management",
        "product",
        "mail",
        "custom_mou",
    ],

    "data": [
        "data/ir_sequence.xml",
        "security/ir.model.access.csv",
        "views/production_plan_views.xml",
        "views/production_machine_views.xml",
        "views/production_machine_schedule_views.xml",
        "views/mrp_production_views.xml",
        "views/production_dashboard_views.xml",
        "views/production_plan_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "custom_production_planning/static/src/js/production_dashboard.js",
            "custom_production_planning/static/src/xml/production_dashboard.xml",
            "custom_production_planning/static/src/css/production_dashboard.css",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}