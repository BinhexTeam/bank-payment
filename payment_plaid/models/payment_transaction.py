from odoo import api, fields, models, _
from werkzeug import urls
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_plaid.controllers.main import PlaidController


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    plaid_transaction_id = fields.Char()

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "plaid":
            return res
        return {
            "amount": self.amount,
            "country": self.partner_country_id.code,
            "currency_code": self.currency_id.name,
            "handling": self.fees,
            "item_number": self.reference,
            "lc": self.partner_lang,
        }

    def _get_processing_values(self):
        res = super()._get_processing_values()
        if self.provider_code != "plaid":
            return res
        res.update(
            {
                "link_token": self._get_link_token(),
            }
        )
        return res

    def _get_link_token(self):
        base_url = self.provider_id.get_base_url()
        webhook_url = urls.url_join(base_url, PlaidController._webhook_url)
        redirect_url = urls.url_join(base_url, PlaidController._return_url)
        interface = self.env["plaid.interface"]

        client = interface._client(
            self.provider_id.plaid_client_id,
            self.provider_id.plaid_secret,
            self.provider_id._plaid_get_api_url(),
        )
        transfer_id = interface._create_transfer(
            client,
            self.amount,
            self.partner_name,
            f"{self.reference}",
        )
        return interface._link(
            client,
            transfer_id,
            webhook_url,
            redirect_url,
        )
