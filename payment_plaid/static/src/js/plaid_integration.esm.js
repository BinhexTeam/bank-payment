/** @odoo-module **/
/* global Plaid */
import {registry} from "@web/core/registry";

export async function plaid_login(env, action) {
    const handler = Plaid.create({
        clientName: "Plaid Quickstart",
        product: ["transfer"],
        onSuccess: (public_token) => {},
        countryCodes: ["US"],
        language: "en",
        token: action.args.token,
    });
    handler.open();
}

registry.category("actions").add("plaid_login", plaid_login);
