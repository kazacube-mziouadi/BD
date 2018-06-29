# -*- coding: utf-8 -*-
#/#############################################################################
#
#
#    Copyright (C) 20015-TODAY KAZACUBE (<http://www.KAZACUBE.com>).
#    Author : ABDELLATOF BENZBIRIA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#/#############################################################################
{
    'name': 'Bill of exchange payment',
    'version': '0.2',
    'category': 'Accounting/Payment method',
    'description': """
        Allow to manage payment by bill of exchange and voucher
    """,
    'author': 'KAZACUBE',
    'website': 'www.kazacube.com',
    'depends': ["account"],
    'init_xml': [],
    'data': [ 'partner.xml',
              'account_journal.xml',
              'wizard/subscription_payment_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
