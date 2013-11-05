# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 ADN (<http://adn-france.com>).
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
##############################################################################

import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dateutil import parser
from dateutil import rrule
from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp import netsvc
from openerp import tools, SUPERUSER_ID
import re

months = {
    1: "January", 2: "February", 3: "March", 4: "April", \
    5: "May", 6: "June", 7: "July", 8: "August", 9: "September", \
    10: "October", 11: "November", 12: "December"
}

def get_recurrent_dates(rrulestring, exdate, startdate=None, exrule=None):
    """
    Get recurrent dates based on Rule string considering exdate and start date.
    @param rrulestring: rulestring
    @param exdate: list of exception dates for rrule
    @param startdate: startdate for computing recurrent dates
    @return: list of Recurrent dates
    """
    def todate(date):
        val = parser.parse(''.join((re.compile('\d')).findall(date)))
        return val

    if not startdate:
        startdate = datetime.now()

    if not exdate:
        exdate = []

    rset1 = rrule.rrulestr(str(rrulestring), dtstart=startdate, forceset=True)
    for date in exdate:
        datetime_obj = todate(date)
        rset1._exdate.append(datetime_obj)

    if exrule:
        rset1.exrule(rrule.rrulestr(str(exrule), dtstart=startdate))

    return list(rset1)

class account_analytic_account(osv.osv):
    _inherit = 'account.analytic.account'
    
    def _get_rulestring(self, cr, uid, ids, name, arg, context=None):
        """
        Gets Recurrence rule string according to value type RECUR of iCalendar from the values given.
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param id: List of calendar event's ids.
        @param context: A standard dictionary for contextual values
        @return: dictionary of rrule value.
        """

        result = {}
        if not isinstance(ids, list):
            ids = [ids]

        for id in ids:
            #read these fields as SUPERUSER because if the record is private a normal search could return False and raise an error
            data = self.read(cr, SUPERUSER_ID, id, ['interval', 'count'], context=context)
            if data.get('interval', 0) < 0:
                raise osv.except_osv(_('Warning!'), _('Interval cannot be negative.'))
            if data.get('count', 0) <= 0:
                raise osv.except_osv(_('Warning!'), _('Count cannot be negative or 0.'))
            data = self.read(cr, uid, id, ['id','byday','recurrency', 'month_list','end_date', 'rrule_type', 'select1', 'interval', 'count', 'end_type', 'mo', 'tu', 'we', 'th', 'fr', 'sa', 'su', 'exrule', 'day', 'week_list' ], context=context)
            event = data['id']
            if data['recurrency']:
                result[event] = self.compute_rule_string(data)
            else:
                result[event] = ""
        return result

    def _rrule_write(self, obj, cr, uid, ids, field_name, field_value, args, context=None):
        data = self._get_empty_rrule_data()
        if field_value:
            data['recurrency'] = True
            for event in self.browse(cr, uid, ids, context=context):
                rdate = rule_date or event.date
                update_data = self._parse_rrule(field_value, dict(data), rdate)
                data.update(update_data)
                super(calendar_event, obj).write(cr, uid, ids, data, context=context)
        return True
        
    def _get_amendment(self, cr, uid, ids, name, arg, context=None):
        result = {}
        if not isinstance(ids, list):
            ids = [ids]

        for id in ids:
            #read these fields as SUPERUSER because if the record is private a normal search could return False and raise an error
            data = self.read(cr, SUPERUSER_ID, id, ['amendment_ids'], context=context)
            print 'data',data
            result[id]=False
            if data.get('amendment_ids', False):
                for amendment in data['amendment_ids']:
                    print 'amendment',amendment
                    amend_data = self.pool.get('account.analytic.amendments').read(cr,uid,amendment,['state'],context=context)
                    print 'amedn_data',amend_data
                    if amend_data['state'] == 'draft':
                        result[id]=True
        return result
    
    def _get_amendment_search(self, cr, uid, obj, name, domain, context=None):
        res=[]
        ids=self.search(cr,uid,[],context=context)
        for contract in self.browse(cr,uid,ids,context=context):
            for amend in contract.amendment_ids:
                if amend.state=='draft':
                    res.append(contract.id)
        return [('id','in',res)]
    
    _columns = {
        'mro_order_ids': fields.one2many('mro.order','contract_id','Maintenance Orders'),
        'asset_ids': fields.one2many('account.analytic.assets','contract_id','Assets'),
        'service_ids': fields.one2many('account.analytic.services','contract_id','Contract services'),
        'amendment_ids': fields.one2many('account.analytic.amendments','contract_id','Contract services'),
        'amendment': fields.function(_get_amendment, fnct_search=_get_amendment_search, type='boolean', string='Amendment not accepted'),
        'date_today': fields.date('date_today'),
        'maintenance_date_start': fields.datetime('Maintenance date start'),
        'maintenance_date_end': fields.datetime('Maintenance date end'),
        'exdate': fields.text('Exception Date/Times', help="This property \
        defines the list of date/time exceptions for a recurring calendar component."),
        'exrule': fields.char('Exception Rule', size=352, help="Defines a \
        rule or repeating pattern of time to exclude from the recurring rule."),
        'rrule': fields.function(_get_rulestring, type='char', size=124, \
                    fnct_inv=_rrule_write, store=True, string='Recurrent Rule'),
        'rrule_type': fields.selection([
            ('daily', 'Day(s)'),
            ('weekly', 'Week(s)'),
            ('monthly', 'Month(s)'),
            ('yearly', 'Year(s)')
            ], 'Recurrency', states={'done': [('readonly', True)]},
            help="Let the event automatically repeat at that interval"),
        'end_type' : fields.selection([('count', 'Number of repetitions'), ('end_date','End date')], 'Recurrence Termination'),
        'interval': fields.integer('Repeat Every', help="Repeat every (Days/Week/Month/Year)"),
        'count': fields.integer('Repeat', help="Repeat x times"),
        'mo': fields.boolean('Mon'),
        'tu': fields.boolean('Tue'),
        'we': fields.boolean('Wed'),
        'th': fields.boolean('Thu'),
        'fr': fields.boolean('Fri'),
        'sa': fields.boolean('Sat'),
        'su': fields.boolean('Sun'),
        'select1': fields.selection([('date', 'Date of month'),
                                    ('day', 'Day of month')], 'Option'),
        'day': fields.integer('Date of month'),
        'week_list': fields.selection([
            ('MO', 'Monday'),
            ('TU', 'Tuesday'),
            ('WE', 'Wednesday'),
            ('TH', 'Thursday'),
            ('FR', 'Friday'),
            ('SA', 'Saturday'),
            ('SU', 'Sunday')], 'Weekday'),
        'byday': fields.selection([
            ('1', 'First'),
            ('2', 'Second'),
            ('3', 'Third'),
            ('4', 'Fourth'),
            ('5', 'Fifth'),
            ('-1', 'Last')], 'By day'),
        'month_list': fields.selection(months.items(), 'Month'),
        'end_date': fields.date('Repeat Until'),
        'recurrency': fields.boolean('Recurrency', help="Recurrency"),
        #~ 'state': fields.selection([('template', 'Template'),('draft','New'),('open','In Progress'),('pending','To Renew'),('close','Closed'),('cancelled', 'Cancelled')], 'Status', required=True, track_visibility='onchange'),
    }
    
    _defaults = {
        'state':'draft',
        'date': lambda *a: (datetime.strptime(time.strftime('%Y-%m-%d'),'%Y-%m-%d')+relativedelta(years=1)).strftime('%Y-%m-%d'),
        'end_date': lambda *a: (datetime.strptime(time.strftime('%Y-%m-%d'),'%Y-%m-%d')+relativedelta(years=1)).strftime('%Y-%m-%d'),
        'end_type': 'end_date',
        'count': 1,
        'rrule_type': False,
        'select1': 'date',
        'interval': 1,
    }
    
    def on_change_partner_id(self, cr, uid, ids,partner_id, name, context={}):
        res={}
        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
            if partner.user_id:
                res['manager_id'] = partner.user_id.id
            if not name:
                res['name'] = _('Contract: ') + partner.name
            res['asset_ids']=[]
            for asset in partner.asset_ids:
                if ids:
                    exist_ids=self.pool.get('account.analytic.assets').search(cr,uid,[('asset_id','=',asset.id),('contract_id','=',ids[0])])
                    if exist_ids:
                        self.pool.get('account.analytic.assets').unlink(cr,uid,exist_ids)
                res['asset_ids'].append(self.pool.get('account.analytic.assets').create(cr,uid,{'asset_id':asset.id}))
        return {'value': res}
        
    def on_change_end_date(self, cr, uid, ids,date, context={}):
        res={}
        if date:
            res['end_date']=date
        return {'value': res}
    
    def get_recurrency(self, cr, uid, ids, context=None):
        mro_obj = self.pool.get('mro.order')
        result=[]
        res={}
        contracts=self.browse(cr,uid,ids,context)
        #~ for data in self.read(cr, uid, ids, ['rrule', 'exdate', 'exrule', 'date_start'], context=context):
        for data in contracts:
            if not data.rrule:
                result.append(data.id)
                continue
            event_date = datetime.strptime(data.date_start, "%Y-%m-%d")

            # TOCHECK: the start date should be replaced by event date; the event date will be changed by that of calendar code

            if not data.rrule:
                continue

            exdate = data.exdate and data.exdate.split(',') or []
            rrule_str = data.rrule
            new_rrule_str = []
            rrule_until_date = False
            is_until = False
            for rule in rrule_str.split(';'):
                name, value = rule.split('=')
                if name == "UNTIL":
                    is_until = True
                    value = parser.parse(value)
                    rrule_until_date = parser.parse(value.strftime("%Y-%m-%d 00:00:00"))
                    value = value.strftime("%Y%m%d000000")
                new_rule = '%s=%s' % (name, value)
                new_rrule_str.append(new_rule)
            new_rrule_str = ';'.join(new_rrule_str)
            rdates = get_recurrent_dates(str(new_rrule_str), exdate, event_date, data.exrule)
            for r_date in rdates:
                print 'r_date.strftime("%Y-%m-%d %H:%M:%S")',r_date.strftime("%Y-%m-%d %H:%M:%S")
                vals = {
                    #~ 'origin': sale.name,
                    #~ 'order_id': sale.id,
                    'contract_id': data.id,
                    'partner_id': data.partner_id.id,
                    'description': '',
                    'origin': data.code,
                    'asset_ids': [(6,0,[x.asset_id.id for x in data.asset_ids])],
                    'maintenance_type': 'pm',
                    'date_planned': r_date.strftime("%Y-%m-%d %H:%M:%S"),
                    'date_scheduled': r_date.strftime("%Y-%m-%d %H:%M:%S"),
                    'date_execution': r_date.strftime("%Y-%m-%d %H:%M:%S"),
                    #~ 'duration': make.duration,
                }
                mro_obj.create(cr, uid, vals, context=context)
        return res
    
    def compute_rule_string(self, data):
        """
        Compute rule string according to value type RECUR of iCalendar from the values given.
        @param self: the object pointer
        @param data: dictionary of freq and interval value
        @return: string containing recurring rule (empty if no rule)
        """
        def get_week_string(freq, data):
            weekdays = ['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su']
            if freq == 'weekly':
                byday = map(lambda x: x.upper(), filter(lambda x: data.get(x) and x in weekdays, data))
                if byday:
                    return ';BYDAY=' + ','.join(byday)
            return ''

        def get_month_string(freq, data):
            if freq == 'monthly':
                if data.get('select1')=='date' and (data.get('day') < 1 or data.get('day') > 31):
                    raise osv.except_osv(_('Error!'), ("Please select a proper day of the month."))

                if data.get('select1')=='day':
                    return ';BYDAY=' + data.get('byday') + data.get('week_list')
                elif data.get('select1')=='date':
                    return ';BYMONTHDAY=' + str(data.get('day'))
            return ''

        def get_end_date(data):
            if data.get('end_date'):
                data['end_date_new'] = ''.join((re.compile('\d')).findall(data.get('end_date'))) + 'T235959Z'

            return (data.get('end_type') == 'count' and (';COUNT=' + str(data.get('count'))) or '') +\
                             ((data.get('end_date_new') and data.get('end_type') == 'end_date' and (';UNTIL=' + data.get('end_date_new'))) or '')

        freq = data.get('rrule_type', False)
        res = ''
        if freq:
            interval_srting = data.get('interval') and (';INTERVAL=' + str(data.get('interval'))) or ''
            res = 'FREQ=' + freq.upper() + get_week_string(freq, data) + interval_srting + get_end_date(data) + get_month_string(freq, data)

        return res
    
    def _get_empty_rrule_data(self):
        return  {
            'byday' : False,
            'recurrency' : False,
            'end_date' : False,
            'rrule_type' : False,
            'select1' : False,
            'interval' : 0,
            'count' : False,
            'end_type' : False,
            'mo' : False,
            'tu' : False,
            'we' : False,
            'th' : False,
            'fr' : False,
            'sa' : False,
            'su' : False,
            'exrule' : False,
            'day' : False,
            'week_list' : False
        }
    
    def _parse_rrule(self, rule, data, date_start):
        day_list = ['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su']
        rrule_type = ['yearly', 'monthly', 'weekly', 'daily']
        r = rrule.rrulestr(rule, dtstart=datetime.strptime(date_start, "%Y-%m-%d %H:%M:%S"))

        if r._freq > 0 and r._freq < 4:
            data['rrule_type'] = rrule_type[r._freq]

        data['count'] = r._count
        data['interval'] = r._interval
        data['end_date'] = r._until and r._until.strftime("%Y-%m-%d %H:%M:%S")
        #repeat weekly
        if r._byweekday:
            for i in xrange(0,7):
                if i in r._byweekday:
                    data[day_list[i]] = True
            data['rrule_type'] = 'weekly'
        #repeat monthly by nweekday ((weekday, weeknumber), )
        if r._bynweekday:
            data['week_list'] = day_list[r._bynweekday[0][0]].upper()
            data['byday'] = r._bynweekday[0][1]
            data['select1'] = 'day'
            data['rrule_type'] = 'monthly'

        if r._bymonthday:
            data['day'] = r._bymonthday[0]
            data['select1'] = 'date'
            data['rrule_type'] = 'monthly'

        #repeat yearly but for openerp it's monthly, take same information as monthly but interval is 12 times
        if r._bymonth:
            data['interval'] = data['interval'] * 12

        #FIXEME handle forever case
        #end of recurrence
        #in case of repeat for ever that we do not support right now
        if not (data.get('count') or data.get('end_date')):
            data['count'] = 100
        if data.get('count'):
            data['end_type'] = 'count'
        else:
            data['end_type'] = 'end_date'
        return data
    
class account_analytic_assets(osv.osv):
    _name = 'account.analytic.assets'
    _description = 'Contract Assets'
    
    
    _columns = {
        'name': fields.char('Description', size=128),
        'date_previous': fields.datetime('Previous maintenance date'),
        'date_next': fields.datetime('Next maintenance date',required=True),
        'asset_id': fields.many2one('product.product', 'Asset', required=True),
        'contract_id': fields.many2one('account.analytic.account', 'Contract', select=True),
    }
    
    _defaults = {
    }
    
    def onchange_asset(self, cr, uid, ids, product, context=None):
        context = context or {}
        result = {}
        product_obj = self.pool.get('product.product')
        product_obj = product_obj.browse(cr, uid, product, context=context)
        result['name'] = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context)[0][1]
        return {'value': result}
        
    
class account_analytic_services(osv.osv):
    _name = 'account.analytic.services'
    _description = 'Contract services'
    _columns = {
        'name': fields.char('Description', size=128),
        'price': fields.float('Price'),
        'service_id': fields.many2one('product.product', 'Contract service', required=True),
        'contract_id': fields.many2one('account.analytic.account', 'Contract', select=True),
    }
    
    _defaults = {
    }
    
    def onchange_service(self, cr, uid, ids, product, context=None):
        context = context or {}
        result = {}
        product_obj = self.pool.get('product.product')
        product_obj = product_obj.browse(cr, uid, product, context=context)
        result['name'] = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context)[0][1]
        return {'value': result}
        
class account_analytic_amendments(osv.osv):
    _name = 'account.analytic.amendments'
    _description = 'Contract amendments'
    _columns = {
        'name': fields.char('Description', size=128),
        'date': fields.date('Date'),
        'data': fields.binary('File'),
        'state': fields.selection([('draft','Draft'),('accepted','Accepted')],'Status'),
        'contract_id': fields.many2one('account.analytic.account', 'Contract', select=True),
    }
    
    _defaults = {
        'state': 'draft',
    }
    
    def button_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)
        
    def button_accepted(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'accepted'}, context=context)
        
    
