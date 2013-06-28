''' preferences.py contains the settings dialog
    and preferences loading methods. '''

''' ...and this file is part of Pynorama.
    
    Pynorama is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    Pynorama is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with Pynorama. If not, see <http://www.gnu.org/licenses/>. '''

from gi.repository import Gio, GLib, Gtk, Gdk, GObject
from gettext import gettext as _
import cairo, math
import extending, organization

Settings = Gio.Settings("com.example.pynorama")

class Dialog(Gtk.Dialog):
	def __init__(self, app):
		Gtk.Dialog.__init__(self, _("Pynorama Preferences"), None,
			Gtk.DialogFlags.DESTROY_WITH_PARENT,
			(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
		
		self.app = app
		
		# Setup notebook
		tabs = Gtk.Notebook()
		tabs_align = Gtk.Alignment()
		tabs_align.set_padding(15, 15, 15, 15)
		tabs_align.add(tabs)
		self.get_content_area().pack_start(tabs_align, True, True, 0)
		tabs_align.show_all()
		
		# Create tabs
		tab_labels = [_("View"), _("Mouse")]
		tab_aligns = []
		for a_tab_label in tab_labels:
			a_tab_align = Gtk.Alignment()
			
			a_tab_align.set_padding(10, 15, 20, 20)
			tabs.append_page(a_tab_align, Gtk.Label(a_tab_label))
			tab_aligns.append(a_tab_align)
		
		view_tab_align, mouse_tab_align = tab_aligns
					
		# Setup view tad
		
		view_grid = Gtk.Grid()
		view_grid.set_column_spacing(20)
		view_grid.set_row_spacing(5)
		view_tab_align.add(view_grid)
				
		point_label = Gtk.Label(_("Image alignment"))
		alignment_tooltip = _('''This alignment setting is \
used for various alignment related things in the program''')
		
		point_label.set_alignment(0, 0)
		point_label.set_line_wrap(True)
		
		hadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
		xlabel = Gtk.Label(_("Horizontal "))
		xlabel.set_alignment(0, 0.5)
		xspin = Gtk.SpinButton()
		xspin.set_adjustment(hadjust)
		
		vadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
		ylabel = Gtk.Label(_("Vertical "))
		ylabel.set_alignment(0, 0.5)
		yspin = Gtk.SpinButton()
		yspin.set_adjustment(vadjust)
		
		xspin.set_digits(2)
		yspin.set_digits(2)
		
		point_scale = PointScale(hadjust, vadjust)
		
		# Set tooltip
		xspin.set_tooltip_text(alignment_tooltip)
		yspin.set_tooltip_text(alignment_tooltip)
		xlabel.set_tooltip_text(alignment_tooltip)
		ylabel.set_tooltip_text(alignment_tooltip)
		point_label.set_tooltip_text(alignment_tooltip)
		point_scale.set_tooltip_text(alignment_tooltip)
		
		view_grid.attach(point_label, 0, 0, 2, 1)
		
		view_grid.attach(xlabel, 0, 1, 1, 1)
		view_grid.attach(ylabel, 0, 2, 1, 1)
		view_grid.attach(xspin, 1, 1, 1, 1)
		view_grid.attach(yspin, 1, 2, 1, 1)
		view_grid.attach(point_scale, 2, 0, 1, 3)
		self.alignment_x_adjust = hadjust
		self.alignment_y_adjust = vadjust
		
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		
		spin_button_specs = [
			(_("Spin effect"), "spin-effect", (0, 1, 359, 3, 30)),
			(_("Zoom in/out effect"), "zoom-effect", (0, 1.02, 4, 0.1, 0.25))
		]
		
		spin_buttons = []
		for a_label_string, a_property, an_adjustment_args in spin_button_specs:
			a_button_label = Gtk.Label(a_label_string)
			a_button_label.set_hexpand(True)
			a_button_label.set_alignment(0, 0.5)
			
			an_adjustment = Gtk.Adjustment(*(an_adjustment_args + (0,)))
			if a_property:
				self.app.bind_property(a_property, an_adjustment, "value",
				                       bidi_flag | sync_flag)
				
			a_spin_button = Gtk.SpinButton()
			a_spin_button.set_adjustment(an_adjustment)
			
			row = len(spin_buttons) + 3
			view_grid.attach(a_button_label, 0, row, 2, 1)
			view_grid.attach(a_spin_button, 2, row, 1, 1)
			spin_buttons.append(a_spin_button)
		
		self.spin_effect, self.zoom_effect = spin_buttons
		self.zoom_effect.set_digits(2)
		
		# Setup mouse tab
		very_mice_book = Gtk.Notebook()
		
		view_handlers_box = Gtk.Box(spacing=8,
		                            orientation=Gtk.Orientation.VERTICAL)
		add_handler_box = Gtk.Box(spacing=8,
		                          orientation=Gtk.Orientation.VERTICAL)
		
		very_mice_book.append_page(view_handlers_box, None)
		very_mice_book.append_page(add_handler_box, None)
		
		mouse_tab_align.add(very_mice_book)
		
		# Setup handlers grid
		handler_liststore = Gtk.ListStore(object)
		
		for a_handler in self.app.meta_mouse_handler.get_handlers():
			handler_liststore.append([a_handler])
		
		self._handler_listview = handler_listview = Gtk.TreeView()
		handler_listview.set_model(handler_liststore)
		
		handler_listview_selection = handler_listview.get_selection()
		handler_listview_selection.set_mode(Gtk.SelectionMode.MULTIPLE)
		
		name_renderer = Gtk.CellRendererText()
		name_column = Gtk.TreeViewColumn("Nickname")
		name_column.pack_start(name_renderer, True)
		name_column.set_cell_data_func(name_renderer, 
		                               self._handler_nick_data_func)
		
		handler_listview.append_column(name_column)
		
		# Create edit button box
		edit_handler_buttonbox = Gtk.ButtonBox(spacing=8,
		                             orientation=Gtk.Orientation.HORIZONTAL)
		edit_handler_buttonbox.set_layout(Gtk.ButtonBoxStyle.START)
		new_handler_button, configure_handler_button, remove_handler_button = (
			Gtk.Button.new_from_stock(Gtk.STOCK_ADD),
			Gtk.Button.new_from_stock(Gtk.STOCK_PROPERTIES),
			Gtk.Button.new_from_stock(Gtk.STOCK_REMOVE),
		)
		# These are insensitive until something is selected
		remove_handler_button.set_sensitive(False)
		configure_handler_button.set_sensitive(False)
		
		edit_handler_buttonbox.add(configure_handler_button)
		edit_handler_buttonbox.add(new_handler_button)
		edit_handler_buttonbox.add(remove_handler_button)
		edit_handler_buttonbox.set_child_secondary(
		                       configure_handler_button, True)
		
		handler_listscroler = Gtk.ScrolledWindow()
		handler_listscroler.add(handler_listview)
		
		view_handlers_box.pack_start(handler_listscroler, True, True, 0)
		view_handlers_box.pack_start(edit_handler_buttonbox, False, True, 0)
		
		# Setup add handlers grid (it is used to add handlers)
		brand_liststore = Gtk.ListStore(object)
		
		for a_brand in extending.MouseHandlerBrands:
			brand_liststore.append([a_brand])
		
		brand_listview = Gtk.TreeView()
		brand_listview.set_model(brand_liststore)
		
		type_column = Gtk.TreeViewColumn("Type")
		label_renderer = Gtk.CellRendererText()
		type_column.pack_start(label_renderer, True)
		type_column.set_cell_data_func(label_renderer, 
		                               self._brand_label_data_func)
		
		brand_listview.append_column(type_column)
		
		brand_listscroller = Gtk.ScrolledWindow()
		brand_listscroller.add(brand_listview)
		
		# Create button box
		add_handler_buttonbox = Gtk.ButtonBox(spacing=8,
		                             orientation=Gtk.Orientation.HORIZONTAL)
		add_handler_buttonbox.set_layout(Gtk.ButtonBoxStyle.END)
		cancel_button, add_button = (
			Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL),
			Gtk.Button.new_from_stock(Gtk.STOCK_NEW),
		)
		add_handler_buttonbox.add(cancel_button)
		add_handler_buttonbox.add(add_button)
		
		add_handler_box.pack_start(brand_listscroller, True, True, 0)
		add_handler_box.pack_start(add_handler_buttonbox, False, True, 0)
		
		# Bindings and events
		self._window_bindings, self._view_bindings = [], []
		self.connect("notify::target-window", self._changed_target_window)
		self.connect("notify::target-view", self._changed_target_view)
		
		remove_handler_button.connect("clicked", self._clicked_remove_handler)
		handler_listview_selection.connect("changed",
		                                   self._changed_handler_list_selection,
		                                   remove_handler_button,
		                                   configure_handler_button)
		
		tabs.show_all()

	
	def _handler_nick_data_func(self, column, renderer, model, treeiter, *data):
		handler = model[treeiter][0]
		text = handler.nickname
		if not text:
			if handler.factory:
				text = handler.factory.label
				
			else:
				text = "???"
				
		renderer.props.text = text
	
	
	def _clicked_remove_handler(self, *data):
		selection = self._handler_listview.get_selection()
		model, row_paths = selection.get_selected_rows()
		
		remove_handler = self.app.meta_mouse_handler.remove
		
		treeiters = [model.get_iter(a_path) for a_path in row_paths]
		for a_treeiter in treeiters:
			a_handler = model[a_treeiter][0]
			remove_handler(a_handler)
			
			del model[a_treeiter]
	
	
	def _changed_handler_list_selection(self, selection, 
	                                    remove_button, configure_button):
		model, row_paths = selection.get_selected_rows()
		
		selected_anything = bool(row_paths)
		remove_button.set_sensitive(selected_anything)
		configure_button.set_sensitive(selected_anything)
	
	
	def _brand_label_data_func(self, column, renderer, model, treeiter, *data):
		factory = model[treeiter][0]
		renderer.props.text = factory.label
	
	def _popup_add_handlers(self, data):
		time = Gtk.get_current_event_time()
		menu = self._add_handlers_menu
		menu.popup( None, None, None, None, 0, time)
	
	
	def create_widget_group(self, *widgets):
		alignment = Gtk.Alignment()
		alignment.set_padding(0, 0, 20, 0)
		
		box = Gtk.VBox()
		alignment.add(box)
		
		for a_widget in widgets:
			box.pack_start(a_widget, False, False, 3)
			
		return alignment
		
	
	def _changed_target_window(self, *data):
		self.set_transient_for(self.target_window)
		
		view, album = self.target_window.view, self.target_window.album
		
		if self.target_view != view:
			self.target_view = view
			
		if self.target_album != album:
			self.target_album = album
		
		
	def _changed_target_view(self, *data):
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		
		for a_binding in self._view_bindings:
			a_binding.unbind()
		
		view = self.target_view
		if view:
			self._view_bindings = [
				view.bind_property("alignment-x", self.alignment_x_adjust,
						           "value", bidi_flag | sync_flag),
			
				view.bind_property("alignment-y", self.alignment_y_adjust,
				                   "value", bidi_flag | sync_flag)
			]
		else:
			self._view_bindings = []
		
	target_window = GObject.Property(type=object)
	target_view = GObject.Property(type=object)
	target_album = GObject.Property(type=object)
	
def LoadForApp(app):
	app.zoom_effect = Settings.get_double("zoom-effect")
	app.spin_effect = Settings.get_int("rotation-effect")


def SaveFromApp(app):
	Settings.set_double("zoom-effect", app.zoom_effect)
	Settings.set_int("rotation-effect", app.spin_effect)


def LoadForWindow(window):	
	window.toolbar_visible = Settings.get_boolean("interface-toolbar")
	window.statusbar_visible = Settings.get_boolean("interface-statusbar")
	
	hscrollbar = Settings.get_enum("interface-horizontal-scrollbar")
	vscrollbar = Settings.get_enum("interface-vertical-scrollbar")
	window.hscrollbar_placement = hscrollbar
	window.vscrollbar_placement = vscrollbar
	
	auto_zoom = Settings.get_boolean("auto-zoom")
	auto_zoom_minify = Settings.get_boolean("auto-zoom-minify")
	auto_zoom_magnify = Settings.get_boolean("auto-zoom-magnify")
	auto_zoom_mode = Settings.get_enum("auto-zoom-mode")
	
	window.set_auto_zoom_mode(auto_zoom_mode)
	window.set_auto_zoom(auto_zoom, auto_zoom_minify, auto_zoom_magnify)
	
	layout_codename = Settings.get_string("layout-codename")
	
	option_list = extending.LayoutOption.List
	for an_option in option_list:
		if an_option.codename == layout_codename:
			window.layout_option = an_option
			break

def SaveFromWindow(window):	
	Settings.set_boolean("interface-toolbar", window.toolbar_visible)
	Settings.set_boolean("interface-statusbar", window.statusbar_visible)
	
	hscrollbar = window.hscrollbar_placement
	vscrollbar = window.vscrollbar_placement
	Settings.set_enum("interface-horizontal-scrollbar", hscrollbar)
	Settings.set_enum("interface-vertical-scrollbar", vscrollbar)
	
	auto_zoom, auto_zoom_minify, auto_zoom_magnify = window.get_auto_zoom()
	auto_zoom_mode = window.get_auto_zoom_mode()
	
	Settings.set_boolean("auto-zoom", auto_zoom)
	Settings.set_boolean("auto-zoom-minify", auto_zoom_minify)
	Settings.set_boolean("auto-zoom-magnify", auto_zoom_magnify)
	Settings.set_enum("auto-zoom-mode", auto_zoom_mode)
	
	fullscreen = window.get_fullscreen()
	Settings.set_boolean("start-fullscreen", fullscreen)
	
	try:
		layout_codename = window.layout_option.codename
	except Exception:
		pass
		
	else:
		Settings.set_string("layout-codename", window.layout_option.codename)


def LoadForAlbum(album):
	album.freeze_notify()
	try:
		album.autosort = Settings.get_boolean("sort-auto")
		album.reverse = Settings.get_boolean("sort-reverse")
		
		comparer_value = Settings.get_enum("sort-mode")
		album.comparer = organization.SortingKeys.Enum[comparer_value]
		
	finally:
		album.thaw_notify()

	
def SaveFromAlbum(album):
	Settings.set_boolean("sort-auto", album.autosort)
	Settings.set_boolean("sort-reverse", album.reverse)
	
	comparer_value = organization.SortingKeys.Enum.index(album.comparer)
	Settings.set_enum("sort-mode", comparer_value)	

def LoadForView(view):
	view.freeze_notify()
	try:
		# Load alignment
		view.alignment_x = Settings.get_double("view-horizontal-alignment")
		view.alignment_y = Settings.get_double("view-vertical-alignment")
		
		# Load interpolation filter settings
		interp_min_value = Settings.get_enum("interpolation-minify")
		interp_mag_value = Settings.get_enum("interpolation-magnify")
		interp_map = [cairo.FILTER_NEAREST, cairo.FILTER_BILINEAR,
			          cairo.FILTER_FAST, cairo.FILTER_GOOD, cairo.FILTER_BEST]
		view.minify_filter = interp_map[interp_min_value]
		view.magnify_filter = interp_map[interp_mag_value]
	
	finally:
		view.thaw_notify()
	
def SaveFromView(view):
	# Save alignment
	Settings.set_double("view-horizontal-alignment", view.alignment_x)
	Settings.set_double("view-vertical-alignment", view.alignment_y)
	
	# Save interpolation filter settings
	interp_map = [cairo.FILTER_NEAREST, cairo.FILTER_BILINEAR,
	              cairo.FILTER_FAST, cairo.FILTER_GOOD, cairo.FILTER_BEST]
	interp_min_value = interp_map.index(view.minify_filter)
	interp_mag_value = interp_map.index(view.magnify_filter)
	Settings.set_enum("interpolation-minify", interp_min_value)
	Settings.set_enum("interpolation-magnify", interp_mag_value)

class PointScale(Gtk.DrawingArea):
	''' A widget like a Gtk.HScale and Gtk.VScale together. '''
	def __init__(self, hrange, vrange):
		Gtk.DrawingArea.__init__(self)
		self.set_size_request(50, 50)
		self.padding = 1
		self.mark_width = 24
		self.mark_height = 24
		self.dragging = False
		self.__hrange = self.__vrange = None
		self.hrange_signal = self.vrange_signal = None
		self.set_hrange(hrange)
		self.set_vrange(vrange)
		self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
			Gdk.EventMask.BUTTON_RELEASE_MASK |
			Gdk.EventMask.POINTER_MOTION_MASK |
			Gdk.EventMask.POINTER_MOTION_HINT_MASK)
			
	def adjust_from_point(self, x, y):
		w, h = self.get_allocated_width(), self.get_allocated_height()
		t, l = (self.padding + self.mark_height / 2,
		        self.padding + self.mark_width / 2)
		r = w - (self.padding + self.mark_width / 2)
		b = h - (self.padding + self.mark_height / 2)
		
		x, y = (max(0, min(r - l, x - l)) / (r - l),
		        max(0, min(b - t, y - t)) / (b - t))
		        
		hrange = self.get_hrange()
		if hrange:
			lx, ux = hrange.get_lower(), hrange.get_upper()
			vx = x * (ux - lx) + lx
			self.hrange.set_value(vx)
		
		vrange = self.get_vrange()
		if vrange:
			ly, uy = vrange.get_lower(), vrange.get_upper()
			vy = y * (uy - ly) + ly
			self.vrange.set_value(vy)
	
	def do_get_request_mode(self):
		return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH
		
	def do_get_preferred_width_for_height(self, height):
		hrange = self.get_hrange()
		vrange = self.get_vrange()
		lx, ux = hrange.get_lower(), hrange.get_upper()
		ly, uy = vrange.get_lower(), vrange.get_upper()
		return 24, max(24, int((ux - lx) / (uy - ly) * height))
	
	def do_get_preferred_height_for_width(self, width):
		hrange = self.get_hrange()
		vrange = self.get_vrange()
		lx, ux = hrange.get_lower(), hrange.get_upper()
		ly, uy = vrange.get_lower(), vrange.get_upper()
		return 24, max(24, int((uy - ly) / (ux - lx) * width))
		
	def do_button_press_event(self, data):
		self.dragging = True
		self.adjust_from_point(data.x, data.y)
			
	def do_button_release_event(self, data):
		self.dragging = False
		self.queue_draw()
	
	def do_motion_notify_event(self, data):
		if self.dragging:
			mx, my = data.x, data.y
			self.adjust_from_point(mx, my)
	
	def do_draw(self, cr):
		w, h = self.get_allocated_width(), self.get_allocated_height()		
		t, l = (self.padding + self.mark_height / 2,
		        self.padding + self.mark_width / 2)
		r = w - (self.padding + self.mark_width / 2)
		b = h - (self.padding + self.mark_height / 2)
		
		hrange = self.get_hrange()
		if hrange:
			lx, ux = hrange.get_lower(), hrange.get_upper()
			vx = hrange.get_value()
			x = (r - l - 1) * (vx / (ux - lx) - lx) + l
		else:
			x = w / 2
			
		vrange = self.get_vrange()
		if vrange:
			ly, uy = vrange.get_lower(), vrange.get_upper()
			vy = vrange.get_value()
			y = (b - t - 1) * (vy / (uy - ly) - ly) + l
		else:
			y = h / 2
		
		style = self.get_style_context()
		
		style.add_class(Gtk.STYLE_CLASS_ENTRY)
		Gtk.render_background(style, cr, 0, 0, w, h)
		cr.save()
		border = style.get_border(style.get_state())
		radius = style.get_property(Gtk.STYLE_PROPERTY_BORDER_RADIUS,
		                            Gtk.StateFlags.NORMAL)
		color = style.get_color(style.get_state())
		cr.arc(border.left + radius,
		       border.top + radius, radius, math.pi, math.pi * 1.5)
		cr.arc(w - border.right - radius -1,
		       border.top + radius, radius, math.pi * 1.5, math.pi * 2)
		cr.arc(w - border.right - radius -1,
		       h -border.bottom - radius -1, radius, 0, math.pi / 2)
		cr.arc(border.left + radius,
		       h - border.bottom - radius - 1, radius, math.pi / 2, math.pi)
		cr.clip()
		
		cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
		
		ml, mt = x - self.mark_width / 2, y - self.mark_height / 2
		mr, mb = ml + self.mark_width, mt + self.mark_height
		
		ml, mt, mr, mb = round(ml), round(mt), round(mr), round(mb)
		
		cr.set_line_width(1)
		cr.set_dash([1, 7], x)
		Gtk.render_line(style, cr, ml, 0, ml, h)
		Gtk.render_line(style, cr, mr, 0, mr, h)
		cr.set_dash([1, 7], y)
		Gtk.render_line(style, cr, 0, mt, w, mt)
		Gtk.render_line(style, cr, 0, mb, w, mb)
		
		cr.set_line_width(2)
		cr.set_dash([], 0)
		Gtk.render_line(style, cr, ml, mt, ml, mb)
		Gtk.render_line(style, cr, mr, mt, mr, mb)
		Gtk.render_line(style, cr, ml, mt, mr, mt)
		Gtk.render_line(style, cr, ml, mb, mr, mb)
		
		cr.stroke()
		
		cr.restore()
		Gtk.render_frame(style, cr, 0, 0, w, h)
		
	def adjustment_changed(self, data):
		self.queue_draw()
	
	def get_hrange(self):
		return self.__hrange
	def set_hrange(self, adjustment):
		if self.__hrange:
			self.__hrange.disconnect(self.hrange_signal)
			self.hrange_signal = None
			
		self.__hrange = adjustment
		if adjustment:
			self.hrange_signal = adjustment.connect("value-changed",
			                                         self.adjustment_changed)
		self.queue_draw()
		
	def get_vrange(self):
		return self.__vrange
	def set_vrange(self, adjustment):
		if self.__vrange:
			self.__vrange.disconnect(self.vrange_signal)
			self.vrange_signal = None
			
		self.__vrange = adjustment
		if adjustment:
			self.vrange_signal = adjustment.connect("value-changed",
			                                         self.adjustment_changed)
		self.queue_draw()
			                                         
	hrange = GObject.property(get_hrange, set_hrange, type=Gtk.Adjustment)
	vrange = GObject.property(get_vrange, set_vrange, type=Gtk.Adjustment)
