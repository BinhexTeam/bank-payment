# Copyright 2024 Binhex - Adasat Torres de León.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.ach_class import ACHClass
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transfer_intent_create_request import TransferIntentCreateRequest
from plaid.model.transfer import Transfer
from plaid.model.transfer_intent_create_mode import (
    TransferIntentCreateMode,
)
from plaid.model.transfer_user_in_request import TransferUserInRequest

from odoo import _, models
from odoo.exceptions import ValidationError


class PlaidInterface(models.AbstractModel):
    _name = "plaid.interface"
    _description = "Plaid Interface"

    def _client(self, client_id, secret, host):
        configuration = plaid.Configuration(
            host=host,
            api_key={
                "clientId": client_id or "",
                "secret": secret or "",
            },
        )
        try:
            return plaid_api.PlaidApi(plaid.ApiClient(configuration))
        except plaid.ApiException as e:
            raise ValidationError(_("Error getting client api: %s") % e.body) from e

    def _create_transfer(
        self,
        client,
        amount,
        partner_name,
        description,
    ):
        request = TransferIntentCreateRequest(
            mode=TransferIntentCreateMode("PAYMENT"),
            amount="{:.2f}".format(amount),
            ach_class=ACHClass("ppd"),
            description=description,
            user=TransferUserInRequest(partner_name),
        )
        try:
            response = client.transfer_intent_create(request)
        except plaid.ApiException as e:
            raise ValidationError(_("Error creating transfer: %s") % e.body) from e
        return response.to_dict()["transfer_intent"]["id"]

    def _link(self, client, transfer_intent_id, webhook, redirect_uri):
        request = LinkTokenCreateRequest(
            products=[Products("transfer")],
            client_name="Plaid",
            country_codes=[CountryCode("US")],
            transfer=Transfer(transfer_intent_id),
            webhook=webhook,
            redirect_uri=redirect_uri,
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="client_user_id"),
        )
        try:
            response = client.link_token_create(request)
        except plaid.ApiException as e:
            raise ValidationError(_("Error getting link token: %s") % e.body) from e
        return response.to_dict()["link_token"]
