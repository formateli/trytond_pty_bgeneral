# This file is part of pty_bgeneral module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import bank
from . import ach_batch


def register():
    Pool.register(
        bank.Bank,
        bank.Account,
        ach_batch.AchBatch,
        ach_batch.AchBatchLine,
        ach_batch.AchBatchLog,
        module='pty_bgeneral', type_='model')
    Pool.register(
        ach_batch.CreateAchFileReport,
        module='pty_bgeneral', type_='report')
