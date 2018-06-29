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
from openerp.osv import  osv
import time
from openerp import workflow


class account_invoice(models.Model):
    _inherit="account.invoice"

    @api.multi
    def test_paid(self):
        # check whether all corresponding account move lines are reconciled
        line_ids = self.move_line_id_payment_get()
        for line in self.env['account.move.line'].search([('id','in',tuple(line_ids))]) :
            voucher_line=self.env['account.voucher.line'].search([('move_line_id','=',line.id)])
            if voucher_line :
                voucher_line=voucher_line[0]
                journal_id=voucher_line.voucher_id.journal_id
                if not voucher_line.voucher_id.is_paid and (journal_id.is_check or journal_id.is_boe) :
                    return False
        if not line_ids:
            return False
        query = "SELECT reconcile_id FROM account_move_line WHERE id IN %s"
        self._cr.execute(query, (tuple(line_ids),))
        return all(row[0] for row in self._cr.fetchall())


class account_journal(models.Model):

    _inherit="account.journal"

    is_check = fields.Boolean(string="Journal chèques en portefeuille?")
    is_bank = fields.Boolean(string="Journal banque?")
    is_boe = fields.Boolean(string="Journal des effets?")
    is_operation=fields.Boolean(string="Journal des opérations diverses?")

class account_voucher(models.Model):

    _inherit="account.voucher"

    is_paid = fields.Boolean(string="Encaissé")
    check_end_date = fields.Date(string='Date d\'échéance du chèque')
    boe_end_date = fields.Date(string='Date d\'échéance de l\'effet')
    journal_type = fields.Selection(related='journal_id.type', store=True)
    collecting_date = fields.Date(string="Date d\'encaissement")
    collecting_bank = fields.Many2one("account.journal","Banque d\'encaissement")
    collecting_description = fields.Char(string="Libellé d\'encaissement")
    check_journal = fields.Boolean(related='journal_id.is_check', store=True)
    boe_journal = fields.Boolean(related='journal_id.is_boe', store=True)

    state = fields.Selection(
            [('draft','Draft'),
             ('cancel','Cancelled'),
             ('proforma','Pro-forma'),
             ('posted','Posted'),
             ('collected','Encaissé')
            ], 'Status', readonly=True, track_visibility='onchange', copy=False,
            help=' * The \'Draft\' status is used when a user is encoding a new and unconfirmed Voucher. \
                        \n* The \'Pro-forma\' when voucher is in Pro-forma status,voucher does not have an voucher number. \
                        \n* The \'Posted\' status is used when user create voucher,a voucher number is generated and voucher entries are created in account \
                        \n* The \'Collected\' status is used when user create voucher with boe journal or check journal. \
                        \n* The \'Cancelled\' status is used when user cancel voucher.')

    # AB: Action pour lancer le wizard d'encaissement
    def action_encashment(self,cr,uid,ids,context=None):
        context['voucher_id']=ids
        #voucher.journal_id.
        voucher=self.browse(cr,uid,ids)
        account_id = False
        if voucher.type in ('receipt'):
            account_id = voucher.partner_id.property_account_receivable.id
            line_ids =[]
            for x in voucher.line_cr_ids:
                if x.reconcile:
                    line_ids.append(x.move_line_id.id)
        if voucher.type in ('payment'):
            account_id = voucher.partner_id.property_account_payable.id
            line_ids =[]
            for x in voucher.line_dr_ids:
                if x.reconcile:
                    line_ids.append(x.move_line_id.id)

        context['account_id']=account_id
        if line_ids.__len__() > 0:
            context['line_ids']= line_ids

        #print"id(s) selected before opening wizard ==========================================>",line_ids

        return {
                'name':_("Constat d'encaissement"),
                 'view_mode': 'form',
                 'view_id': False,
                 'view_type': 'form',
                 'res_model': 'subscription.payment',
                 'res_id':False,
                 'type': 'ir.actions.act_window',
                 'nodestroy': True,
                 'context':context,
                 'target': 'new',
              }

    # AB : heritage pour empêcher le lettrage auto 127..130
    def action_move_line_create(self, cr, uid, ids, context=None):
        '''
        Confirm the vouchers given in ids and create the journal entries for each of them
        '''
        if context is None:
            context = {}
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')

        for voucher in self.browse(cr, uid, ids, context=context):
            local_context = dict(context, force_company=voucher.journal_id.company_id.id)
            if voucher.move_id:
                continue
            company_currency = self._get_company_currency(cr, uid, voucher.id, context)
            current_currency = self._get_current_currency(cr, uid, voucher.id, context)
            # we select the context to use accordingly if it's a multicurrency case or not
            context = self._sel_context(cr, uid, voucher.id, context)
            # But for the operations made by _convert_amount, we always need to give the date in the context
            ctx = context.copy()
            ctx.update({'date': voucher.date})
            # Create the account move record.
            move_id = move_pool.create(cr, uid, self.account_move_get(cr, uid, voucher.id, context=context), context=context)
            #print"account move id ================> ", move_id
            # Get the name of the account_move just created
            name = move_pool.browse(cr, uid, move_id, context=context).name
           # print"account name =============> ", name
            # Create the first line of the voucher
            move_line_id = move_line_pool.create(cr, uid, self.first_move_line_get(cr,uid,voucher.id, move_id, company_currency, current_currency, local_context), local_context)
            #print "move_line_id =====================>", move_line_id

            move_line_brw = move_line_pool.browse(cr, uid, move_line_id, context=context)
            #print "move_line_brw =====================>",move_line_brw
            line_total = move_line_brw.debit - move_line_brw.credit
            #print "line_total =====================>",line_total
            rec_list_ids = []
            if voucher.type == 'sale':
                line_total = line_total - self._convert_amount(cr, uid, voucher.tax_amount, voucher.id, context=ctx)
                print "line_total 1=====================>",line_total
            elif voucher.type == 'purchase':
                line_total = line_total + self._convert_amount(cr, uid, voucher.tax_amount, voucher.id, context=ctx)
                print "line_total 2=====================>",line_total
            # Create one move line per voucher line where amount is not 0.0
            line_total, rec_list_ids = self.voucher_move_line_create(cr, uid, voucher.id, line_total, move_id, company_currency, current_currency, context)

            # Create the writeoff line if needed
            ml_writeoff = self.writeoff_move_line_get(cr, uid, voucher.id, line_total, move_id, name, company_currency, current_currency, local_context)
            if ml_writeoff:
                 print "ml_writeoff =====================>", move_line_pool.create(cr, uid, ml_writeoff, local_context)

            # We post the voucher.
            if not (voucher.journal_id.is_check or voucher.journal_id.is_boe):
                self.write(cr, uid, [voucher.id], {
                    'move_id': move_id,
                    'state': 'collected',
                    'number': name
                })
            else:
                self.write(cr, uid, [voucher.id], {
                    'move_id': move_id,
                    'state': 'posted',
                    'number': name
                })
            if voucher.journal_id.entry_posted:
                move_pool.post(cr, uid, [move_id], context={})

            # We automatically reconcile the account move lines.
            reconcile = False
            # print"reconcile ======> ",reconcile
            # print"rec_list_ids ======================== ",rec_list_ids
            # print "val : ",rec_list_ids[0]
            # print "val : ",rec_list_ids[0][0]
            if not (voucher.journal_id.is_check or voucher.journal_id.is_boe):
                for rec_ids in rec_list_ids:
                    if len(rec_ids) >= 2:
                        # print" cr      ========> ",cr
                        # print" uid      ========> ",uid
                        # print" writeoff_acc_id   ========> ",voucher.writeoff_acc_id.id
                        # print" writeoff_period_id  ========> ", voucher.period_id.id
                        # print" writeoff_journal_id ========> ",voucher.journal_id.id
                        # print" rec_ids ========> ",rec_ids
                        reconcile = move_line_pool.reconcile_partial(cr, uid, rec_ids,
                                                                     writeoff_acc_id=voucher.writeoff_acc_id.id,
                                                                     writeoff_period_id=voucher.period_id.id,
                                                                     writeoff_journal_id=voucher.journal_id.id)
               # print"reconcile ======> ",reconcile
        return True

    #AB : Héritage 189..197 : pour empêcher de supprimer les lignes de paiement si on modifie la methode (journal_id)
    def recompute_voucher_lines(self, cr, uid, ids, partner_id, journal_id, price, currency_id, ttype, date, context=None):
        """
        Returns a dict that contains new values and context

        @param partner_id: latest value from user input for field partner_id
        @param args: other arguments
        @param context: context arguments, like lang, time zone

        @return: Returns a dict which contains new values, and context
        """
        def _remove_noise_in_o2m():
            """if the line is partially reconciled, then we must pay attention to display it only once and
                in the good o2m.
                This function returns True if the line is considered as noise and should not be displayed
            """
            if line.reconcile_partial_id:
                if currency_id == line.currency_id.id:
                    if line.amount_residual_currency <= 0:
                        return True
                else:
                    if line.amount_residual <= 0:
                        return True
            return False

        if context is None:
            context = {}
        context_multi_currency = context.copy()

        currency_pool = self.pool.get('res.currency')
        move_line_pool = self.pool.get('account.move.line')
        partner_pool = self.pool.get('res.partner')
        journal_pool = self.pool.get('account.journal')
        line_pool = self.pool.get('account.voucher.line')

        #set default values
        default = {
            'value': {'line_dr_ids': [], 'line_cr_ids': [], 'pre_line': False},
        }

        # drop existing lines
        line_ids = ids and line_pool.search(cr, uid, [('voucher_id', '=', ids[0])])
        partner = partner_pool.browse(cr, uid, partner_id, context=context)
        journal = journal_pool.browse(cr, uid, journal_id, context=context)
        #code standard modifié pour empêcher de supprimer les lignes de paiement si on modifie la methode (journal_id)
        #By abdellatif benzbiria
        #start
        receivable_bill_account=partner.receivable_bill_account
        portfolio_check_account=partner.portfolio_check_account
        payable_bill_account=partner.payable_bill_account
        remitted_check_account=partner.remitted_check_account
        account_id=False

        if partner.customer == True:
            if journal.is_check :
                account_id=portfolio_check_account

            if journal.is_boe :
                account_id=receivable_bill_account


        if partner.supplier == True:
            if journal.is_check :
                account_id=remitted_check_account

            if journal.is_boe :
                account_id=payable_bill_account


        for line in line_pool.browse(cr, uid, line_ids, context=context):

            if line.type == 'cr':
                if journal.is_check or journal.is_boe :
                     default['value']['line_cr_ids'].append((2, line.id,{'account_id':account_id}))
                else :
                    default['value']['line_cr_ids'].append((2, line.id))
            else:
                 if journal.is_check or journal.is_boe :
                     default['value']['line_dr_ids'].append((2, line.id,{'account_id':account_id}))
                 else :
                     default['value']['line_dr_ids'].append((2, line.id))

        ### fin code
        if not partner_id or not journal_id:
            return default
        currency_id = currency_id or journal.company_id.currency_id.id

        total_credit = 0.0
        total_debit = 0.0
        account_type = None
        if context.get('account_id'):
            account_type = self.pool['account.account'].browse(cr, uid, context['account_id'], context=context).type
        if ttype == 'payment':
            if not account_type:
                account_type = 'payable'
            total_debit = price or 0.0
        else:
            total_credit = price or 0.0
            if not account_type:
                account_type = 'receivable'

        if not context.get('move_line_ids', False):
            ids = move_line_pool.search(cr, uid, [('state','=','valid'), ('account_id.type', '=', account_type), ('reconcile_id', '=', False), ('partner_id', '=', partner_id)], context=context)
        else:
            ids = context['move_line_ids']
        invoice_id = context.get('invoice_id', False)
        company_currency = journal.company_id.currency_id.id
        move_lines_found = []

        #order the lines by most old first
        ids.reverse()
        account_move_lines = move_line_pool.browse(cr, uid, ids, context=context)

        #compute the total debit/credit and look for a matching open amount or invoice
        for line in account_move_lines:
            if _remove_noise_in_o2m():
                continue

            if invoice_id:
                if line.invoice.id == invoice_id:
                    #if the invoice linked to the voucher line is equal to the invoice_id in context
                    #then we assign the amount on that line, whatever the other voucher lines
                    move_lines_found.append(line.id)
            elif currency_id == company_currency:
                #otherwise treatments is the same but with other field names
                if line.amount_residual == price:
                    #if the amount residual is equal the amount voucher, we assign it to that voucher
                    #line, whatever the other voucher lines
                    move_lines_found.append(line.id)
                    break
                #otherwise we will split the voucher amount on each line (by most old first)
                total_credit += line.credit or 0.0
                total_debit += line.debit or 0.0
            elif currency_id == line.currency_id.id:
                if line.amount_residual_currency == price:
                    move_lines_found.append(line.id)
                    break
                total_credit += line.credit and line.amount_currency or 0.0
                total_debit += line.debit and line.amount_currency or 0.0

        remaining_amount = price
        #voucher line creation
        for line in account_move_lines:

            if _remove_noise_in_o2m():
                continue

            if line.currency_id and currency_id == line.currency_id.id:
                amount_original = abs(line.amount_currency)
                amount_unreconciled = abs(line.amount_residual_currency)
            else:
                #always use the amount booked in the company currency as the basis of the conversion into the voucher currency
                amount_original = currency_pool.compute(cr, uid, company_currency, currency_id, line.credit or line.debit or 0.0, context=context_multi_currency)
                amount_unreconciled = currency_pool.compute(cr, uid, company_currency, currency_id, abs(line.amount_residual), context=context_multi_currency)
            line_currency_id = line.currency_id and line.currency_id.id or company_currency
            rs = {
                'name':line.move_id.name,
                'type': line.credit and 'dr' or 'cr',
                'move_line_id':line.id,
                'account_id':account_id or line.account_id.id,#AB : ajout du compte selon le type du journal
                'amount_original': amount_original,
                'amount': (line.id in move_lines_found) and min(abs(remaining_amount), amount_unreconciled) or 0.0,
                'date_original':line.date,
                'date_due':line.date_maturity,
                'amount_unreconciled': amount_unreconciled,
                'currency_id': line_currency_id,
            }
            remaining_amount -= rs['amount']
            #in case a corresponding move_line hasn't been found, we now try to assign the voucher amount
            #on existing invoices: we split voucher amount by most old first, but only for lines in the same currency
            if not move_lines_found:
                if currency_id == line_currency_id:
                    if line.credit:
                        amount = min(amount_unreconciled, abs(total_debit))
                        rs['amount'] = amount
                        total_debit -= amount
                    else:
                        amount = min(amount_unreconciled, abs(total_credit))
                        rs['amount'] = amount
                        total_credit -= amount

            if rs['amount_unreconciled'] == rs['amount']:
                rs['reconcile'] = True

            if rs['type'] == 'cr':
                default['value']['line_cr_ids'].append(rs)
            else:
                default['value']['line_dr_ids'].append(rs)

            if len(default['value']['line_cr_ids']) > 0:
                default['value']['pre_line'] = 1
            elif len(default['value']['line_dr_ids']) > 0:
                default['value']['pre_line'] = 1
            default['value']['writeoff_amount'] = self._compute_writeoff_amount(cr, uid, default['value']['line_dr_ids'], default['value']['line_cr_ids'], price, ttype)
        return default

class account_move_line(models.Model):
    _inherit = "account.move.line"
    # _columns = {
    #     'reconcile_with': fields.char('reconcile_with', help="Indicate lines to reconcile in the account move line table")
    #     }

    # AB : heritage ligne 363 pour éviter de stoper le paiement s'il s'agit un compte effet ou cheque
    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None):
        print "AAAAAAAAAAAAAA",ids
        #raise osv.except_osv("recosile",ids)
        account_obj = self.pool.get('account.account')
        move_obj = self.pool.get('account.move')
        move_rec_obj = self.pool.get('account.move.reconcile')
        partner_obj = self.pool.get('res.partner')
        currency_obj = self.pool.get('res.currency')
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        credit = debit = 0.0
        currency = 0.0
        account_id = False
        partner_id = False
        if context is None:
            context = {}
        company_list = []
        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning!'), _('To reconcile the entries company should be the same for all entries.'))
            company_list.append(line.company_id.id)
        for line in unrec_lines:
            if line.state <> 'valid':
                raise osv.except_osv(_('Error!'),
                        _('Entry "%s" is not valid !') % line.name)
            credit += line['credit']
            debit += line['debit']
            currency += line['amount_currency'] or 0.0
            account_id = line['account_id']['id']
            partner_id = (line['partner_id'] and line['partner_id']['id']) or False
        writeoff = debit - credit

        # Ifdate_p in context => take this date
        if context.has_key('date_p') and context['date_p']:
            date=context['date_p']
        else:
            date = time.strftime('%Y-%m-%d')

        print "gggggggggggggggggggggg",ids,tuple(ids)
        cr.execute("SELECT account_id, reconcile_id FROM account_move_line WHERE id IN %s GROUP BY account_id,reconcile_id ;",(tuple(ids),) )
        r = cr.fetchall()
        journal_id=self.pool.get("account.journal").search(cr,uid,[('id','=',writeoff_journal_id)])
        journal=self.pool.get("account.journal").browse(cr,uid,journal_id)
        #TODO: move this check to a constraint in the account_move_reconcile object
        if len(r) != 1 and not ( journal.is_check  or journal.is_boe) : #AB : éviter de stoper le paiement s'il s'agit un commpte effet ou cheque
            raise osv.except_osv(_('Error'), _('Entries are not of the same account or already reconciled ! '))
        if not unrec_lines:
            raise osv.except_osv(_('Error!'), _('Entry is already reconciled.'))
        account = account_obj.browse(cr, uid, account_id, context=context)
        if not account.reconcile:
            raise osv.except_osv(_('Error'), _('The account is not defined to be reconciled !'))
        if r[0][1] != None:
            raise osv.except_osv(_('Error!'), _('Some entries are already reconciled.'))

        if (not currency_obj.is_zero(cr, uid, account.company_id.currency_id, writeoff)) or \
           (account.currency_id and (not currency_obj.is_zero(cr, uid, account.currency_id, currency))):
            if not writeoff_acc_id:
                raise osv.except_osv(_('Warning!'), _('You have to provide an account for the write off/exchange difference entry.'))
            if writeoff > 0:
                debit = writeoff
                credit = 0.0
                self_credit = writeoff
                self_debit = 0.0
            else:
                debit = 0.0
                credit = -writeoff
                self_credit = 0.0
                self_debit = -writeoff
            # If comment exist in context, take it
            if 'comment' in context and context['comment']:
                libelle = context['comment']
            else:
                libelle = _('Write-Off')

            cur_obj = self.pool.get('res.currency')
            cur_id = False
            amount_currency_writeoff = 0.0
            if context.get('company_currency_id',False) != context.get('currency_id',False):
                cur_id = context.get('currency_id',False)
                for line in unrec_lines:
                    if line.currency_id and line.currency_id.id == context.get('currency_id',False):
                        amount_currency_writeoff += line.amount_currency
                    else:
                        tmp_amount = cur_obj.compute(cr, uid, line.account_id.company_id.currency_id.id, context.get('currency_id',False), abs(line.debit-line.credit), context={'date': line.date})
                        amount_currency_writeoff += (line.debit > 0) and tmp_amount or -tmp_amount

            writeoff_lines = [
                (0, 0, {
                    'name': libelle,
                    'debit': self_debit,
                    'credit': self_credit,
                    'account_id': account_id,
                    'date': date,
                    'partner_id': partner_id,
                    'currency_id': cur_id or (account.currency_id.id or False),
                    'amount_currency': amount_currency_writeoff and -1 * amount_currency_writeoff or (account.currency_id.id and -1 * currency or 0.0)
                }),
                (0, 0, {
                    'name': libelle,
                    'debit': debit,
                    'credit': credit,
                    'account_id': writeoff_acc_id,
                    'analytic_account_id': context.get('analytic_id', False),
                    'date': date,
                    'partner_id': partner_id,
                    'currency_id': cur_id or (account.currency_id.id or False),
                    'amount_currency': amount_currency_writeoff and amount_currency_writeoff or (account.currency_id.id and currency or 0.0)
                })
            ]

            writeoff_move_id = move_obj.create(cr, uid, {
                'period_id': writeoff_period_id,
                'journal_id': writeoff_journal_id,
                'date':date,
                'state': 'draft',
                'line_id': writeoff_lines
            })

            writeoff_line_ids = self.search(cr, uid, [('move_id', '=', writeoff_move_id), ('account_id', '=', account_id)])
            if account_id == writeoff_acc_id:
                writeoff_line_ids = [writeoff_line_ids[1]]
            ids += writeoff_line_ids

        # marking the lines as reconciled does not change their validity, so there is no need
        # to revalidate their moves completely.
        reconcile_context = dict(context, novalidate=True)
        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_id': map(lambda x: (4, x, False), ids),
            'line_partial_ids': map(lambda x: (3, x, False), ids)
        }, context=reconcile_context)
        # the id of the move.reconcile is written in the move.line (self) by the create method above
        # because of the way the line_id are defined: (4, x, False)
        for id in ids:
            workflow.trg_trigger(uid, 'account.move.line', id, cr)

        if lines and lines[0]:
            partner_id = lines[0].partner_id and lines[0].partner_id.id or False
            if partner_id and not partner_obj.has_something_to_reconcile(cr, uid, partner_id, context=context):
                partner_obj.mark_as_reconciled(cr, uid, [partner_id], context=context)
        return r_id





