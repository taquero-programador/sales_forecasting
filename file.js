// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Forecasting"] = {
	"filters": [
		{
			fieldname: "tree_type",
			label: __("Tree Type"),
			fieldtype: "Select",
			options: ["Customer Group","Customer","Item Group","Item","Territory","Sales Person"],
			default: "Customer Group",
			reqd: 1,
			on_change: () => {
				/*let raw_data = frappe.query_report.chart.data;
        let new_datasets = raw_data.datasets;
				for(var i=0; i < new_datasets.length;i++){
					try {
						new_datasets.splice(i,1);
					} catch (error) {
						console.log(error);
					}
        }
				let new_data = {
          labels: raw_data.labels,
          datasets: new_datasets
        }
				frappe.query_report.raw_chart_data = new_data;
				try {
					frappe.query_report.chart.update(new_data);
				} catch (error) {
					console.log(error);
        } */
				frappe.query_report.refresh();
				frappe.query_reports['Sales Forecasting'].drilldown({});
			}
		},
		{
			fieldname: "based_on_document",
			label: __("based_on"),
			fieldtype: "Select",
			options: ["Sales Order","Delivery Note","Sales Invoice"],
			default: "Sales Invoice",
			reqd: 1
		},
		{
			fieldname: "based_on_field",
			label: __("Value Or Qty"),
			fieldtype: "Select",
			options: [
				{ "value": "Value", "label": __("Value") },
				{ "value": "Quantity", "label": __("Quantity") },
			],
			default: "Value",
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.defaults.get_user_default("year_start_date"),
			reqd: 1
		},
		{
			fieldname:"to_date",
			label: __("To Date"),
			fieldtype: "Date",
			//default: frappe.defaults.get_user_default("year_end_date"),
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldname: "periodicity",
			label: __("Range"),
			fieldtype: "Select",
			options: [
				{ "value": "Weekly", "label": __("Weekly") },
				{ "value": "Monthly", "label": __("Monthly") },
				{ "value": "Quarterly", "label": __("Quarterly") },
        { "value": "Half-Yearly", "label": __("Half-Yearly") },
        { "value": "Yearly", "label": __("Yearly") }
			],
			default: "Yearly",
			reqd: 1
		},
		{
      "fieldname":"no_of_years",
      "label": __("Based On Data ( in years )"),
      "fieldtype": "Select",
      "options": [1,2,3,4,5,6,7,8,9,10],
      "default": 3,
      "reqd": 1
    },
		{
      "fieldname":"method",
      "label": __("Method"),
      "fieldtype": "Select",
      "options": [{
				"value": "deflation",
				"label": __("Inflation Adjustment (Deflation)"),
			}],
      "default": "deflation",
      "reqd": 1
    },
		{
      "fieldname":"reference_value",
      "label": __("Reference Value"),
      "fieldtype": "Select",
      "options": [
				{
					"value": "oldest",
					"label": __("Oldest"),
				},
				{
          "value": "latest",
          "label": __("Latest"),
        }
			],
      "default": "latest",
      "reqd": 1
    },
		{
      "label": __("Customer Group"),
      "fieldname": "customer_group",
      "fieldtype": "Link",
      "options": "Customer Group",
      "default": "",
      "width": 300,
      "read_only": 1,
      on_change: function() {
          let customer_group = frappe.query_report.get_filter_value('customer_group');

          frappe.query_report.refresh();
      }
    },
		{
      "label": __("Customer"),
      "fieldname": "customer",
      "fieldtype": "Link",
      "options": "Customer",
      "default": "",
      "width": 300,
      "read_only": 1,
      on_change: function() {
          let customer = frappe.query_report.get_filter_value('customer');

          frappe.query_report.refresh();
      }
    },
    {
      "label": __("Back"),
      "fieldname": "back",
      "fieldtype": "Button",
      "onclick": function() { frappe.query_reports['Sales Forecasting'].drilldown({});}
    }
	],
	"formatter": function(value, row, column, data, default_formatter) {
		if (data && column.fieldname == "entity" && column.options=="Customer Group") {
			value = data.entity || value;
      column.link_onclick =
      "frappe.query_reports['Sales Forecasting'].drilldown(" + JSON.stringify({'by':'customer_group','value':value}) + ")";
      column.is_tree = false;
    }
    if (data && column.fieldname=="entity" && column.options=="Customer") {
			value = data.entity || value;
      column.link_onclick =
      "frappe.query_reports['Sales Forecasting'].drilldown(" + JSON.stringify({'by':'customer','value':value}) + ")";
      column.is_tree = false;
    }

    value = default_formatter(value, row, column, data);

    if (["Currency","Int","Percent"].includes(column.fieldtype) && data && data[column.fieldname] < 0) {
			$value = $(`${value}`);
      $value.addClass("text-danger");
      value = $value.wrap("<span></span>").parent().html();
    }

    return value;
  },
	onload: function(report) {
      let customer_group = frappe.query_report.get_filter_value('customer_group');
			let customer = frappe.query_report.get_filter_value('customer');
      if (!customer_group && !customer) {
				frappe.query_report.toggle_filter_display('customer_group', true);
				frappe.query_report.toggle_filter_display('customer', true);
        frappe.query_report.toggle_filter_display('back', true);
      }
  },
	drilldown: function(data) {
		if (data.by && ['customer_group','customer'].includes(data.by)) {
			if (data.by == "customer_group") {
				if (data.value) {
					frappe.query_report.set_filter_value({'customer_group': data.value});
					frappe.query_report.toggle_filter_display('customer_group', false);
					frappe.query_report.toggle_filter_display('back', false);
				} else {
					frappe.query_report.set_filter_value({'customer_group': ""});
					frappe.query_report.toggle_filter_display('customer_group', true);
					frappe.query_report.toggle_filter_display('back', true);
				}
			} else if (data.by == "customer") {
        if (data.value) {
          frappe.query_report.set_filter_value({'customer': data.value});
					frappe.query_report.toggle_filter_display('customer', false);
          frappe.query_report.toggle_filter_display('back', false);
        } else {
          frappe.query_report.set_filter_value({'customer': ""});
					frappe.query_report.toggle_filter_display('customer', true);
          frappe.query_report.toggle_filter_display('back', true);
        }
			}
		} else {
			frappe.query_report.set_filter_value({'customer': ""});
			frappe.query_report.set_filter_value({'customer_group': ""});
			frappe.query_report.toggle_filter_display('customer', true);
			frappe.query_report.toggle_filter_display('customer_group', true);
			frappe.query_report.toggle_filter_display('back', true);
		}
  },
	after_datatable_render: function(datatable_obj) {
		$(datatable_obj.wrapper).find(".dt-row-0").find('input[type=checkbox]').click();
	},
	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
			events: {
				onCheckRow: function(data) {
					let row_name = data[2].content;
					let length = data.length;
					let data_columns_length = (length - 3+2)/4;
					
					let real_columns = {"first":3,"last": 3 + data_columns_length -1};
					let projected_columns = {"first":real_columns.last + data_columns_length, "last": length - (data_columns_length - 1)};
					var tree_type = frappe.query_report.filters[0].value;

					let real_sufix = " " + __("Actual");
					let projected_sufix = " " + __("Projected");
					if (frappe.query_report.get_filter_value("method") == "deflation") {
						projected_sufix = " " + __("Deflated");
					}

					if(tree_type == "Customer") {
						data_columns_length = (length - 4+2)/4;
						real_columns = {"first":4,"last": 4 + data_columns_length - 1};
            projected_columns = {"first":real_columns.last + data_columns_length, "last": length - (data_columns_length - 1)};
					} else if (tree_type == "Item") {
						data_columns_length =(length - 5+2)/4;
						real_columns = {"first":5,"last": 5 + data_columns_length - 1};
						projected_columns = {"first":real_columns.last + data_columns_length, "last": length - (data_columns_length - 1)};
					}

					row_values = data.slice(real_columns.first,real_columns.last+1).map(function (column) {
						return column.content;
          })
					projected_row_values = data.slice(projected_columns.first,projected_columns.last).map(function (column) {
						return column.content;
          })

					entry = {
						'name':row_name + real_sufix,
						'values':row_values
					}

					projected_entry = {
						'name':row_name + projected_sufix,
            'values':projected_row_values
					}

					let raw_data = frappe.query_report.chart.data;
					let new_datasets = raw_data.datasets;

					var found = false;

					for(var i=0; i < new_datasets.length;i++){
						if(new_datasets[i].name == entry.name){
							found = true;
							new_datasets.splice(i,1);
							break;
						}
					}
					if(!found){
            new_datasets.push(entry);
          }

					var found = false;
					for(var i=0; i < new_datasets.length;i++){
						if(new_datasets[i].name == projected_entry.name){
              found = true;
              new_datasets.splice(i,1);
              break;
            }
					}
					if(!found){
						new_datasets.push(projected_entry);
					}

					let new_data = {
						labels: raw_data.labels,
						datasets: new_datasets
					}
					
					
					setTimeout(() => {
						try {
							frappe.query_report.chart.update(new_data);
						} catch (error) {
							console.log(error);
						}
					}, 500)


					setTimeout(() => {
						frappe.query_report.chart.draw(true);
					}, 1000)

					frappe.query_report.raw_chart_data = new_data;
				},
			}
		})
	},
}
