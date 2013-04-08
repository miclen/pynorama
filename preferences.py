from gi.repository import Gtk
from gettext import gettext as _
import navigation

class Dialog(Gtk.Dialog):
	def __init__(self, app):
		Gtk.Dialog.__init__(self, _("Pynorama Preferences"), None,
			Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
			(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK))
		
		self.app = app
		
		tabs = Gtk.Notebook()
		tabs_align = Gtk.Alignment()
		tabs_align.set_padding(15, 15, 15, 15)
		
		tabs_align.add(tabs)
		self.get_content_area().pack_start(tabs_align, True, True, 0)
		
		tabs_align.show_all()
		
		tab_labels = [_("Panning"), _("Zooming")]
		tab_grids = []
		for a_tab_label in tab_labels:
			a_tab_align = Gtk.Alignment()
			a_tab_grid = Gtk.Grid()
			a_tab_grid.set_column_spacing(20)
			a_tab_grid.set_row_spacing(5)
			a_tab_align.set_padding(10, 15, 20, 20)
			a_tab_align.add(a_tab_grid)
			tabs.append_page(a_tab_align, Gtk.Label(a_tab_label))
			tab_grids.append(a_tab_grid)
		
		pan_grid, zoom_grid = tab_grids
						
		self.nav_book = Gtk.Notebook()
		self.nav_book.set_show_tabs(False)
		self.nav_book.set_show_border(False)
		self.nav_selection = Gtk.ComboBoxText()
		self.nav_selection.set_hexpand(True)
		self.navi_widgets = []
		self.navigators = []
		
		for navi in navigation.NaviList:
			name = navi.get_name()
			label = Gtk.Label(name)
			widgets = navi.get_settings_widgets()
			
			self.nav_book.append_page(widgets, label)
			self.nav_selection.append_text(name)
			self.navigators.append(navi)
					
		self.nav_selection.connect("changed", self.refresh_nav_book)	
		self.nav_enabler = Gtk.CheckButton(_("Enable mouse panning"))
		
		current_navi = self.app.navi_factory
		self.nav_enabler.set_active(current_navi is not None)
		
		if current_navi is None:
			self.nav_selection.set_active(0)
		else:
			self.nav_selection.set_active(self.navigators.index(current_navi))
			
		nav_mode_label = Gtk.Label(_("Mouse panning mode"))
		pan_grid.attach(nav_mode_label, 0, 0, 1, 1)
		pan_grid.attach(self.nav_selection, 1, 0, 1, 1)
		pan_grid.attach(self.nav_enabler, 2, 0, 1, 1)
		pan_grid.attach(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL),
		                0, 1, 3, 1)
		pan_grid.attach(self.nav_book, 0, 2, 3, 1)
		
		self.zoom_effect = Gtk.SpinButton()
		self.zoom_effect.set_adjustment(Gtk.Adjustment(
		                                self.app.zoom_effect,
		                                1.02, 4, 0.1, 0.25, 0
		                                ))
		self.zoom_effect.set_digits(2)
		
		zoom_label = Gtk.Label(_("Zoom in/out effect"))
		zoom_label.set_hexpand(True)
		zoom_label.set_alignment(0, 0.5)
		zoom_grid.attach(zoom_label, 0, 0, 1, 1)
		zoom_grid.attach(self.zoom_effect, 1, 0, 1, 1)
		
		tabs.show_all()
		self.refresh_nav_book()
		
	def create_widget_group(self, *widgets):
		alignment = Gtk.Alignment()
		alignment.set_padding(0, 0, 20, 0)
		
		box = Gtk.VBox()
		alignment.add(box)
		
		for a_widget in widgets:
			box.pack_start(a_widget, False, False, 3)
			
		return alignment
		
	def refresh_nav_book(self, data=None):
		active_page = self.nav_selection.get_active()
		if active_page >= 0:
			self.nav_book.set_current_page(active_page)
			
	def save_prefs(self):
		# Go through all pages to get the "widgets" and tell them to save themselves
		for the_n in range(self.nav_book.get_n_pages()):
			self.nav_book.get_nth_page(the_n).save_settings()
			
		if self.nav_enabler.get_active():
			selected_navi = self.navigators[self.nav_selection.get_active()]
		else:
			selected_navi = None
		# Maybe I should reattach the same navigator, maybe not
		self.app.set_navi_factory(selected_navi)
		self.app.zoom_effect = self.zoom_effect.get_value()