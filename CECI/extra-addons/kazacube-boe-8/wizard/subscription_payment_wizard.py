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
import openerp
from openerp import models, fields, api, _
from openerp.osv import  osv
from openerp.exceptions import except_orm, Warning, RedirectWarning


class subscription_payment(models.TransientModel):

    _name="subscription.payment"

    receipt_date=fields.Date("Date d'encaissement",required=True)
    bank_id=fields.Many2one("account.journal","Banque",required=True)
    name=fields.Char("Libellé opération",required=True)

    @api.multi
    def action_done(self):
        voucher=self.env['account.voucher'].search([('id','=',self._context['voucher_id'][0]) ])
        #facture = self.env['account.invoice'].search([('number','=',voucher.line_dr_ids)])
        move_pool = self.env['account.move']
        move_line_pool = self.env['account.move.line']
        move_line_pool_v7=self.pool.get('account.move.line')
        seq_obj = self.env['ir.sequence']
        rec_list_ids=[]
        temp_list_ids = []
        #journal des OD
        journal_id=self.env['account.journal'].search([('is_operation','=',True)])

        if not journal_id:
                model, action_id = self.env['ir.model.data'].get_object_reference('account', 'action_account_journal_form')
                msg = _("Vous n'avez pas configuré un journal d'opérations diverses")
                raise openerp.exceptions.RedirectWarning(msg, action_id, _('Aller à la configuration des journaux comptables'))

        ctx = dict(self._context)
        ctx.update({'fiscalyear_id': voucher.period_id.fiscalyear_id.id})
        name = seq_obj.next_by_id(journal_id.sequence_id.id, context=ctx)
        if not voucher.reference:
            ref = name.replace('/','')
        else:
            ref = voucher.reference

        move = {
            'name': name,
            'journal_id': journal_id.id,
            #'narration': self.name,
            'date': self.receipt_date,
            'ref': ref,
            'period_id': voucher.period_id.id,
        }
        move_id = move_pool.create(move)
        move_line = {
                'journal_id': journal_id.id,
                'period_id': voucher.period_id.id,
                'name': self.name,
                'account_id': self._context['account_id'],
                'move_id': move_id.id,
                'partner_id': voucher.partner_id.id,
               # 'currency_id': voucher.currency_id.id,
                'quantity': 1,
                'credit': 0.0,
                'debit': 0.0,
                'date': self.receipt_date
            }

        account_partner=False
        if voucher.type =='receipt':
            move_line['credit'] = voucher.amount
            rec_id = move_line_pool.create(move_line)
            rec=move_line

           # print"   tuplet id JOD ============================>  ", rec_id.id
            temp_list_ids.append(rec_id.id)

            move_line['debit'] = voucher.amount
            move_line['credit'] = 0.0
            if voucher.journal_id.is_boe :
                account_partner=voucher.partner_id.receivable_bill_account.id
                print "journal BOE ",account_partner
            if voucher.journal_id.is_check :
                account_partner=voucher.partner_id.portfolio_check_account.id
                print"journal cheque ",account_partner

        if voucher.type=='payment':

            move_line['credit'] = 0.0
            move_line['debit'] = voucher.amount
            rec_id = move_line_pool.create(move_line)
            #print"   tuplet id JOD =================================>  ", rec_id.id
            temp_list_ids.append(rec_id.id)
            move_line['credit'] = voucher.amount
            move_line['debit'] = 0.0
            if voucher.journal_id.is_boe :
                account_partner=voucher.partner_id.payable_bill_account.id
            if voucher.journal_id.is_check :
                account_partner=voucher.partner_id.remitted_check_account.id

        if account_partner==False :
            raise except_orm("Il n'y pas de compte tiers pour encaisser le paiement , merci de vérifier le partenaire ou le journal du paiement",voucher.journal_id.name)
        move_line['account_id'] = account_partner
        print "move_line_credit",move_line
        move_line_pool.create(move_line)

        ######### bank account move ###############"
        move['journal_id']=self.bank_id.id
        name = seq_obj.next_by_id(journal_id.sequence_id.id, context=ctx)
        move['name']=name
        move_id = move_pool.create(move)
        move_line_bank = {
                'journal_id': self.bank_id.id,
                'period_id': voucher.period_id.id,
                'name': self.name,
                'account_id': voucher.journal_id.default_credit_account_id.id,
                'move_id': move_id.id,
                'partner_id': voucher.partner_id.id,
               # 'currency_id': voucher.currency_id.id,
                'quantity': 1,
                'credit': voucher.amount,
                'debit': 0.0,
                'date': self.receipt_date
            }
        if voucher.type=='receipt':
            move_line_pool.create(move_line_bank)
            move_line_bank['credit'] = 0.0
            move_line_bank['debit']=voucher.amount
            move_line_bank['account_id'] = self.bank_id.default_debit_account_id.id
            move_line_pool.create(move_line_bank)
        if voucher.type=='payment':
            move_line_bank['credit'] = 0.0
            move_line_bank['debit']=voucher.amount
            move_line_pool.create(move_line_bank)
            move_line_bank['credit'] = voucher.amount
            move_line_bank['debit']= 0.0
            move_line_bank['account_id'] = self.bank_id.default_debit_account_id.id
            move_line_pool.create(move_line_bank)

        voucher.write({'is_paid': True,
                       'collecting_date':self.receipt_date,
                       'collecting_bank':self.bank_id.id,
                       'collecting_description':self.name,
                       'state':'collected'
                       })

        for rec in self._context['line_ids']:
            temp_list_ids.append(rec)

        rec_list_ids.append(temp_list_ids)
        #print "rec_list_ids, rec_list_ids[0]====>",rec_list_ids,rec_list_ids[0]
        #for rec_ids in rec_list_ids:
            # if len(rec_ids) >= 2:
            #     print" self._cr      ========> ",self._cr
            #     print" self._uid      ========> ",self._uid
            #     print "rec_list_ids      ======> ",rec_ids
            #     print" writeoff_acc_id   ========> ",voucher.writeoff_acc_id.id
            #     print" writeoff_period_id  ========> ", voucher.period_id.id
            #     print" writeoff_journal_id ========> ",voucher.journal_id.id
            #     print" ========> ",

        move_line_pool_v7.reconcile(self._cr,self._uid,rec_list_ids[0])

        return False
subscription_payment ()
