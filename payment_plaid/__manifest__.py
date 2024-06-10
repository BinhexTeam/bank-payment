{
    "name": "Payment Provider: Plaid",
    "version": "16.0.1.0.0",
    "category": "payment addons",
    "license": "AGPL-3",
    "summary": "Adds payment with plaid",
    "author": "Binhex, " "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/bank-payment",
    "depends": [
        "payment",
    ],
    "data": [
        "views/payment_plaid_templates.xml",
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "/payment_plaid/static/src/js/*.js",
            "/payment_plaid/static/src/lib/**/*.js",
        ],
    },
    "external_dependencies": {
        "python": ["plaid-python"],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "auto_install": True,
}
