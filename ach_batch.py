# This file is part of pty_bgeneral module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.modules.currency.fields import Monetary
from trytond.modules.log_action import LogActionMixin, write_log
from trytond.modules.nuntiare.nuntiare_report import Nuntiare
from trytond.modules.nuntiare.data import Data


class AchBatch(Workflow, ModelSQL, ModelView):
    "ACH Batch"
    __name__ = "bank.bgeneral.ach"

    _states = {
        'readonly': Eval('state') != 'draft',
        }
    _depends = ['state']

    date = fields.Date('Date', required=True,
        states=_states, depends=_depends)
    reference = fields.Char('Reference', size=None)
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': True,
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': True,
        })
    description = fields.Char('Description', size=None,
        states=_states, depends=_depends)
    lines = fields.One2Many('bank.bgeneral.ach.line', 'ach',
        'Lines', states=_states,
        depends=_depends)
    total_amount = fields.Function(Monetary('Total',
        digits='currency', currency='currency'),
        'on_change_with_total_amount')
    total_count = fields.Function(fields.Integer('Count'),
        'on_change_with_total_count')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True, required=True)
    logs = fields.One2Many('bank.bgeneral.ach.log_action', 'resource',
        'Logs', readonly=True)

    del _states, _depends

    @classmethod
    def __setup__(cls):
        super(AchBatch, cls).__setup__()
        cls._order = [
                ('date', 'DESC'),
                ('id', 'DESC'),
                ]

        cls._transitions |= set(
            (
                ('draft', 'confirmed'),
                ('confirmed', 'cancel'),
                ('cancel', 'draft'),
            )
            )

        cls._buttons.update({
            'cancel': {
                'invisible': ~Eval('state').in_(['confirmed']),
                },
            'confirm': {
                'invisible': ~Eval('state').in_(['draft']),
                },
            'draft': {
                'invisible': ~Eval('state').in_(['cancel']),
                'icon': If(Eval('state') == 'cancel',
                    'tryton-clear', 'tryton-go-previous'),
                },
            'create_ach_file': {
                'invisible': ~Eval('state').in_(['confirmed']),
                },
            })

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.id

    @fields.depends('lines')
    def on_change_with_total_amount(self, name=None):
        if self.lines:
            res = 0
            for l in self.lines:
                if l.amount:
                    res += l.amount
            return res

    @fields.depends('lines')
    def on_change_with_total_count(self, name=None):
        if self.lines:
            return len(self.lines)

    @classmethod
    def delete(cls, achs):
        for ach in achs:
            if ach.state not in ['draft']:
                write_log('log_action.msg_deletion_attempt', [ach])
                raise UserError(
                    gettext('log_action.msg_delete_document_state_fail',
                        doc_name='Ach',
                        doc_number=ach.rec_name,
                        state='Draft'
                    ))
        super(AchBatch, cls).delete(achs)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, achs):
        write_log('log_action.msg_draft', achs)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, achs):
        write_log('log_action.msg_confirmed', achs)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, achs):
        write_log('log_action.msg_cancelled', achs)

    @classmethod
    @ModelView.button_action('pty_bgeneral.report_ach_file')
    def create_ach_file(cls, achs):
        pass


class AchBatchLine(ModelSQL, ModelView):
    'Ach Batch Line'
    __name__ = 'bank.bgeneral.ach.line'

    _states = {
        'readonly': Eval('ach_state') != 'draft',
        }
    _depends = ['ach_state']

    ach = fields.Many2One('bank.bgeneral.ach', 'Ach Batch',
        required=True, ondelete='CASCADE')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        required=True,
        states=_states, depends=_depends)
    party_id = fields.Function(fields.Integer('Party ID'),
        'on_change_with_party_id')
    party_accounts = fields.Function(fields.One2Many(
        'bank.account', None, 'Accounts'),
        'on_change_with_party_accounts',
        'set_party_accounts')
    bank_account = fields.Many2One('bank.account', 'Bank Account',
        ondelete='RESTRICT',
        domain=[
            ('id', 'in', Eval('party_accounts')),
            ('currency', '=', Eval('currency'))
        ],
        states={
            'readonly': Eval('ach_state') != 'draft',
            'required': True,
        }, depends=_depends + ['party_accounts'])
    bank_account_number = fields.Function(fields.Char('Account Number'),
        'on_change_with_bank_account_number')
    bank_account_type = fields.Function(fields.Char('Account Type'),
        'on_change_with_bank_account_type')
    bank_route = fields.Function(fields.Char('Bank Route'),
        'on_change_with_bank_route')
    amount = Monetary('Amount', required=True,
        digits='currency', currency='currency',
        states=_states, depends=_depends)
    description = fields.Char('Description', size=None,
        required=True,
        states=_states, depends=_depends)
    ach_state = fields.Function(
        fields.Selection('get_ach_states', 'Ach State'),
        'on_change_with_ach_state')

    del _states, _depends

    @fields.depends('ach', '_parent_ach.state')
    def on_change_with_ach_state(self, name=None):
        if self.ach:
            return self.ach.state

    @classmethod
    def get_ach_states(cls):
        pool = Pool()
        Ach = pool.get('bank.bgeneral.ach')
        return Ach.fields_get(['state'])['state']['selection']

    @fields.depends('ach', '_parent_ach.currency')
    def on_change_with_currency(self, name=None):
        if self.ach:
            return self.ach.currency.id

    @fields.depends('party')
    def on_change_with_party_id(self, name=None):
        if self.party:
            return self.party.id

    @fields.depends('bank_account')
    def on_change_with_bank_account_type(self, name=None):
        if self.bank_account:
            return self.bank_account.account_pty_type

    @fields.depends('bank_account')
    def on_change_with_bank_account_number(self, name=None):
        if self.bank_account:
            if self.bank_account.numbers:
                return self.bank_account.numbers[0].number

    @fields.depends('bank_account')
    def on_change_with_bank_route(self, name=None):
        if self.bank_account:
            return self.bank_account.bank.bgeneral_ruta

    @fields.depends('party')
    def on_change_with_party_accounts(self, name=None):
        if self.party:
            res = []
            for acc in self.party.bank_accounts:
                res.append(acc.id)
            return res

    @classmethod
    def set_party_accounts(cls, instances, name, value):
        pass


class AchBatchLog(LogActionMixin):
    "Ach Logs"
    __name__ = "bank.bgeneral.ach.log_action"
    resource = fields.Many2One('bank.bgeneral.ach',
        'Ach Batch', ondelete='CASCADE')


class CreateAchFileReport(Nuntiare):
    __name__ = 'bank.bgeneral.ach_file'

    @classmethod
    def execute(cls, ids, data):
        Ach = Pool().get('bank.bgeneral.ach')

        records = Data()
        records.add_fields([
            'id', 'name', 'route',
            'account', 'type', 'amount',
            'payment_type', 'description'
            ])

        domain = []
        if ids:
            domain = [('id', 'in', ids)]

        achs = Ach.search(domain)
        for ach in achs:
            for line in ach.lines:
                records.new_record()
                records.add_values({
                        'id': line.party.id,
                        'name': cls.validate_str(line.party.rec_name),
                        'route': line.bank_route,
                        'account': line.bank_account_number,
                        'type': line.bank_account_type,
                        'amount': "{:.2f}".format(line.amount),
                        'payment_type': 'C',
                        'description': 'REF*TXT**' + cls.validate_str(line.description)
                    })

        data['records_ach'] = records.get_records()

        data['output_type'] = 'csv'
        data['nuntiare_render_kws_separator'] = ','
        data['nuntiare_render_kws_delimeter'] = None

        return super(CreateAchFileReport, cls).execute(ids, data)

    @classmethod
    def validate_str(cls, value):
        value = value.replace(',', ' ')
        value = value.replace('.', ' ')
        value = value.replace(';', ' ')
        value = value.replace(':', ' ')
        value = value.replace('@', ' ')
        value = value.replace('-', ' ')
        value = value.replace('ñ', 'n')
        value = value.replace('Ñ', 'N')
        value = value.replace('(', ' ')
        value = value.replace(')', ' ')
        value = value.replace('.', ' ')
        value = value.replace('[', ' ')
        value = value.replace(']', ' ')
        value = value.replace('|', ' ')
        value = value.replace('á', 'a')
        value = value.replace('é', 'e')
        value = value.replace('í', 'i')
        value = value.replace('ó', 'o')
        value = value.replace('ú', 'u')

        return value


