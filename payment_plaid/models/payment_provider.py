from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import plaid


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("plaid", "Plaid")], ondelete={"plaid": "set default"}
    )
    plaid_client_id = fields.Char()
    plaid_secret = fields.Char()

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == "plaid").update(
            {
                "support_fees": True,
            }
        )

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        providers = super()._get_compatible_providers(
            *args, currency_id=currency_id, **kwargs
        )

        currency = self.env["res.currency"].browse(currency_id).exists()
        if currency and currency.name != "USD":
            providers = providers.filtered(lambda p: p.code != "plaid")
        return providers

    def _plaid_get_api_url(self):
        self.ensure_one()
        if self.state == "enabled":
            return plaid.Environment.Production
        return plaid.Environment.Sandbox
