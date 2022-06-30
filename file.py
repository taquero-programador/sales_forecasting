# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub
from frappe.utils import add_to_date, add_days, add_years, cint, flt, formatdate, getdate

import erpnext
#from erpnext.accounts.report.financial_statements import get_period_list
#from valsa.selling_reports.utils import get_period_list
from erpnext.stock.doctype.warehouse.warehouse import get_child_warehouses
from six import iteritems
from erpnext.accounts.utils import get_fiscal_year



def execute(filters=None):
	return Forecasting(filters).run()


class ExponentialSmoothingForecast(object):
	def forecast_future_data(self):
		for key, value in self.period_wise_data.items():
			forecast_data = []
			for period in self.period_list:
				forecast_key = "forecast_" + period.key

				if value.get(period.key) and not forecast_data:
					value[forecast_key] = flt(value.get("avg", 0)) or flt(value.get(period.key))

				elif forecast_data:
					previous_period_data = forecast_data[-1]
					value[forecast_key] = previous_period_data[1] + flt(self.filters.smoothing_constant) * (
						flt(previous_period_data[0]) - flt(previous_period_data[1])
					)

				if value.get(forecast_key):
					# will be use to forecaset next period
					forecast_data.append([value.get(period.key), value.get(forecast_key)])

class Forecasting(ExponentialSmoothingForecast):
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.date_field = 'transaction_date' \
			if self.filters.based_on_document in ['Sales Order', 'Purchase Order'] else 'posting_date'
		self.months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

		self.fieldtype = "Float" if self.filters.based_on_field == "Quantity" else "Currency"
		self.company_currency = erpnext.get_company_currency(self.filters.company)

	def run(self):
		self.prepare_periodical_data()
		self.get_columns()
		self.get_data()
		self.get_chart_data()

		# Skipping total row for tree-view reports
		skip_total_row = 0

		if self.filters.tree_type in ["Supplier Group", "Item Group", "Customer Group", "Territory", "Sales Person"]:
			skip_total_row = 1

		if self.filters.tree_type == "Customer Group" and self.filters.get("customer_group",None):
			skip_total_row = 0

		return self.columns, self.data, None, self.chart, None, skip_total_row

		#summary_data = self.get_summary_data()

		#return columns, self.data, None, charts, summary_data


	def prepare_periodical_data(self):
		self.period_wise_data = {}
		self.get_period_date_ranges()
		self.get_data_for_forecast()


	def prepare_final_data(self):
		self.data = []

		if not self.period_wise_data:
			return

		for key in self.period_wise_data:
			self.data.append(self.period_wise_data.get(key))

	def add_total(self):
		if not self.data:
			return

		total_row = {"item_code": _(frappe.bold("Total Quantity"))}

		for value in self.data:
			for period in self.period_list:
				forecast_key = "forecast_" + period.key
				if forecast_key not in total_row:
					total_row.setdefault(forecast_key, 0.0)

				if period.key not in total_row:
					total_row.setdefault(period.key, 0.0)

				total_row[forecast_key] += value.get(forecast_key, 0.0)
				total_row[period.key] += value.get(period.key, 0.0)

		self.data.append(total_row)

	def get_columns(self):
		self.columns = [{
				"label": _("Item Code") if self.filters.tree_type in ["Customer Group","Customer"] and (self.filters.get("customer_group",None) or self.filters.get("customer",None)) else _(self.filters.tree_type + " ID"),
				"options": self.filters.tree_type if self.filters.tree_type != "Order Type" else "",
				"fieldname": "entity",
				"fieldtype": "Link" if self.filters.tree_type != "Order Type" else "Data",
				"width": 140 if self.filters.tree_type != "Order Type" else 200
			}]
		if self.filters.tree_type in ["Customer", "Supplier", "Item"] or (self.filters.tree_type == "Customer Group" and self.filters.get("customer_group",None)):
			self.columns.append({
				"label":  _("Item Name") if self.filters.tree_type in ["Customer Group","Customer"] and (self.filters.get("customer_group",None) or self.filters.get("customer",None)) else _(self.filters.tree_type + " Name"),
				"fieldname": "entity_name",
				"fieldtype": "Data",
				"width": 140
			})

		if self.filters.tree_type == "Item":
			self.columns.append({
				"label": _("UOM"),
				"fieldname": 'stock_uom',
				"fieldtype": "Link",
				"options": "UOM",
				"width": 100
			})

		for end_date in self.periodic_daterange:
			period = self.get_period(end_date)
			self.columns.append({
				"label": _(period),
				"fieldname": scrub(period),
				"fieldtype": self.fieldtype,
				"width": 150
			})

		last_period = None
		for end_date in self.periodic_daterange:
			period = self.get_period(end_date)
			if not last_period:
				last_period = period
				continue

			period_name = "{0}_{1}".format(period,last_period)

			self.columns.append({
				"label": _(period) + "-" + _(last_period),
				"fieldname": scrub(period_name),
				"fieldtype": "Percent",
				"width": 100
			})
			last_period = period

		for end_date in self.periodic_daterange:
			period = self.get_period(end_date)
			period_name = "{0}_projected".format(period)
			sufix = _("Forecast")
			if self.filters.method == "deflation":
				sufix = _("Deflated")
 
			self.columns.append({
				"label": _(period) + " (" + sufix + ")",
				"fieldname": scrub(period_name),
				"fieldtype": self.fieldtype,
				"width": 150
			})

		last_period = None
		for end_date in self.periodic_daterange:
			period = self.get_period(end_date)
			if not last_period:
				last_period = period
				continue

			period_name = "{0}_{1}_projected".format(period,last_period)
			sufix = _("Forecast")
			if self.filters.method == "deflation":
				sufix = _("Deflated")

			self.columns.append({
				"label": _(period) + "-" + _(last_period) + " (" + sufix + ")",
				"fieldname": scrub(period_name),
				"fieldtype": "Percent",
				"width": 100
			})
			last_period = period


	def get_data(self):
		if self.filters.tree_type in ["Customer", "Supplier"]:
			if self.filters.customer:
				self.get_sales_transactions_based_on_items()
				self.get_rows()
			else:
				self.get_sales_transactions_based_on_customers_or_suppliers()
				self.get_rows()

		elif self.filters.tree_type == 'Item':
			self.get_sales_transactions_based_on_items()
			self.get_rows()

		elif self.filters.tree_type in ["Customer Group", "Supplier Group", "Territory", "Sales Person"]:
			if self.filters.customer_group:
				self.get_sales_transactions_based_on_items()
				self.get_rows()
			else:
				self.get_sales_transactions_based_on_customer_or_territory_group()
				self.get_rows_by_group()

		elif self.filters.tree_type == 'Item Group':
			self.get_sales_transactions_based_on_item_group()
			self.get_rows_by_group()

		elif self.filters.tree_type == "Order Type":
			if self.filters.based_on_document != "Sales Order":
				self.data = []
				return
			self.get_sales_transactions_based_on_order_type()
			self.get_rows_by_group()

	def get_sales_transactions_based_on_order_type(self):
		if self.filters["based_on_field"] == 'Value':
			value_field = "base_net_total"
		else:
			value_field = "total_qty"

		self.entries = frappe.db.sql(""" select s.order_type as entity, s.{value_field} as value_field, s.{date_field}
			from `tab{doctype}` s where s.docstatus = 1 and s.company = %s and s.{date_field} between %s and %s
			and ifnull(s.order_type, '') != '' order by s.order_type
		"""
		.format(date_field=self.date_field, value_field=value_field, doctype=self.filters.based_on_document),
		(self.filters.company, self.filters.from_date, self.filters.to_date), as_dict=1)

		self.get_teams()

	def get_sales_transactions_based_on_customers_or_suppliers(self):
		if self.filters["based_on_field"] == 'Value':
			value_field = "base_net_total as value_field"
		else:
			value_field = "total_qty as value_field"

		if self.filters.tree_type == 'Customer':
			entity = "customer as entity"
			entity_name = "customer_name as entity_name"
		else:
			entity = "supplier as entity"
			entity_name = "supplier_name as entity_name"

		self.entity_names = {}
		for d in self.entries:
			self.entity_names.setdefault(d.entity, d.entity_name)

	def get_sales_transactions_based_on_items(self):

		self.entity_names = {}
		for d in self.entries:
			self.entity_names.setdefault(d.entity, d.entity_name)

	def get_sales_transactions_based_on_customer_or_territory_group(self):
		if self.filters["based_on_field"] == 'Value':
			value_field = "SUM(si.base_amount) as value_field"
		else:
			value_field = "SUM(si.stock_qty) as value_field"

		if self.filters.tree_type == 'Customer Group':
			entity_field = 'c.customer_group as entity'
		elif self.filters.tree_type == 'Supplier Group':
			entity_field = "supplier as entity"
			self.get_supplier_parent_child_map()
		elif self.filters.tree_type == 'Sales Person':
			entity_field = 'c.sales_agent as entity'
		else:
			entity_field = "territory as entity"

		filters = {
			"docstatus": 1,
			"company": self.filters.company,
			self.date_field: ('between', [self.filters.from_date, self.filters.to_date])
		}

		self.get_groups()

	def get_sales_transactions_based_on_item_group(self):

		self.get_groups()


	def get_data_for_forecast(self):
		if self.filters["based_on_field"] == 'Value':
			value_field = "SUM(si.base_net_amount)"
		else:
			if self.filters.based_on_document == 'Sales Invoice':
				#value_field = 'SUM(IF(IFNULL(s.is_return,0) = 1 AND IFNULL(s.return_reason,"") NOT IN ("Devolución","Refacturación"), 0, si.stock_qty))'
				value_field = 'SUM(IF(IFNULL(s.is_return,0) = 1 AND IFNULL(s.return_reason,"") NOT IN ("Devolución","Refacturación"), 0, si.stock_qty))'
			else:
				value_field = 'SUM(si.stock_qty)'

		entity_name = ""

		if self.filters.tree_type == 'Customer Group':
			entity_field = 'c.customer_group'
			if self.filters.customer_group:
				entity_field = 'si.item_code'
				entity_name = "i.item_name AS entity_name,"
		elif self.filters.tree_type == 'Supplier Group':
			entity_field = "supplier"
			self.get_supplier_parent_child_map()
		elif self.filters.tree_type == 'Item Group':
			entity_field = "i.item_group"
		elif self.filters.tree_type == 'Sales Person':
			entity_field = 'c.sales_agent'
		elif self.filters.tree_type == 'Item':
			entity_field = 'si.item_code'
			entity_name = "i.item_name AS entity_name,"
		elif self.filters.tree_type == 'Customer':
			entity_field = "c.name"
			entity_name = "c.customer_name AS entity_name,"
			if self.filters.customer:
				entity_field = 'si.item_code'
				entity_name = "i.item_name AS entity_name,"
		else:
			entity_field = "c.territory"

		filters = {
			"docstatus": 1,
			"company": self.filters.company,
			#self.date_field: ('between', [self.filters.from_date, self.filters.to_date])
		}

		additional_filters = ""
		qty_field = "SUM(si.stock_qty)"
		if self.filters.based_on_document == 'Sales Invoice':
			additional_filters += ' AND IFNULL(s.return_reason,"") NOT IN ("Acuerdo efectivo")'
			qty_field = 'SUM(IF(IFNULL(s.is_return,0) = 1 AND IFNULL(s.return_reason,"") NOT IN ("Devolución"), 0, si.stock_qty))'

		if self.filters.get("customer_group",None):
			lft,rgt = frappe.get_value("Customer Group",self.filters.get("customer_group",None),['lft','rgt'])
			additional_filters += " AND s.customer IN (SELECT name from `tabCustomer` WHERE customer_group IN (SELECT name from `tabCustomer Group` where lft>={0} and rgt<={1}))".format(lft,rgt)

		if self.filters.get("customer",None):
			additional_filters += " AND s.customer = '{0}'".format(self.filters.get("customer",None))


		date_field_filters = " OR ".join([ "s.{0} BETWEEN '{1}' AND '{2}'".format("{date_field}",d.from_date,d.to_date) for d in self.period_list])
		date_field_filters = date_field_filters.format(date_field=self.date_field)


		reference_rate_query = "FIRST_VALUE(AVG(NULLIF(IF(si.stock_qty <= 0,0,si.base_net_rate),0))) OVER (PARTITION BY s.customer,si.item_code ORDER BY s.{date_field}) AS reference_rate".format(date_field = self.date_field)
		
		if self.filters.reference_value == "latest":
			reference_rate_query = "FIRST_VALUE(AVG(NULLIF(IF(si.stock_qty <= 0,0,si.base_net_rate),0))) OVER (PARTITION BY s.customer,si.item_code ORDER BY s.{date_field} DESC) AS reference_rate".format(date_field = self.date_field)

		self.entries = frappe.db.sql("""
			WITH cte AS (
			SELECT 
				{entity_field} AS entity,
				{value_field} AS value_field,
				{entity_name}
				s.{date_field},
				s.customer,
				c.sales_agent,
				c.customer_group,
				c.territory,
				si.item_code,
				i.item_group,
				i.stock_uom,
				YEAR(s.{date_field}) AS y,
				MONTH(s.{date_field}) AS m,
				WEEK(s.{date_field}) AS w,
				{qty_field} AS qty,
				SUM(si.base_net_amount) AS amount,
				MIN(si.base_net_rate) AS min_rate,
				MAX(si.base_net_rate) AS max_rate,
				AVG(NULLIF(IF(si.stock_qty <= 0,0,si.base_net_rate),0)) AS avg_rate,
				{reference_rate_query}
			FROM
				`tab{doctype} Item` si
					LEFT JOIN
				`tab{doctype}` s ON (si.parent = s.name)
					LEFT JOIN
				`tabCustomer` c ON (s.customer = c.name)
					LEFT JOIN
				`tabItem` i ON (si.item_code = i.name)
			WHERE
				s.docstatus = 1
					AND s.company = %(company)s
					AND ({date_field_filters}) {additional_filters}
			GROUP BY s.customer , si.item_code , y, m, w
			)
			SELECT 
				*,
				qty * reference_rate AS projected,
				IFNULL((avg_rate - reference_rate) / avg_rate,0) * 100 AS percent
			FROM
				cte
		"""
		.format(
			entity_field = entity_field,
			date_field = self.date_field,
			value_field = value_field,
			doctype = self.filters.based_on_document,
			date_field_filters = date_field_filters,
			additional_filters = additional_filters,
			qty_field = qty_field,
			entity_name = entity_name,
			reference_rate_query = reference_rate_query 
		),
		filters, as_dict=1)


	def get_rows(self):
		self.data = []
		self.get_periodic_data()

		for entity, period_data in iteritems(self.entity_periodic_data):
			row = {
				"entity": entity,
				"entity_name": self.entity_names.get(entity)
			}
			total = 0
			total_projected = 0

			for end_date in self.periodic_daterange:
				period = self.get_period(end_date)
				fperiod = "{0}_projected".format(period)
				
				amount = flt(period_data.get(period, 0.0))
				pamount = flt(period_data.get(fperiod, 0.0))

				row[scrub(period)] = amount
				row[scrub(fperiod)] = pamount

				total += amount
				total_projected += pamount

			row["total"] = total
			row["total_projected"] = total_projected

			if self.filters.tree_type == "Item":
				row["stock_uom"] = period_data.get("stock_uom")

			self.data.append(row)

	def get_rows_by_group(self):
		self.get_periodic_data()
		out = []

		for d in reversed(self.group_entries):
			row = {
				"entity": d.name,
				"indent": self.depth_map.get(d.name)
			}
			total = 0
			total_projected = 0
			last_period = None
			last_fperiod = None
			last_period_value = 0
			for end_date in self.periodic_daterange:
				period = self.get_period(end_date)
				fperiod = "{0}_projected".format(period)
				if last_period:
					pperiod = '{0}-{1}'.format(period,last_period)
					pfperiod = '{0}-{1}_projected'.format(period,last_period)
					
				amount = flt(self.entity_periodic_data.get(d.name, {}).get(period, 0.0))
				pamount = flt(self.entity_periodic_data.get(d.name, {}).get(fperiod, 0.0))
				row[scrub(period)] = amount
				row[scrub(fperiod)] = pamount
				if last_period:
					row[scrub(pperiod)] = flt((row[scrub(period)] - row[scrub(last_period)]) / abs(row[scrub(last_period)]) * 100,1) if row[scrub(last_period)] else 0
					row[scrub(pfperiod)] = flt((row[scrub(fperiod)] - row[scrub(last_fperiod)]) / abs(row[scrub(last_fperiod)]) * 100,1) if row[scrub(last_fperiod)] else 0

				if d.parent and (self.filters.tree_type != "Order Type" or d.parent == "Order Types"):
					self.entity_periodic_data.setdefault(d.parent, frappe._dict()).setdefault(period, 0.0)
					self.entity_periodic_data[d.parent][period] += amount
					self.entity_periodic_data.setdefault(d.parent, frappe._dict()).setdefault(fperiod, 0.0)
					self.entity_periodic_data[d.parent][fperiod] += pamount
					if last_period:
						self.entity_periodic_data.setdefault(d.parent, frappe._dict()).setdefault(pperiod, 0.0)
						self.entity_periodic_data[d.parent][pperiod] = flt((self.entity_periodic_data[d.parent][period] - self.entity_periodic_data[d.parent][last_period]) / abs(self.entity_periodic_data[d.parent][last_period]) * 100,1)if self.entity_periodic_data[d.parent][last_period] else 0
						self.entity_periodic_data.setdefault(d.parent, frappe._dict()).setdefault(pfperiod, 0.0)
						self.entity_periodic_data[d.parent][pfperiod] = flt((self.entity_periodic_data[d.parent][fperiod] - self.entity_periodic_data[d.parent][last_fperiod]) / abs(self.entity_periodic_data[d.parent][last_fperiod]) * 100,1)if self.entity_periodic_data[d.parent][last_fperiod] else 0

				total += amount
				total_projected += pamount
				last_period = period
				last_fperiod = fperiod

			row["total"] = total
			row["total_projected"] = total_projected
			out = [row] + out

		self.data = out

	def get_periodic_data(self):
		self.entity_periodic_data = frappe._dict()

		for d in self.entries:
			if self.filters.tree_type == "Supplier Group":
				d.entity = self.parent_child_map.get(d.entity)
			period = self.get_period(d.get(self.date_field))
			self.entity_periodic_data.setdefault(d.entity, frappe._dict()).setdefault(period, 0.0)
			self.entity_periodic_data.setdefault(d.entity, frappe._dict()).setdefault("{0}_projected".format(period), 0.0)
			self.entity_periodic_data[d.entity][period] += flt(d.value_field)
			self.entity_periodic_data[d.entity]["{0}_projected".format(period)] += flt(d.projected)

			if self.filters.tree_type == "Item":
				self.entity_periodic_data[d.entity]['stock_uom'] = d.stock_uom

	def get_period(self, posting_date):
		if self.filters.periodicity == 'Weekly':
			period = "Week " + str(posting_date.isocalendar()[1]) + " " + str(posting_date.year)
		elif self.filters.periodicity == 'Monthly':
			period = str(self.months[posting_date.month - 1]) + " " + str(posting_date.year)
		elif self.filters.periodicity == 'Quarterly':
			period = "Quarter " + str(((posting_date.month - 1) // 3) + 1) + " " + str(posting_date.year)
		else:
			year = get_fiscal_year(posting_date, company=self.filters.company)
			period = str(year[0])
		return period

	def get_label(periodicity, from_date, to_date):
		if periodicity == "Yearly":
			if formatdate(from_date, "YYYY") == formatdate(to_date, "YYYY"):
				label = formatdate(from_date, "YYYY")
			else:
				label = formatdate(from_date, "YYYY") + "-" + formatdate(to_date, "YYYY")
		else:
			label = formatdate(from_date, "MMM YY") + "-" + formatdate(to_date, "MMM YY")

		return label


	def get_period_date_ranges(self):
		from dateutil.relativedelta import relativedelta, MO
		self.periodic_daterange = []
		self.period_list = []

		fdate = add_years(getdate(self.filters.from_date), cint(self.filters.no_of_years) * -1)
		tdate = getdate(self.filters.to_date)
		for year in range(fdate.year, tdate.year + 1):
			self.period_list.append(frappe._dict(
				from_date = fdate.replace(year=year),
				to_date = tdate.replace(year=year),
				key = str(year),
			))

		for period in self.period_list:
			from_date, to_date = getdate(period.from_date), getdate(period.to_date)
			increment = {
				"Monthly": 1,
				"Quarterly": 3,
				"Half-Yearly": 6,
				"Yearly": 12
			}.get(self.filters.periodicity, 1)

			if self.filters.periodicity in ['Monthly', 'Quarterly']:
				from_date = getdate(from_date).replace(day=1)
			elif self.filters.periodicity == "Yearly":
				from_date = get_fiscal_year(from_date)[1]
			else:
				from_date = getdate(from_date) + relativedelta(from_date, weekday=MO(-1))

			for dummy in range(1, 53):
				if self.filters.periodicity == "Weekly":
					period_end_date = add_days(from_date, 6)
				else:
					period_end_date = add_to_date(from_date, months=increment, days=-1)

				if period_end_date > to_date:
					period_end_date = to_date

				self.periodic_daterange.append(period_end_date)

				from_date = add_days(period_end_date, 1)
				if period_end_date == to_date:
					break

	def get_groups(self):
		if self.filters.tree_type == "Territory":
			parent = 'parent_territory'
		if self.filters.tree_type == "Customer Group":
			parent = 'parent_customer_group'
		if self.filters.tree_type == "Item Group":
			parent = 'parent_item_group'
		if self.filters.tree_type == "Supplier Group":
			parent = 'parent_supplier_group'
		if self.filters.tree_type == "Sales Person":
			parent = 'parent_sales_person'

		self.depth_map = frappe._dict()

		self.group_entries = frappe.db.sql("""select name, lft, rgt , {parent} as parent
			from `tab{tree}` order by lft"""
		.format(tree=self.filters.tree_type, parent=parent), as_dict=1)

		for d in self.group_entries:
			if d.parent:
				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
			else:
				self.depth_map.setdefault(d.name, 0)

	def get_teams(self):
		self.depth_map = frappe._dict()

		self.group_entries = frappe.db.sql(""" select * from (select "Order Types" as name, 0 as lft,
			2 as rgt, '' as parent union select distinct order_type as name, 1 as lft, 1 as rgt, "Order Types" as parent
			from `tab{doctype}` where ifnull(order_type, '') != '') as b order by lft, name
		"""
		.format(doctype=self.filters.based_on_document), as_dict=1)

		for d in self.group_entries:
			if d.parent:
				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
			else:
				self.depth_map.setdefault(d.name, 0)

	def get_supplier_parent_child_map(self):
		self.parent_child_map = frappe._dict(frappe.db.sql(""" select name, supplier_group from `tabSupplier`"""))

	def get_chart_data(self):
		length = len(self.columns)
		last = cint((length - 1) /2)

		if self.filters.tree_type in ["Customer", "Supplier"]:
			last = cint((length - 2) /2)
			labels = [d.get("label") for d in self.columns[2:last + 2] if d.get("fieldtype") != "Percent"]
		elif self.filters.tree_type == "Item":
			last = cint((length - 3) /2)
			labels = [d.get("label") for d in self.columns[3:last + 3] if d.get("fieldtype") != "Percent"]
		else:
			labels = [d.get("label") for d in self.columns[1:last + 1] if d.get("fieldtype") != "Percent"]

		

		self.chart = {
			"data": {
				'labels': labels,
				'datasets': [
				]
			},
			"type": "line"
		}

		self.chart2 = {
			"data": {
				"labels": ["12am-3am", "3am-6am", "6am-9am", "9am-12pm","12pm-3pm", "3pm-6pm", "6pm-9pm", "9pm-12am"],
				"datasets": [
					{
						"name": "Some Data",
						"chartType": 'line',
						"values": [25, 40, 30, 35, 8, 52, 17, -4]
					},
					{
						"name": "Another Set",
						"chartType": 'line',
						"values": [25, 50, -10, 15, 18, 32, 27, 14]
					},
					{
						"name": "Yet Another",
						"chartType": 'line',
						"values": [15, 20, -3, -15, 58, 12, -17, 37]
					}
				],

				"yMarkers": [{
					"label": "Marker",
					"value": 40,
					"options": { "labelPos": 'left' }
				}],

				"yRegions": [{
					"label": "Region",
					"start": -10,
					"end": 50,
					"options": { "labelPos": 'right' }
				}],
			},
			"title": "My Awesome Chart",
			"type": 'axis-mixed', # // or 'bar', 'line', 'pie', 'percentage'
			"height": 600,
			"colors": ['purple', '#ffa3ef', 'light-blue'],
			
			"tooltipOptions": {
			#	"formatTooltipX": "d => (d + '').toUpperCase()",
			#	"formatTooltipY": "d => d + ' pts'"
			}
		}

	def get_summary_data(self):
		if not self.data:
			return

		return [
			{
				"value": sum(self.total_demand),
				"label": _("Total Demand (Past Data)"),
				"currency": self.company_currency,
				"datatype": self.fieldtype,
			},
			{
				"value": sum(self.total_history_forecast),
				"label": _("Total Forecast (Past Data)"),
				"currency": self.company_currency,
				"datatype": self.fieldtype,
			},
			{
				"value": sum(self.total_future_forecast),
				"indicator": "Green",
				"label": _("Total Forecast (Future Data)"),
				"currency": self.company_currency,
				"datatype": self.fieldtype,
			},
		]
