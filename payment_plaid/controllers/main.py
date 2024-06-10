from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError


class PlaidController(http.Controller):

    _return_url = "/payment/plaid/return"
    _webhook_url = "/payment/plaid/webhook"
    _create_link_token_url = "/create/plaid/link_token"

    @http.route(
        _return_url, type="http", auth="public", methods=["GET", "POST"], csrf=False
    )
    def plaid_return_from_checkout(self, **data):
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._get_tx_from_notification_data("plaid", data)
        )
        tx_sudo._handle_notification_data("plaid", data)
        return request.redirect("/payment/status")

    @http.route(_webhook_url, type="json", auth="public", methods=["POST"], csrf=False)
    def plaid_webhook(self, **data):
        try:
            # Check the origin and integrity of the notification
            tx_sudo = (
                request.env["payment.transaction"]
                .sudo()
                ._get_tx_from_notification_data("plaid", data)
            )
            # Handle the notification data
            tx_sudo._handle_notification_data("plaid", data)
        except ValidationError:  # Acknowledge the notification to avoid getting spammed
            pass
