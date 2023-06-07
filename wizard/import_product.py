# -*- coding: utf-8 -*-

import csv
import io
import logging
import base64
from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)

try:
	from cStringIO import StringIO
except ImportError:
	from io import StringIO

class StockInventoryLine(models.Model):
	_inherit = 'stock.quant'

	@api.onchange('product_id')
	def _onchange_product_id(self):
		if self.product_id:
			self.product_uom_id = self.product_id.uom_id.id


class ImportProducts(models.TransientModel):
	_name = "import.products"
	_description = "Product Import"
   
	file_path = fields.Binary(type='binary', string="File To Import")

	def _read_csv_data(self, binary_data):
		"""
			Reads CSV from given path and Return list of dict with Mapping
		"""
		data = csv.reader(StringIO(base64.b64decode(self.file_path).decode('utf-8')), quotechar='"', delimiter=',')

		# Read the column names from the first line of the file
		fields = next(data)
		data_lines = []
		for row in data:
			items = dict(zip(fields, row))
			data_lines.append(items)
		return fields, data_lines

	def do_import_product_data(self):
		file_path = self.file_path
		if not file_path or file_path == "":
			_logger.warning("Import can not be started. Configure your schedule Actions.")
			return True
		fields = data_lines = False

		try:
			fields, data_lines = self._read_csv_data(file_path)
		except:
			_logger.warning("Can not read source file(csv) '%s', Invalid file path or File not reachable on file system."%(file_path))
			return True
		if not data_lines:
			_logger.info("File '%s' has no data or it has been already imported, please update the file."%(file_path))
			return True
		_logger.info("Starting Import Product Process from file '%s'."%(file_path))
		product_tmpl_obj = self.env['product.template']
		product_attribute = self.env['product.attribute']

		bounced_cust = [tuple(fields)]
		error_lst=[]
		product_tmpl_id = False

		rem_product_tmpl_desc = []
		duplicate_product_template = []


		variant_list = []
		stock_move_line_dict = {}
		stock_inventory_obj = self.env['stock.quant']
		location_id = self.env['stock.scrap']._get_default_location_id()

		record = 0
		for data in data_lines:
			
			# Product
			name = data['Name']
			categ_id = data['Product Category'] # Internal Category
			default_code = data['Internal Reference'] # Internal Reference
			color = data['Color'] # Color
			size = data['Size'] # Size
			list_price = data['Sale price'] # Sales price
			barcode = data['EAN'] # Barcode
			quantity = data['Stock'] # Stock

			# Remove extra spaces
			name = name.strip()
			categ_id = categ_id.strip()
			color = color.strip()
			size = size.strip()
			default_code = default_code.strip()
			barcode = barcode.strip()

			product_category_obj = self.env['product.category']
			attribute_value_obj = self.env['product.attribute.value']

			try:
				internal_categ_id = False
				if data['Product Category']:
					internal_categ_id = product_category_obj.search([('name', '=', categ_id)])
					if not internal_categ_id:
						internal_categ_id = product_category_obj.create({'name': categ_id})
				else:
					internal_categ_id = product_category_obj.search([('name', '=', 'All')])
					if not internal_categ_id:
						internal_categ_id = product_category_obj.create({'name': 'All'})
				
				# Product Attributes get
				attribute_color_id = product_attribute.search([('name', '=', 'Color')])
				if not attribute_color_id:
					attribute_color_id = product_attribute.create({'name': 'Color'})

				attribute_size_id = product_attribute.search([('name', '=', 'Size')])
				if not attribute_size_id:
					attribute_size_id = product_attribute.create({'name': 'Size'})

				attribute_color_value_id_lis = []
				attribute_color_value_id = False
				if color:
					for cl in color.split('/'):
						attribute_color_value_id = attribute_value_obj.search([('name', '=', cl), ('attribute_id', '=', attribute_color_id.id)])
						if attribute_color_value_id:
							attribute_color_value_id_lis.append(attribute_color_value_id.id)
						else:
							attribute_color_value_id = attribute_value_obj.create({'attribute_id': attribute_color_id.id, 'name': cl})
							attribute_color_value_id_lis.append(attribute_color_value_id.id)
				

				attribute_size_value_id_lis = []
				attribute_size_value_id = False
				if size:
					for sz in size.split('/'):
						attribute_size_value_id = attribute_value_obj.search([('name', '=', sz), ('attribute_id', '=', attribute_size_id.id)])
						if attribute_size_value_id:
							attribute_size_value_id_lis.append(attribute_size_value_id.id)
						else:
							attribute_size_value_id = attribute_value_obj.create({'attribute_id': attribute_size_id.id, 'name': sz})
							attribute_size_value_id_lis.append(attribute_size_value_id.id)
			  
				attribute_value_list = []
				if attribute_color_value_id:
					attribute_value_list.append([0, 0, {'attribute_id': attribute_color_id.id, 'value_ids': [(6,0, attribute_color_value_id_lis)]}])
				if attribute_size_value_id:
					attribute_value_list.append([0, 0, {'attribute_id': attribute_size_id.id, 'value_ids': [(6,0, attribute_size_value_id_lis)]}])

				exist_product_template = product_tmpl_obj.search([('default_code', '=', default_code)])
				
				product_barcode = False
				if barcode:
					product_barcode = self.env['product.product'].search([('barcode', '=', barcode)])
					if not product_barcode:
						barcode_search = '0' + str(barcode)
						product_barcode = self.env['product.product'].search([('barcode', '=', barcode_search)])

				if len(exist_product_template.ids) != 1:
					for dup in exist_product_template:
						duplicate_product_template.append({'default_code': dup.default_code})
					exist_product_template_test = product_tmpl_obj.search([('barcode', '=', barcode)])
					if not exist_product_template_test and exist_product_template:
						exist_product_template = exist_product_template[0]
					else:
						exist_product_template = exist_product_template_test
				
				if exist_product_template:
					stock_move_line_dict = {}

					for color in attribute_color_value_id_lis:
						attr_obj = exist_product_template.attribute_line_ids.filtered(lambda x: x.attribute_id == attribute_color_value_id.attribute_id)
						if color not in attr_obj.value_ids.ids:
							att_obj_val_ids = attr_obj.value_ids.ids
							att_obj_val_ids.append(color)
							attr_obj.value_ids = [(6, 0, att_obj_val_ids)]
					
					for size in attribute_size_value_id_lis:
						attr_obj = exist_product_template.attribute_line_ids.filtered(lambda x: x.attribute_id == attribute_size_value_id.attribute_id)
						if size not in attr_obj.value_ids.ids:
							att_vals_ids = attr_obj.value_ids.ids
							att_vals_ids.append(size)
							attr_obj.value_ids = [(6, 0, att_vals_ids)]

					for variant in exist_product_template.product_variant_ids:
						product_att_val_id = variant.product_template_attribute_value_ids.product_attribute_value_id.mapped('id')
						for color in attribute_color_value_id_lis:
							for size in attribute_size_value_id_lis:
								stock_move_line_dict = {}
								if color in product_att_val_id and size in product_att_val_id:
									stock_move_line_dict.update({
										'product_id': variant.id, 
										'quantity': quantity, 
										'location_id': location_id
										})

								if stock_move_line_dict:
									stock_inventory = stock_inventory_obj.create(stock_move_line_dict)
				else:
					product_template_vals = {
						'name': name,
						'default_code': default_code,
						'categ_id': internal_categ_id.id,
						'barcode': barcode if barcode else False,
						'type': 'product',
						'description': default_code, # Unieque existing product template
						'list_price': list_price
					}
					if attribute_value_list:
						product_template_vals['attribute_line_ids'] = attribute_value_list
					product_tmpl_id = product_tmpl_obj.create(product_template_vals)
					for variant in product_tmpl_id.product_variant_ids:
						stock_move_line_dict.update({
							'product_id': variant.id, 
							'quantity': quantity, 
							'location_id': location_id
							})

						if stock_move_line_dict:
							stock_inventory = stock_inventory_obj.create(stock_move_line_dict)
				record += 1
				print ("Successfully", record)
			except Exception as e:
				error_lst.append(e)
				reject = [data.get(f, '') for f in fields]
				bounced_cust.append(reject)
				continue

		context = self.env.context.copy()
		self.env.context = context
		return {
				'name': _('Notification'),
				'context': context,
				'view_type': 'form',
				'view_mode': 'form',
				'res_model': 'output.output',
				'type': 'ir.actions.act_window',
				'target':'new'
				}


class OutputOutput(models.TransientModel):
	_name = 'output.output'
	_description = "Bounce file Output"

	file_path = fields.Char('File Location', size=128)
	file = fields.Binary(type='binary', string="Download File",readonly=True)
	flag = fields.Boolean('Flag')
	note = fields.Text('Note')