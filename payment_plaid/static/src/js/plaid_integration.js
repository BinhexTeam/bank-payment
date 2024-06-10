odoo.define("payment_plaid.plaid_integration", (require) => {
    "use strict";
    const publicWidget = require("web.public.widget");
    require("web.dom_ready");

    publicWidget.registry.PlaidIntegration = publicWidget.Widget.extend({
        selector: "div .o_plaid_integration",

        PlaidIntegration: function () {
            console.log("Plaid Integration");
        },
    });

    publicWidget.registry.PaymentManageForm.extend({});

    publicWidget.registry.PaymentCheckoutForm.include({
        _processRedirectPayment: (code, providerId, processingValues) => {
            if (!code === "plaid") {
                return this._super(...arguments);
            } else {
                console.log(processingValues);
                const handler = Plaid.create({
                    clientName: "Plaid Quickstart",
                    product: ["transfer"],
                    onSuccess: (public_token) => {},
                    countryCodes: ["US"],
                    language: "en",
                    token: processingValues.link_token,
                });
                handler.open();
            }
        },
    });
});
