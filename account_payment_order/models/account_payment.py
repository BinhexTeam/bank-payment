# Copyright 2019 ACSONE SA/NV
# Copyright 2022 Tecnativa - Pedro M. Baeza
# Copyright 2023 Noviat
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_order_id = fields.Many2one(comodel_name="account.payment.order")
    payment_line_ids = fields.Many2many(comodel_name="account.payment.line")
    order_state = fields.Selection(
        related="payment_order_id.state", string="Payment Order State"
    )

    @api.depends("payment_type", "journal_id")
    def _compute_payment_method_line_fields(self):
        res = super()._compute_payment_method_line_fields()
        for pay in self:
            if pay.payment_order_id:
                pay.available_payment_method_line_ids = (
                    pay.payment_order_id.journal_id._get_available_payment_method_lines(
                        pay.payment_type
                    )
                )
            else:
                pay.available_payment_method_line_ids = (
                    pay.journal_id._get_available_payment_method_lines(
                        pay.payment_type
                    ).filtered(lambda x: not x.payment_method_id.payment_order_only)
                )
            to_exclude = pay._get_payment_method_codes_to_exclude()
            if to_exclude:
                pay.available_payment_method_line_ids = (
                    pay.available_payment_method_line_ids.filtered(
                        lambda x: x.code not in to_exclude
                    )
                )
        return res

    @api.constrains("payment_method_line_id")
    def _check_payment_method_line_id(self):
        for pay in self:
            transfer_journal = (
                pay.payment_order_id.payment_mode_id.transfer_journal_id
                or pay.company_id.transfer_journal_id
            )
            if pay.journal_id == transfer_journal:
                continue
            else:
                super(AccountPayment, pay)._check_payment_method_line_id()
        return

    def update_payment_reference(self):
        view = self.env.ref("account_payment_order.account_payment_update_view_form")
        return {
            "name": _("Update Payment Reference"),
            "view_type": "form",
            "view_mode": "form",
            "res_model": "account.payment.update",
            "view_id": view.id,
            "target": "new",
            "type": "ir.actions.act_window",
            "context": dict(
                self.env.context, default_payment_reference=self.payment_reference
            ),
        }
