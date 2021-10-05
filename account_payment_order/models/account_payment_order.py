# © 2009 EduSense BV (<http://www.edusense.nl>)
# © 2011-2013 Therp BV (<https://therp.nl>)
# © 2016 Serv. Tecnol. Avanzados - Pedro M. Baeza
# © 2016 Akretion (Alexis de Lattre - alexis.delattre@akretion.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPaymentOrder(models.Model):
    _name = 'account.payment.order'
    _description = 'Payment Order'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        string='Number', readonly=True, copy=False)  # v8 field : name
    payment_mode_id = fields.Many2one(
        'account.payment.mode', 'Payment Mode', required=True,
        ondelete='restrict', track_visibility='onchange',
        readonly=True, states={'draft': [('readonly', False)]})
    payment_type = fields.Selection([
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
        ], string='Payment Type', readonly=True, required=True)
    payment_method_id = fields.Many2one(
        'account.payment.method', related='payment_mode_id.payment_method_id',
        readonly=True, store=True)
    company_id = fields.Many2one(
        related='payment_mode_id.company_id', store=True, readonly=True)
    company_currency_id = fields.Many2one(
        related='payment_mode_id.company_id.currency_id', store=True,
        readonly=True)
    bank_account_link = fields.Selection(
        related='payment_mode_id.bank_account_link', readonly=True)
    allowed_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute="_compute_allowed_journal_ids",
        string="Allowed journals",
    )
    journal_id = fields.Many2one(
        'account.journal', string='Bank Journal', ondelete='restrict',
        readonly=True, states={'draft': [('readonly', False)]},
        track_visibility='onchange')
    # The journal_id field is only required at confirm step, to
    # allow auto-creation of payment order from invoice
    company_partner_bank_id = fields.Many2one(
        related='journal_id.bank_account_id', string='Company Bank Account',
        readonly=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('open', 'Confirmed'),
            ('generated', 'File Generated'),
            ('uploaded', 'File Uploaded'),
            ('done', 'Done'),
            ('cancel', 'Cancel'),
        ], string='Status', readonly=True, copy=False, default='draft',
        track_visibility='onchange')
    date_prefered = fields.Selection([
        ('now', 'Immediately'),
        ('due', 'Due Date'),
        ('fixed', 'Fixed Date'),
        ], string='Payment Execution Date Type', required=True, default='due',
        track_visibility='onchange', readonly=True,
        states={'draft': [('readonly', False)]})
    date_scheduled = fields.Date(
        string='Payment Execution Date', readonly=True,
        states={'draft': [('readonly', False)]}, track_visibility='onchange',
        help="Select a requested date of execution if you selected 'Due Date' "
        "as the Payment Execution Date Type.")
    date_generated = fields.Date(string='File Generation Date', readonly=True)
    date_uploaded = fields.Date(string='File Upload Date', readonly=True)
    date_done = fields.Date(string='Done Date', readonly=True)
    generated_user_id = fields.Many2one(
        'res.users', string='Generated by', readonly=True, ondelete='restrict',
        copy=False)
    payment_line_ids = fields.One2many(
        'account.payment.line', 'order_id', string='Transaction Lines',
        readonly=True, states={'draft': [('readonly', False)]})
    # v8 field : line_ids
    bank_line_ids = fields.One2many(
        'bank.payment.line', 'order_id', string="Bank Payment Lines",
        readonly=True,
        help="The bank payment lines are used to generate the payment file. "
        "They are automatically created from transaction lines upon "
        "confirmation of the payment order: one bank payment line can "
        "group several transaction lines if the option "
        "'Group Transactions in Payment Orders' is active on the payment "
        "mode.")
    total_company_currency = fields.Monetary(
        compute='_compute_total', store=True, readonly=True,
        currency_field='company_currency_id')
    bank_line_count = fields.Integer(
        compute='_compute_bank_line_count', string='Number of Bank Lines',
        readonly=True)
    move_ids = fields.One2many(
        'account.move', 'payment_order_id', string='Journal Entries',
        readonly=True)
    description = fields.Char()

    @api.depends('payment_mode_id')
    def _compute_allowed_journal_ids(self):
        for record in self:
            if record.payment_mode_id.bank_account_link == 'fixed':
                record.allowed_journal_ids = (
                    record.payment_mode_id.fixed_journal_id)
            elif record.payment_mode_id.bank_account_link == 'variable':
                record.allowed_journal_ids = (
                    record.payment_mode_id.variable_journal_ids)

    @api.multi
    def unlink(self):
        for order in self:
            if order.state in ('uploaded', 'done'):
                raise UserError(_(
                    "You cannot delete an uploaded payment order. You can "
                    "cancel it in order to do so."))
        return super(AccountPaymentOrder, self).unlink()

    @api.multi
    @api.constrains('payment_type', 'payment_mode_id')
    def payment_order_constraints(self):
        for order in self:
            if (
                    order.payment_mode_id.payment_type and
                    order.payment_mode_id.payment_type != order.payment_type):
                raise ValidationError(_(
                    "The payment type (%s) is not the same as the payment "
                    "type of the payment mode (%s)") % (
                        order.payment_type,
                        order.payment_mode_id.payment_type))

    @api.multi
    @api.constrains('date_scheduled')
    def check_date_scheduled(self):
        today = fields.Date.context_today(self)
        for order in self:
            if order.date_scheduled:
                if order.date_scheduled < today:
                    raise ValidationError(_(
                        "On payment order %s, the Payment Execution Date "
                        "is in the past (%s).")
                        % (order.name, order.date_scheduled))

    @api.multi
    @api.depends(
        'payment_line_ids', 'payment_line_ids.amount_company_currency')
    def _compute_total(self):
        for rec in self:
            rec.total_company_currency = sum(
                rec.mapped('payment_line_ids.amount_company_currency') or
                [0.0])

    @api.multi
    @api.depends('bank_line_ids')
    def _compute_bank_line_count(self):
        for order in self:
            order.bank_line_count = len(order.bank_line_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'account.payment.order') or 'New'
        if vals.get('payment_mode_id'):
            payment_mode = self.env['account.payment.mode'].browse(
                vals['payment_mode_id'])
            vals['payment_type'] = payment_mode.payment_type
            if payment_mode.bank_account_link == 'fixed':
                vals['journal_id'] = payment_mode.fixed_journal_id.id
            if (
                    not vals.get('date_prefered') and
                    payment_mode.default_date_prefered):
                vals['date_prefered'] = payment_mode.default_date_prefered
        return super(AccountPaymentOrder, self).create(vals)

    @api.onchange('payment_mode_id')
    def payment_mode_id_change(self):
        if len(self.allowed_journal_ids) == 1:
            self.journal_id = self.allowed_journal_ids
        if self.payment_mode_id.default_date_prefered:
            self.date_prefered = self.payment_mode_id.default_date_prefered

    @api.multi
    def action_done(self):
        self.write({
            'date_done': fields.Date.context_today(self),
            'state': 'done',
            })
        return True

    @api.multi
    def action_done_cancel(self):
        for move in self.move_ids:
            move.button_cancel()
            for move_line in move.line_ids:
                move_line.remove_move_reconcile()
            move.unlink()
        self.action_cancel()
        return True

    @api.multi
    def cancel2draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def action_cancel(self):
        for order in self:
            order.write({'state': 'cancel'})
            order.bank_line_ids.unlink()
        return True

    @api.model
    def _prepare_bank_payment_line(self, paylines):
        return {
            'order_id': paylines[0].order_id.id,
            'payment_line_ids': [(6, 0, paylines.ids)],
            'communication': '-'.join(
                [line.communication for line in paylines]),
            }

    @api.multi
    def draft2open(self):
        """
        Called when you click on the 'Confirm' button
        Set the 'date' on payment line depending on the 'date_prefered'
        setting of the payment.order
        Re-generate the bank payment lines
        """
        bplo = self.env['bank.payment.line']
        today = fields.Date.context_today(self)
        for order in self:
            if not order.journal_id:
                raise UserError(_(
                    'Missing Bank Journal on payment order %s.') % order.name)
            if (
                    order.payment_method_id.bank_account_required and
                    not order.journal_id.bank_account_id):
                raise UserError(_(
                    "Missing bank account on bank journal '%s'.")
                    % order.journal_id.display_name)
            if not order.payment_line_ids:
                raise UserError(_(
                    'There are no transactions on payment order %s.')
                    % order.name)
            # Delete existing bank payment lines
            order.bank_line_ids.unlink()
            # Create the bank payment lines from the payment lines
            group_paylines = {}  # key = hashcode
            for payline in order.payment_line_ids:
                payline.draft2open_payment_line_check()
                # Compute requested payment date
                if order.date_prefered == 'due':
                    requested_date = payline.ml_maturity_date or today
                elif order.date_prefered == 'fixed':
                    requested_date = order.date_scheduled or today
                else:
                    requested_date = today
                # No payment date in the past
                if requested_date < today:
                    requested_date = today
                # inbound: check option no_debit_before_maturity
                if (
                        order.payment_type == 'inbound' and
                        order.payment_mode_id.no_debit_before_maturity and
                        payline.ml_maturity_date and
                        requested_date < payline.ml_maturity_date):
                    raise UserError(_(
                        "The payment mode '%s' has the option "
                        "'Disallow Debit Before Maturity Date'. The "
                        "payment line %s has a maturity date %s "
                        "which is after the computed payment date %s.") % (
                            order.payment_mode_id.name,
                            payline.name,
                            payline.ml_maturity_date,
                            requested_date))
                # Write requested_date on 'date' field of payment line
                # norecompute is for avoiding a chained recomputation
                # payment_line_ids.date
                # > payment_line_ids.amount_company_currency
                # > total_company_currency
                with self.env.norecompute():
                    payline.date = requested_date
                # Group options
                if order.payment_mode_id.group_lines:
                    hashcode = payline.payment_line_hashcode()
                else:
                    # Use line ID as hascode, which actually means no grouping
                    hashcode = payline.id
                if hashcode in group_paylines:
                    group_paylines[hashcode]['paylines'] += payline
                    group_paylines[hashcode]['total'] +=\
                        payline.amount_currency
                else:
                    group_paylines[hashcode] = {
                        'paylines': payline,
                        'total': payline.amount_currency,
                    }
            order.recompute()
            # Create bank payment lines
            for paydict in list(group_paylines.values()):
                # Block if a bank payment line is <= 0
                if paydict['total'] <= 0:
                    raise UserError(_(
                        "The amount for Partner '%s' is negative "
                        "or null (%.2f) !")
                        % (paydict['paylines'][0].partner_id.name,
                           paydict['total']))
                vals = self._prepare_bank_payment_line(paydict['paylines'])
                bplo.create(vals)
        self.write({'state': 'open'})
        return True

    @api.multi
    def generate_payment_file(self):
        """Returns (payment file as string, filename)"""
        self.ensure_one()
        if self.payment_method_id.code == 'manual':
            return (False, False)
        else:
            raise UserError(_(
                "No handler for this payment method. Maybe you haven't "
                "installed the related Odoo module."))

    @api.multi
    def open2generated(self):
        self.ensure_one()
        payment_file_str, filename = self.generate_payment_file()
        action = {}
        if payment_file_str and filename:
            attachment = self.env['ir.attachment'].create({
                'res_model': 'account.payment.order',
                'res_id': self.id,
                'name': filename,
                'datas': base64.b64encode(payment_file_str),
                'datas_fname': filename,
                })
            simplified_form_view = self.env.ref(
                'account_payment_order.view_attachment_simplified_form')
            action = {
                'name': _('Payment File'),
                'view_mode': 'form',
                'view_id': simplified_form_view.id,
                'res_model': 'ir.attachment',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': attachment.id,
                }
        self.write({
            'date_generated': fields.Date.context_today(self),
            'state': 'generated',
            'generated_user_id': self._uid,
            })
        return action

    @api.multi
    def generated2uploaded(self):
        self.write({
            'state': 'uploaded',
            'date_uploaded': fields.Date.context_today(self),
            })
        for order in self:
            if order.payment_mode_id.generate_move:
                order.generate_move()
        return True

    @api.multi
    def _prepare_move(self, bank_lines=None):
        if self.payment_type == 'outbound':
            ref = _('Payment order %s') % self.name
        else:
            ref = _('Debit order %s') % self.name
        if bank_lines and len(bank_lines) == 1:
            ref += " - " + bank_lines.name
        if self.payment_mode_id.offsetting_account == 'bank_account':
            journal_id = self.journal_id.id
        elif self.payment_mode_id.offsetting_account == 'transfer_account':
            journal_id = self.payment_mode_id.transfer_journal_id.id
        vals = {
            'journal_id': journal_id,
            'ref': ref,
            'payment_order_id': self.id,
            'line_ids': [],
            }
        total_company_currency = total_payment_currency = 0
        for bline in bank_lines:
            total_company_currency += bline.amount_company_currency
            total_payment_currency += bline.amount_currency
            partner_ml_vals = self._prepare_move_line_partner_account(bline)
            vals['line_ids'].append((0, 0, partner_ml_vals))
        trf_ml_vals = self._prepare_move_line_offsetting_account(
            total_company_currency, total_payment_currency, bank_lines)
        vals['line_ids'].append((0, 0, trf_ml_vals))
        return vals

    @api.multi
    def _prepare_move_line_offsetting_account(
            self, amount_company_currency, amount_payment_currency,
            bank_lines):
        vals = {}
        if self.payment_type == 'outbound':
            name = _('Payment order %s') % self.name
        else:
            name = _('Debit order %s') % self.name
        if self.payment_mode_id.offsetting_account == 'bank_account':
            vals.update({'date': bank_lines[0].date})
        else:
            vals.update({'date_maturity': bank_lines[0].date})

        if self.payment_mode_id.offsetting_account == 'bank_account':
            account_id = self.journal_id.default_debit_account_id.id
        elif self.payment_mode_id.offsetting_account == 'transfer_account':
            account_id = self.payment_mode_id.transfer_account_id.id
        partner_id = False
        for index, bank_line in enumerate(bank_lines):
            if index == 0:
                partner_id = bank_line.payment_line_ids[0].partner_id.id
            elif bank_line.payment_line_ids[0].partner_id.id != partner_id:
                # we have different partners in the grouped move
                partner_id = False
                break
        vals.update({
            'name': name,
            'partner_id': partner_id,
            'account_id': account_id,
            'credit': (self.payment_type == 'outbound' and
                       amount_company_currency or 0.0),
            'debit': (self.payment_type == 'inbound' and
                      amount_company_currency or 0.0),
        })
        if bank_lines[0].currency_id != bank_lines[0].company_currency_id:
            sign = self.payment_type == 'outbound' and -1 or 1
            vals.update({
                'currency_id': bank_lines[0].currency_id.id,
                'amount_currency': amount_payment_currency * sign,
                })
        return vals

    @api.multi
    def _prepare_move_line_partner_account(self, bank_line):
        if bank_line.payment_line_ids[0].move_line_id:
            account_id =\
                bank_line.payment_line_ids[0].move_line_id.account_id.id
        else:
            if self.payment_type == 'inbound':
                account_id =\
                    bank_line.partner_id.property_account_receivable_id.id
            else:
                account_id =\
                    bank_line.partner_id.property_account_payable_id.id
        if self.payment_type == 'outbound':
            name = _('Payment bank line %s') % bank_line.name
        else:
            name = _('Debit bank line %s') % bank_line.name
        vals = {
            'name': name,
            'bank_payment_line_id': bank_line.id,
            'partner_id': bank_line.partner_id.id,
            'account_id': account_id,
            'credit': (self.payment_type == 'inbound' and
                       bank_line.amount_company_currency or 0.0),
            'debit': (self.payment_type == 'outbound' and
                      bank_line.amount_company_currency or 0.0),
            }

        if bank_line.currency_id != bank_line.company_currency_id:
            sign = self.payment_type == 'inbound' and -1 or 1
            vals.update({
                'currency_id': bank_line.currency_id.id,
                'amount_currency': bank_line.amount_currency * sign,
                })
        return vals

    @api.multi
    def _create_reconcile_move(self, hashcode, blines):
        self.ensure_one()
        post_move = self.payment_mode_id.post_move
        am_obj = self.env['account.move']
        mvals = self._prepare_move(blines)
        move = am_obj.create(mvals)
        blines.reconcile_payment_lines()
        if post_move:
            move.post()

    @api.multi
    def _prepare_trf_moves(self):
        """
        prepare a dict "trfmoves" that can be used when
        self.payment_mode_id.move_option = date or line
        key = unique identifier (date or True or line.id)
        value = bank_pay_lines (recordset that can have several entries)
        """
        self.ensure_one()
        trfmoves = {}
        for bline in self.bank_line_ids:
            hashcode = bline.move_line_offsetting_account_hashcode()
            if hashcode in trfmoves:
                trfmoves[hashcode] += bline
            else:
                trfmoves[hashcode] = bline
        return trfmoves

    @api.multi
    def generate_move(self):
        """
        Create the moves that pay off the move lines from
        the payment/debit order.
        """
        self.ensure_one()
        trfmoves = self._prepare_trf_moves()
        for hashcode, blines in trfmoves.items():
            self._create_reconcile_move(hashcode, blines)

    @api.multi
    def _all_lines_reconciled(self):
        """
        Return true if all payment lines' counterpart lines are reconciled too
        Also return true if the counterpart account cannot be reconciled
        """
        self.ensure_one()
        move_lines = self.env['account.move.line'].search([(
            'bank_payment_line_id', 'in', self.mapped('bank_line_ids').ids
        )]).mapped('move_id.line_ids')
        return bool(move_lines) and all(
            move_line.reconciled for move_line in move_lines
            if move_line.account_id.reconcile
        )
