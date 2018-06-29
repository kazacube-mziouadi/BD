# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 - ABDELLATIF BENZBIRIA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _

class partner(models.Model):

    _inherit="res.partner"

    receivable_bill_account=fields.Many2one("account.account",company_dependent=True,domain="[('type', '=', 'receivable')]",string="Compte effets à recevoir", required=True ,copy=False )
    payable_bill_account=fields.Many2one("account.account",company_dependent=True, domain="[('type', '=', 'payable')]", string="Compte effets à payer", required=True ,copy=False )
    remitted_check_account=fields.Many2one("account.account",company_dependent=True, domain="[('type', '=', 'payable')]", string="Compte chèque en portefeuille", required=True,copy=False )
    portfolio_check_account=fields.Many2one("account.account",company_dependent=True, domain="[('type', '=', 'receivable')]", string="Compte chèque remis", required=True,copy=False )





