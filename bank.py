# This file is part of pty_bgeneral module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

class Bank(metaclass=PoolMeta):
    __name__ = 'bank'

    bgeneral_ruta = fields.Char('Ruta / Transito')


class Account(metaclass=PoolMeta):
    __name__ = 'bank.account'

    account_pty_type = fields.Selection([
        ('04', 'Cuenta de Ahorros'),
        ('03', 'Cuenta Corriente'),
        ('07', 'Prestamo'),
        ], 'Account PTY Type',
        states={'required': True})
