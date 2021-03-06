#!/usr/bin/env python3
# coding=utf-8
 
''' pynorama.py is the main module of an image viewer application. '''

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

import gc, math, random, os, sys
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib, GObject
import cairo
from gettext import gettext as _
import extending, utility
import organization, mousing, loading, preferences, viewing, notification
from viewing import ZoomMode
from loading import DirectoryLoader
DND_URI_LIST, DND_IMAGE = range(2)

class ImageViewer(Gtk.Application):
	Version = "v0.2.3"
		
	def __init__(self):
		Gtk.Application.__init__(self)
		self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)
		
		# Default prefs stuff
		self._preferences_dialog = None
		self.memory_check_queued = False
		self.meta_mouse_handler = mousing.MetaMouseHandler()
		self.meta_mouse_handler.connect("handler-removed",
		                                self._removed_mouse_handler)
		self.mouse_handler_dialogs = dict()
		
		
	# --- Gtk.Application interface down this line --- #
	def do_startup(self):
		Gtk.Application.do_startup(self)
		
		preferences.LoadForApp(self)
		
		self.memory = loading.Memory()
		self.memory.connect("thing-requested", self.queue_memory_check)
		self.memory.connect("thing-unused", self.queue_memory_check)
		self.memory.connect("thing-unlisted", self.queue_memory_check)
			
		Gtk.Window.set_default_icon_name("pynorama")
	
	
	def do_activate(self):
		some_window = self.get_window()
		some_window.present()
	
	
	def do_open(self, files, file_count, hint):
		some_window = self.get_window()
		
		some_window.go_new = True
		self.open_files_for_album(some_window.album, files=files,
		                          search=file_count == 1)
		some_window.go_new = False
		
		some_window.present()
	
	
	def do_shutdown(self):
		preferences.SaveFromApp(self)
		Gtk.Application.do_shutdown(self)
	
	
	#-- Some properties down this line --#
	zoom_effect = GObject.Property(type=float, default=2)
	spin_effect = GObject.Property(type=float, default=90)
	
	def open_image_dialog(self, album, window=None):
		''' Creates an "open image..." dialog for
		    adding images into an album. '''
		    
		image_chooser = Gtk.FileChooserDialog(_("Open Image..."), window,
		                                      Gtk.FileChooserAction.OPEN,
		                                      (Gtk.STOCK_CANCEL,
		                                       Gtk.ResponseType.CANCEL,
		                                       Gtk.STOCK_ADD,
		                                       1,
		                                       Gtk.STOCK_OPEN,
		                                       Gtk.ResponseType.OK))
			
		image_chooser.set_default_response(Gtk.ResponseType.OK)
		image_chooser.set_select_multiple(True)
		image_chooser.set_local_only(False)
		
		# Add dialog options from "loading" module
		for a_dialog_option in loading.CombinedDialogOption.List:
			a_dialog_filter = a_dialog_option.create_filter()
			image_chooser.add_filter(a_dialog_filter)			
			
		for a_dialog_option in loading.DialogOption.List:
			a_dialog_filter = a_dialog_option.create_filter()
			image_chooser.add_filter(a_dialog_filter)
			
		clear_album = False
		search_siblings = False
		choosen_uris = None
		
		response = image_chooser.run()
		
		choosen_option = image_chooser.get_filter().dialog_option
		if response in [Gtk.ResponseType.OK, 1]:
			choosen_uris = image_chooser.get_uris()
		
		if response == Gtk.ResponseType.OK:
			clear_album = True
			if len(choosen_uris) == 1:
				search_siblings = True
				
		image_chooser.destroy()
			
		if choosen_uris:
			self.open_files_for_album(album, choosen_option.loader,
			                          uris=choosen_uris, search=search_siblings,
			                          replace=clear_album)
	
	
	def show_preferences_dialog(self, target_window=None):
		''' Show the preferences dialog '''
		
		target_window = target_window or self.get_window()
		
		if not self._preferences_dialog:
			dialog = self._preferences_dialog = preferences.Dialog(self)
			
			dialog.connect("response", self._preferences_dialog_responded)
			dialog.present()
			
		self._preferences_dialog.target_window = target_window
		self._preferences_dialog.present()
	
	
	def _preferences_dialog_responded(self, *data):
		self._preferences_dialog.destroy()
		self._preferences_dialog = None
		preferences.SaveFromApp(self)
		
	
	def get_mouse_handler_dialog(self, handler):
		dialog = self.mouse_handler_dialogs.pop(handler, None)
		if not dialog:
			# Create a new dialog if there is not one
			create_dialog = preferences.MouseHandlerSettingDialog
			handler_data = self.meta_mouse_handler[handler]
			dialog = create_dialog(handler, handler_data)
			self.mouse_handler_dialogs[handler] = dialog
			dialog.connect("response", lambda d, v: d.destroy())
			dialog.connect("destroy", self._mouse_handler_dialog_destroyed)
			
		return dialog
	
	
	def _mouse_handler_dialog_destroyed(self, dialog, *data):
		self.mouse_handler_dialogs.pop(dialog.handler, None)
		
		
	def _removed_mouse_handler(self, meta, handler):
		dialog = self.mouse_handler_dialogs.pop(handler, None)
		if dialog:
			dialog.destroy()
		
	
	def show_about_dialog(self, window=None):
		''' Shows the about dialog '''
		dialog = Gtk.AboutDialog(program_name="pynorama",
		                         version=ImageViewer.Version,
		                         comments=_("pynorama is an image viewer"),
		                         logo_icon_name="pynorama",
		                         license_type=Gtk.License.GPL_3_0)
		                         
		dialog.set_copyright("Copyrght © 2013 Leonardo Augusto Pereira")
		
		dialog.set_transient_for(window or self.get_window())
		dialog.set_modal(True)
		dialog.set_destroy_with_parent(True)
		
		dialog.run()
		dialog.destroy()
		
		
	def get_window(self):
		windows = self.get_windows() # XP, Vista, 7, 8?
		if windows:
			# Return most recently focused window
			return windows[0]
		else:
			# Create a window and return it
			try:
				a_window = ViewerWindow(self)
			
			except Exception:
				# Doing this because I'm tired of ending up with a
				# frozen process when an exception occurs in the 
				# ViewerWindow constructor. Meaning a_window it doesn't get set
				# and thus a window not shown, but since the ApplicationWindow
				# constructor comes before any errors it gets added to the
				# application windows list, and the application will not quit
				# while the list is not empty.</programmerrage>
				notification.log("\nCould not create the first window\n")
				windows = self.get_windows()
				if len(windows) > 0:
					self.remove_window(windows[0])
					
				raise
				
			a_window.show()
			image_view = a_window.view
			image_view.mouse_adapter = mousing.MouseAdapter(image_view)
			self.meta_mouse_handler.attach(image_view.mouse_adapter)
			
			fillscreen = preferences.Settings.get_boolean("start-fullscreen")
			a_window.set_fullscreen(fillscreen)
			return a_window
			
			
	def queue_memory_check(self, *data):
		if not self.memory_check_queued:
			self.memory_check_queued = True
			GObject.idle_add(self.memory_check)
			
			
	def memory_check(self):
		self.memory_check_queued = False
		
		while self.memory.enlisted_stuff:
			enlisted_thing = self.memory.enlisted_stuff.pop()
			enlisted_thing.connect("finished-loading", self.log_loading_finish)
				
		if self.memory.unlisted_stuff or self.memory.unused_stuff:
			while self.memory.unlisted_stuff:
				unlisted_thing = self.memory.unlisted_stuff.pop()
				if unlisted_thing.is_loading or unlisted_thing.on_memory:
					unlisted_thing.unload()
					notification.log(notification.Lines.Unloaded(unlisted_thing))
					
			while self.memory.unused_stuff:
				unused_thing = self.memory.unused_stuff.pop()
				# Do not unload things that are not on disk (like pastes)
				if unused_thing.on_disk:
					if unused_thing.is_loading or unused_thing.on_memory:
						unused_thing.unload()
						notification.log(notification.Lines.Unloaded(unused_thing))
						
			gc.collect()
			
		while self.memory.requested_stuff:
			requested_thing = self.memory.requested_stuff.pop()
			if not (requested_thing.is_loading or requested_thing.on_memory):
				requested_thing.load()
				notification.log(notification.Lines.Loading(requested_thing))
				
		return False
		
		
	def log_loading_finish(self, thing, error):
		if error:
			notification.log(notification.Lines.Error(error))
			
		elif thing.on_memory:
			notification.log(notification.Lines.Loaded(thing))
	
	
	def open_files_for_album(self, album, loader=None, files=None, uris=None,
	                         replace=False, search=False, silent=False,
	                         manage=True):
		''' Open files or uris for an album '''
		album_context = loading.Context(files=files, uris=uris)
		context_sorting = lambda ctx: album.sort_list(ctx.images)
		
		self.open_files(album_context, context_sorting=context_sorting,
		                loader=loader, search=search, silent=silent)
		
		if album_context.images:
			if replace:
				del album[:]
			
			if manage:			
				for image in album_context.images:
					self.memory.observe(image)
					
			album.extend(album_context.images)
		
		
	def open_files(self, context, loader=None, search=False,
	                     context_sorting=None, silent=False):
	                     
		''' Open files using loading.LoadersLoader '''
		if loader is None:
			loader = loading.LoadersLoader.LoaderListLoader
		
		context.uris_to_files()
		context.load_files_info()
		for a_file, a_problem in context.problems.items():
			context.files.remove(a_file)
		
		directories = []
		removed_files = 0
		for i in range(len(context.files)):
			index = i - removed_files
			a_file = context.files[index]
			try:
				if DirectoryLoader.should_open(a_file):
					removed_files += 1
					directories.append(a_file)
					del context.files[index]
			except Exception:
				raise
		
		if search and context.files:
			# Sibling file loading is not sorted
			context.add_sibling_files(loader)
			files = list(context.files)
			del context.files[:]
			self.open_context_images(context, files, loader)
			                         
		if directories:
			self.open_context_images(context, directories, DirectoryLoader,
			                         sort_method=context_sorting)
			                         
		if context.files:
			self.open_context_images(context, context.files, loader,
			                         sort_method=context_sorting)
		
		if context.problems and not silent:
			problem_list = []
			for a_file, a_problem in context.problems.items():
				problem_list.append((a_file.get_parse_name(), str(a_problem))) 
			
			message = _("There were problems opening the following files:")
			columns = [_("File"), _("Error")]
			
			notification.alert_list(message, problem_list, columns)
			
			
	def open_context_images(self, context, files, loader, sort_method=None):
		''' Opens files in a loader, sort the result with sort_method and
		    append it to context. '''
		loader_context = loading.Context()
		for a_file in files:
			loader.open_file(loader_context, a_file)
		
		if sort_method:
			sort_method(loader_context)
		
		context.images.extend(loader_context.images)
		context.files.extend(loader_context.files)
		context.uris.extend(loader_context.uris)
		
	def load_pixels(self, pixels):
		pixelated_image = loading.PixbufDataImageNode(pixels, "Pixels")
		return [pixelated_image]
	
	
class ViewerWindow(Gtk.ApplicationWindow):
	def __init__(self, app):
		Gtk.ApplicationWindow.__init__(
			self, title=_("Pynorama"), application=app
		)
		self.app = app
		self.set_default_size(600, 600)
		
		# Idly refresh index
		self._refresh_index = utility.IdlyMethod(self._refresh_index)
		self._refresh_transform = utility.IdlyMethod(self._refresh_transform)
		
		# Auto zoom stuff
		self.auto_zoom_magnify = False
		self.auto_zoom_minify = True
		self.auto_zoom_mode = 0
		self.auto_zoom_enabled = False
		# If the user changes the zoom set by auto_zoom, 
		# then auto_zoom isn't called after rotating or resizing
		# the imageview
		self.auto_zoom_zoom_modified = False
		# Album variables
		
		
		self._focus_loaded_handler_id = None
		self._old_focused_image = None
		self.go_new = False
		self.album = organization.Album()
		self.album.connect("image-added", self._image_added)
		self.album.connect("image-removed", self._image_removed)
		self.album.connect("order-changed", self._album_order_changed)
		
		# Set clipboard
		self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		
		# Create layout
		vlayout = Gtk.VBox()
		self.add(vlayout)
		vlayout.show()
		
		# Setup actions
		self.setup_actions()
		
		self.uimanager.add_ui_from_string(ViewerWindow.ui_description)
		self.menubar = self.uimanager.get_widget("/menubar")
		self.toolbar = self.uimanager.get_widget("/toolbar")
		
		# Make the toolbar look primary
		toolbar_style = self.toolbar.get_style_context()
		toolbar_style.add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)
		vlayout.pack_start(self.menubar, False, False, 0)
		vlayout.pack_start(self.toolbar, False, False, 0)
		self.menubar.show_all()
		self.toolbar.show_all()
		
		# Create a scrollwindow and a imagev--, galleryv-- err.. imageview!
		self.view_scroller = Gtk.ScrolledWindow()
		# TODO: There ought to be a better way
		# to drop the default key behaviour
		self.view_scroller.connect("key-press-event", lambda x, y: True)
		self.view_scroller.connect("key-release-event", lambda x, y: True)
		self.view_scroller.connect("scroll-event", lambda x, y: True)
		
		self.view = viewing.ImageView()
		# Setup a bunch of reactions to all sorts of things
		self.view.connect("notify::magnification",
		                       self.magnification_changed)
		self.view.connect("notify::rotation", self.reapply_auto_zoom)
		self.view.connect("size-allocate", self.reapply_auto_zoom)
		self.view.connect("notify::magnification", self.view_changed)
		self.view.connect("notify::rotation", self.view_changed)
		self.view.connect("notify::horizontal-flip", self.view_changed)
		self.view.connect("notify::vertical-flip", self.view_changed)
		
		self.view_scroller.add(self.view)
		self.view_scroller.show_all()
		
		vlayout.pack_start(self.view_scroller, True, True, 0)
		
		# Add a status bar, the statusbar box and a statusbar box box
		self.statusbarboxbox = Gtk.Box()
		self.statusbarboxbox.set_orientation(Gtk.Orientation.VERTICAL)
		separator = Gtk.Separator()
		self.statusbarboxbox.pack_start(separator, False, False, 0)
		
		self.statusbarbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
		self.statusbarbox.set_spacing(8)
		
		# With a label for image index
		self.index_label = Gtk.Label()
		self.index_label.set_alignment(1, 0.5)
		self.index_label.set_tooltip_text(_("""The index of the current image \
/ the album image count"""))
		self.statusbarbox.pack_start(self.index_label, False, True, 0)
		
		# And a spinner for loading hint
		self.loading_spinner = Gtk.Spinner()
		self.statusbarbox.pack_start(self.loading_spinner, False, True, 0)
		
		self.statusbar = Gtk.Statusbar()
		self.statusbarbox.pack_start(self.statusbar, True, True, 0)
		
		# And a label for the image transformation
		transform_labels = (
			Gtk.Label(),
			Gtk.Label(), Gtk.Label(), Gtk.Label(), Gtk.Label()
		)
		for a_label in transform_labels:
			self.statusbarbox.pack_end(a_label, False, True, 0)
		
		self.flip_label, self.angle_label, self.zoom_label, \
			self.size_label, self.status_label = transform_labels
		
		self.size_label.set_tooltip_text(_("Image width×height"))
		self.flip_label.set_tooltip_text(_("Direction the image is flipped"))
		self.zoom_label.set_tooltip_text(_("Image magnification"))
		self.angle_label.set_tooltip_text(_("Rotation in degrees"))
		
		statusbarboxpad = Gtk.Alignment()
		statusbarboxpad.set_padding(3, 3, 12, 12)
		statusbarboxpad.add(self.statusbarbox)
		
		self.statusbarboxbox.pack_end(statusbarboxpad, False, True, 0)
		
		# Show status
		vlayout.pack_end(self.statusbarboxbox, False, True, 0)
		
		self.statusbarboxbox.show_all()
		self.loading_spinner.hide()
		
		# DnD setup	
		self.view.drag_dest_set(
			Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY
		)
		target_list = Gtk.TargetList.new([])
		target_list.add_image_targets(DND_IMAGE, False)
		target_list.add_uri_targets(DND_URI_LIST)
		
		self.view.drag_dest_set_target_list(target_list)
		self.view.connect("drag-data-received", self.dragged_data)
		
		# Setup layout stuff
		self.layout_dialog = None
		self.avl = organization.AlbumViewLayout(album=self.album,
		                                        view=self.view)
		
		self.avl.connect("notify::layout", self._layout_changed)
		self.avl.connect("focus-changed", self._focus_changed)
		
		
		# Build layout menu
		self._layout_action_group = None
		self._layout_ui_merge_id = None
		
		self._layout_options_merge_ids = dict()
		optionList = extending.LayoutOption.List
		
		other_option = self.actions.get_action("layout-other-option")
		other_option.connect("changed", self._layout_option_chosen)
		
		for an_index, an_option in enumerate(optionList):
			a_merge_id = self.uimanager.new_merge_id()
			
			# create action
			an_action_name = "layout-option-" + an_option.codename
			an_action = Gtk.RadioAction(an_action_name, an_option.name,
			                            an_option.description,
			                            None, an_index)
			                            
			an_action.join_group(other_option)
			self.actions.add_action(an_action)
			
			# Insert UI
			self.uimanager.add_ui(
				a_merge_id,
				"/ui/menubar/view/layout/layout-options",
				an_action_name, # the item name
				an_action_name, # the action name
				Gtk.UIManagerItemType.MENUITEM,
				False
			)
			
			self._layout_options_merge_ids[an_option] = a_merge_id
			
		# Bind properties
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		get_action = self.actions.get_action
		utility.Bind(self,
			("sort-automatically", self.album, "autosort"),
			("reverse-ordering", self.album, "reverse"),
			("toolbar-visible", self.toolbar, "visible"),
			("statusbar-visible", self.statusbarboxbox, "visible"),
			("reverse-ordering", get_action("sort-reverse"), "active"),
			("sort-automatically", get_action("sort-auto"), "active"),
			("ordering-mode", get_action("sort-name"), "current-value"),
			("toolbar-visible", get_action("ui-toolbar"), "active"),
			("statusbar-visible", get_action("ui-statusbar"), "active"),
			bidirectional=True
		)
		
		self.view.bind_property(
			"current-interpolation-filter",
			get_action("interp-nearest"), "current-value",
			bidi_flag
		)
		self.view.bind_property(
			"zoomed",
			get_action("interpolation"), "sensitive",
			bidi_flag | sync_flag
		)
		
		self.connect("notify::vscrollbar-placement", self._changed_scrollbars)
		self.connect("notify::hscrollbar-placement", self._changed_scrollbars)
		self.connect("notify::ordering-mode", self._changed_ordering_mode)
		self.connect("notify::layout-option", self._changed_layout_option)
		
		self.album.connect("notify::comparer", self._changed_album_comparer)
		
		# Load preferences
		other_option.set_current_value(0)
		preferences.LoadForWindow(self)
		preferences.LoadForView(self.view)
		preferences.LoadForAlbum(self.album)
		
		# Refresh status widgets
		self._refresh_transform()
		self._refresh_index()
		
	def setup_actions(self):
		self.uimanager = Gtk.UIManager()
		self.uimanager.connect("connect-proxy",
		                     lambda ui, a, w: self.connect_to_statusbar(a, w))
		
		self.accelerators = self.uimanager.get_accel_group()
		self.add_accel_group(self.accelerators)
		self.actions = Gtk.ActionGroup("pynorama")
		self.uimanager.insert_action_group(self.actions)
		
		action_params = [
		# File Menu
		("file", _("_File"), None, None),
			("open", _("_Open..."), _("Opens an image in the viewer"),
			 Gtk.STOCK_OPEN),
			("paste", _("_Paste"), _("Shows an image from the clipboard"),
			 Gtk.STOCK_PASTE),
			# Ordering submenu
			("ordering", _("Or_dering"),
			 _("Image ordering settings"), None),
			    ("sort", _("_Sort Images"),
			     _("Sorts the images currently loaded"), None),
			    ("sort-auto", _("Sort _Automatically"),
			     _("Sorts images as they are added"), None),
			     ("sort-reverse", _("_Reverse Order"),
			      _("Reverts the image order"), None),
				("sort-name", _("By _Name"),
				 _("Compares filenames and number sequences but not dots"),
				 None),
				("sort-char", _("By _Characters"),
				 _("Only compares characters in filenames"),
				 None),
				("sort-file-date", _("By _Modification Date"),
				 _("Compares dates when images were last modified"), None),
				("sort-file-size", _("By _File Size"),
				 _("Compares files byte size"), None),
				("sort-img-size", _("By Image Si_ze"),
				 _("Compares images pixel count, or width times height"), None),
				("sort-img-width", _("By Image _Width"),
				 _("Compares images width"), None),
				("sort-img-height", _("By Image _Height"),
				 _("Compares images height"), None),
			("remove", _("_Remove"), _("Removes the image from the viewer"),
			 Gtk.STOCK_CLOSE),
			("clear", _("R_emove All"), _("Removes all images from the viewer"),
			 Gtk.STOCK_CLEAR),
			("quit", _("_Quit"), _("Exits the program"), Gtk.STOCK_QUIT),
		# Go menu
		("go", _("_Go"), None, None),
			("go-previous", _("P_revious Image"), _("Loads the previous image"),
			 Gtk.STOCK_GO_BACK),
			("go-next", _("Nex_t Image"), _("Loads the next image"),
			 Gtk.STOCK_GO_FORWARD),
			("go-first", _("Fir_st Image"), _("Loads the first image"),
			 Gtk.STOCK_GOTO_FIRST),
			("go-last", _("L_ast Image"), _("Loads the last image"),
			 Gtk.STOCK_GOTO_LAST),
 			("go-random", _("A_ny Image"), _("Loads some random image"),
			 Gtk.STOCK_GOTO_LAST),
		# View menu
		("view", _("_View"), None, None),
			("zoom-in", _("Zoom _In"), _("Makes the image look larger"),
			 Gtk.STOCK_ZOOM_IN),
			("zoom-out", _("Zoom _Out"), _("Makes the image look smaller"),
			 Gtk.STOCK_ZOOM_OUT),
			("zoom-none", _("No _Zoom"),
			 _("Shows the image at it's normal size"), Gtk.STOCK_ZOOM_100),
			# Auto-zoom submenu
			("auto-zoom", _("_Automatic Zoom"), 
			 _("Automatic zooming features"), None),
				("auto-zoom-enable", _("Enable _Automatic Zoom"),
				 _("Enables the automatic zoom features"), None),
				("auto-zoom-fit", _("Fi_t Image"),
				 _("Fits the image completely inside the window"), None),
				("auto-zoom-fill", _("Fi_ll Window"),
				 _("Fills the window completely with the image"), None),
				("auto-zoom-match-width", _("Match _Width"),
				 _("Gives the image the same width as the window"), None),
				("auto-zoom-match-height", _("Match _Height"),
				 _("Gives the image the same height as the window"), None),
				("auto-zoom-minify", _("Mi_nify Large Images"),
				 _("Let the automatic zoom minify images"), None),
				("auto-zoom-magnify", _("Ma_gnify Small Images"),
				 _("Let the automatic zoom magnify images"), None),
			# Transform submenu
			("transform", _("_Transform"),
			 _("Viewport transformation"), None),
				("rotate-cw", _("_Rotate Clockwise"),
				 _("Turns the top side to the right side"), None),
				("rotate-ccw", _("Rotat_e Counter Clockwise"),
				 _("Turns the top side to the left side"), None),
				("flip-h", _("Flip _Horizontally"), 
				 _("Inverts the left and right sides"), None),
				("flip-v", _("Flip _Vertically"),
				 _("Inverts the top and bottom sides"), None),
				("transform-reset", _("Re_set"),
				 _("Resets the view transform"), None),
			# Interpolation submenu
			("interpolation", _("Inter_polation"),
			 _("Pixel interpolation settings"), None),
				("interp-nearest", _("_Nearest Neighbour Filter"),
				 _("Interpolation filter that does not blend pixels"), None),
				("interp-bilinear", _("_Bilinear Filter"),
				 _("Interpolation filter that blends pixels in a linear way"),
				 None),
				("interp-fast", _("Fa_ster Fil_ter"),
				 _("A fast interpolation filter"), None),
				("interp-good", _("B_etter Filt_er"),
				 _("A good interpolation filter"), None),
				("interp-best", _("St_ronger Filte_r"),
				 _("The best interpolation filter avaiable"), None),
			 # Layout submenu
			("layout", _("_Layout"), _("Album layout settings"), None),
				("layout-other-option","", "", None),
				("layout-configure", _("_Configure..."),
				 _("Shows a dialog to configure the current album layout"),
				 None),
			# Interface submenu
			("interface", _("_Interface"),
			 _("This window settings"), None),
				("ui-toolbar", _("T_oolbar"),
				 _("Displays a toolbar with tools"), None),
				("ui-statusbar", _("Stat_usbar"),
				 _("Displays a statusbar with status"), None),
				("ui-scrollbar-top", _("_Top Scroll Bar"),
				 _("Displays the horizontal scrollbar at the top side"), None),
				("ui-scrollbar-bottom", _("_Bottom Scroll Bar"),
				 _("Displays the horizontal scrollbar at the bottom side"), None),
				("ui-scrollbar-left", _("Le_ft Scroll Bar"),
				 _("Displays the vertical scrollbar at the left side"), None),
				("ui-scrollbar-right", _("Rig_ht Scroll Bar"),
				 _("Displays the vertical scrollbar at the right side"), None),
				("ui-keep-above", _("Keep Ab_ove"),
				 _("Keeps this window above other windows"), None),
				("ui-keep-below", _("Keep Be_low"),
				 _("Keeps this window below other windows"), None),
			("preferences", _("_Preferences..."),
			 _("Shows Pynorama preferences dialog"),
			 Gtk.STOCK_PREFERENCES),
			("fullscreen", _("_Fullscreen"),
			 _("Fills the entire screen with this window"),
			 Gtk.STOCK_FULLSCREEN),
		("help", _("_Help"),
		 _("Help! I'm locked inside an image viewer!" + 
		   "I have wife and children! Please, save me!!!"), None),
			("about", _("_About"), _("Shows the about dialog"),
			 Gtk.STOCK_ABOUT),
		]
		
		signaling_params = {
			"open" : (self.file_open,),
			"paste" : (self.pasted_data,),
			"sort" : (lambda data: self.album.sort(),),
			"sort-reverse" : (self._toggled_reverse_sort,),
			"remove" : (self.handle_remove,),
			"clear" : (self.handle_clear,),
			"quit" : (lambda data: self.destroy(),),
			"go-previous" : (self.go_previous,),
			"go-next" : (self.go_next,),
			"go-first" : (self.go_first,),
			"go-last" : (self.go_last,),
			"go-random" : (self.go_random,),
			"zoom-in" : (lambda data: self.zoom_view(1),),
			"zoom-out" : (lambda data: self.zoom_view(-1),),
			"zoom-none" : (lambda data: self.set_view_zoom(1),),
			"auto-zoom-enable" : (self.change_auto_zoom,),
			"auto-zoom-fit" : (self.change_auto_zoom,),
			"auto-zoom-magnify" : (self.change_auto_zoom,),
			"auto-zoom-minify" : (self.change_auto_zoom,),
			"rotate-cw" : (lambda data: self.rotate_view(1),),
			"rotate-ccw" : (lambda data: self.rotate_view(-1),),
			"flip-h" : (lambda data: self.flip_view(False),),
			"flip-v" : (lambda data: self.flip_view(True),),
			"transform-reset" : (lambda data: self.reset_view_transform(),),
			"layout-configure" : (self.show_layout_dialog,),
			"ui-scrollbar-top" : (self._toggled_hscroll,),
			"ui-scrollbar-bottom" : (self._toggled_hscroll,),
			"ui-scrollbar-left" : (self._toggled_vscroll,),
			"ui-scrollbar-right" : (self._toggled_vscroll,),
			"ui-keep-above" : (self.toggle_keep_above,),
			"ui-keep-below" : (self.toggle_keep_below,),
			"preferences" : (lambda data:
			                 self.app.show_preferences_dialog(self),),
			"fullscreen" : (self.toggle_fullscreen,),
			"about" : (lambda data: self.app.show_about_dialog(self),),
		}
		
		sort_group, interp_group, zoom_mode_group = [], [], []
		hscroll_group, vscroll_group = [], []
		
		toggleable_actions = {
			"sort-auto" : None,
			"sort-reverse" : None,
			"auto-zoom-enable" : None,
			"auto-zoom-fit" : (ZoomMode.FitContent, zoom_mode_group),
			"auto-zoom-fill" : (ZoomMode.FillView, zoom_mode_group),
			"auto-zoom-match-width" : (ZoomMode.MatchWidth, zoom_mode_group),
			"auto-zoom-match-height" : (ZoomMode.MatchHeight, zoom_mode_group),
			"auto-zoom-minify" : None,
			"auto-zoom-magnify" : None,
			"fullscreen" : None,
			"sort-name" : (0, sort_group),
			"sort-char" : (1, sort_group),
			"sort-file-date" : (2, sort_group),
			"sort-file-size" : (3, sort_group),
			"sort-img-size" : (4, sort_group),
			"sort-img-width" : (5, sort_group),
			"sort-img-height" : (6, sort_group),
			"interp-nearest" : (cairo.FILTER_NEAREST, interp_group),
			"interp-bilinear" : (cairo.FILTER_BILINEAR, interp_group),
			"interp-fast" : (cairo.FILTER_FAST, interp_group),
			"interp-good" : (cairo.FILTER_GOOD, interp_group),
			"interp-best" : (cairo.FILTER_BEST, interp_group),
			"layout-other-option" : (-1, []),
			"ui-statusbar" : None,
			"ui-toolbar" :None,
			"ui-scrollbar-top" : None,
			"ui-scrollbar-bottom" : None,
			"ui-scrollbar-left" : None,
			"ui-scrollbar-right" : None,
			"ui-keep-above" : None,
			"ui-keep-below" : None,
		}
		
		accel_actions = {
			"open" : None,
			"paste" : None,
			"remove" : "Delete",
			"clear" : "<ctrl>Delete",
			"quit" : None,
			"go-next" : "Page_Down",
			"go-previous" : "Page_Up",
			"go-first" : "Home",
			"go-last" : "End",
			"zoom-none" : "KP_0",
			"zoom-in" : "KP_Add",
			"zoom-out" : "KP_Subtract",
			"auto-zoom-enable" : "KP_Multiply",
			"rotate-cw" : "R",
			"rotate-ccw" : "<ctrl>R",
			"flip-h" : "F",
			"flip-v" : "<ctrl>F",
			"fullscreen" : "F4",
		}
		
		for name, label, tip, stock in action_params:
			some_signal_params = signaling_params.get(name, None)
			if name in toggleable_actions:
				# Toggleable actions :D
				group_data = toggleable_actions[name]
				if group_data is None:
					# No group data = ToggleAction
					signal_name = "toggled"
					an_action = Gtk.ToggleAction(name, label, tip, stock)
				else:
					# Group data = RadioAction
					signal_name = "changed"
					radio_value, group_list = group_data
					an_action = Gtk.RadioAction(name, label, tip, stock,
					                            radio_value)
					# Join the group of last radioaction in the list
					if group_list:
						an_action.join_group(group_list[-1])
					group_list.append(an_action)
			else:
				# Non-rare kind of action
				signal_name = "activate"
				an_action = Gtk.Action(name, label, tip, stock)
			
			# Set signal
			if some_signal_params:
				an_action.connect(signal_name, *some_signal_params)
			
			# Add to action group
			try:
				an_accel = accel_actions[name]
			except KeyError:
				self.actions.add_action(an_action)
			else:
				self.actions.add_action_with_accel(an_action, an_accel)

		
	# --- event handling down this line --- #
	def connect_to_statusbar(self, action, proxy):
		''' Connects an action's widget proxy enter-notify-event to show the
		    action tooltip on the statusbar when the widget is hovered '''
		    
		try:
			# Connect select/deselect events
			proxy.connect("select", self._tooltip_to_statusbar, action)
			proxy.connect("deselect", self._pop_tooltip_from_statusbar)
			
		except TypeError: # Not a menu item
			pass
			
	def _tooltip_to_statusbar(self, proxy, action):
		''' Pushes a proxy action tooltip to the statusbar '''
		tooltip = action.get_tooltip()
		if tooltip:
			context_id = self.statusbar.get_context_id("tooltip")
			self.statusbar.pop(context_id)
			self.statusbar.push(context_id, tooltip)
			
	
	def _pop_tooltip_from_statusbar(self, *data):
		context_id = self.statusbar.get_context_id("tooltip")
		self.statusbar.pop(context_id)
	
	
	def _changed_ordering_mode(self, *data):
		#TODO: Use GObject.bind_property_with_closure for this
		new_comparer = organization.SortingKeys.Enum[self.ordering_mode]
		if self.album.comparer != new_comparer:
			self.album.comparer = new_comparer
			
			if not self.album.autosort:
				self.album.sort()
	
	
	def _changed_album_comparer(self, album, *data):
		sorting_keys_enum = organization.SortingKeys.Enum
		ordering_mode = sorting_keys_enum.index(album.comparer)
		
		self.ordering_mode = ordering_mode
	
		
	def _toggled_reverse_sort(self, *data):
		if not self.album.autosort:
			self.album.sort()

	
	def _layout_option_chosen(self, radio_action, current_action):
		''' Sets the layout-option property from the menu choices '''
		current_value = current_action.get_current_value()
		
		if current_value >= 0:
			self.layout_option = extending.LayoutOption.List[current_value]

	
	def _changed_layout_option(self, *data):
		''' layout-option handler '''
		current_layout = self.avl.layout
		if not current_layout \
		   or current_layout.source_option != self.layout_option:
			self.avl.layout = self.layout_option.create_layout()


	def _layout_changed(self, *args):
		''' Handles a layout change in the avl  '''
		layout = self.avl.layout
		
		try:
			if self.layout_option != layout.source_option:
				self.layout_option = layout.source_option
				
		except Exception:
			pass
			
		# Refresh the layout options
		option_list = extending.LayoutOption.List
		other_option = self.actions.get_action("layout-other-option")
		try:
			option_index = option_list.index(layout.source_option)
			
		except Exception:
			# The layout is not on the index, so we do something with the menu
			other_option.set_current_value(-1)
			
		else:
			# The layout is on the index, so we update the menu
			other_option.set_current_value(option_index)
			
		# Destroy a possibly open layout settings dialog
		if self.layout_dialog:
			self.layout_dialog.destroy()
			self.layout_dialog = None
			
		# Turn "configure" menu item insensitive if the layout
		# doesn't have a settings widget
		configure = self.actions.get_action("layout-configure")
		configure.set_sensitive(layout.has_settings_widget)
		
		# Remove previosly merged ui from the menu
		if self._layout_action_group:
			self.uimanager.remove_action_group(self._layout_action_group)
			self.uimanager.remove_ui(self._layout_ui_merge_id)
			self._layout_ui_merge_id = None
		
		# Merge ui from layout
		self._layout_action_group = layout.ui_action_group
		if self._layout_action_group:
			self.uimanager.insert_action_group(self._layout_action_group, -1)
			merge_id = self.uimanager.new_merge_id()
			try:
				layout.add_ui(self.uimanager, merge_id)
				
			except Exception:
				notification.log_exception("Error adding layout UI")
				self._layout_action_group = None
				self.uimanager.remove_ui(merge_id)
				
			else:
				self._layout_ui_merge_id = merge_id
		
		
	def _toggled_vscroll(self, action, *data):
		left = self.actions.get_action("ui-scrollbar-left")
		right = self.actions.get_action("ui-scrollbar-right")
		if left.get_active() and right.get_active():
			if action is left:
				right.set_active(False)
				
			else:
				left.set_active(False)
				
		new_value = 2 if right.get_active() else 1 if left.get_active() else 0
		self.vscrollbar_placement = new_value
	
		
	def _toggled_hscroll(self, action, *data):
		top = self.actions.get_action("ui-scrollbar-top")
		bottom = self.actions.get_action("ui-scrollbar-bottom")
		if top.get_active() and bottom.get_active():
			if action is top:
				bottom.set_active(False)
				
			else:
				top.set_active(False)
		
		new_value = 2 if bottom.get_active() else 1 if top.get_active() else 0
		self.hscrollbar_placement = new_value


	def _changed_scrollbars(self, *data):
		h = self.hscrollbar_placement
		v = self.vscrollbar_placement
		
		# Refresh actions
		actions = [
			self.actions.get_action("ui-scrollbar-top"),
			self.actions.get_action("ui-scrollbar-right"),
			self.actions.get_action("ui-scrollbar-bottom"),
			self.actions.get_action("ui-scrollbar-left")
		]
		for an_action in actions:
			an_action.block_activate()
		
		top, right, bottom, left = actions
		left.set_active(v == 1)
		right.set_active(v == 2)
		top.set_active(h == 1)
		bottom.set_active(h == 2)
		
		for an_action in actions:
			an_action.unblock_activate()
		
		# Update scrollbars
		hpolicy = Gtk.PolicyType.NEVER if h == 0 else Gtk.PolicyType.AUTOMATIC
		vpolicy = Gtk.PolicyType.NEVER if v == 0 else Gtk.PolicyType.AUTOMATIC
		
		# This placement is the placement of the scrolled window 
		# child widget in comparison to the scrollbars.
		# Basically everything is inverted and swapped.
		if h == 2:
			# horizontal scrollbar at bottom
			if v == 2:
				# vertical scrollbar at right
				placement = Gtk.CornerType.TOP_LEFT
			else:
				placement = Gtk.CornerType.TOP_RIGHT
				
		else:
			if v == 2:
				placement = Gtk.CornerType.BOTTOM_LEFT
			else:
				placement = Gtk.CornerType.BOTTOM_RIGHT
		
		self.view_scroller.set_policy(hpolicy, vpolicy)
		self.view_scroller.set_placement(placement)

	
	def magnification_changed(self, widget, data=None):
		self.auto_zoom_zoom_modified = True
		
	def view_changed(self, widget, data):
		self._refresh_transform.queue()
	
	def reapply_auto_zoom(self, *data):
		if self.auto_zoom_enabled and not self.auto_zoom_zoom_modified:
			self.auto_zoom()

		
	def _refresh_index(self):
		focused_image = self.avl.focus_image
		can_remove = not focused_image is None
		can_goto_first = False
		can_goto_last = False
		can_previous = False
		can_next = False
			
		if self.album:
			can_remove = True
			
			count = len(self.album)
			count_chr_count = len(str(count))
			
			if focused_image in self.album:
				image_index = self.album.index(focused_image)
				can_goto_first = image_index != 0
				can_goto_last = image_index != count - 1
				can_previous = True
				can_next = True
				
				index_text = str(image_index + 1).zfill(count_chr_count)
				
				index_fmt = _("#{index}/{count:d}") 
				label_text = index_fmt.format(index=index_text, count=count)
				self.index_label.set_text(label_text)
			else:
				can_goto_first = True
				can_goto_last = True
				
				question_marks = _("?") * count_chr_count
				index_fmt = _("{question_marks}/{count:d}")
				label_text = index_fmt.format(question_marks=question_marks,
				                              count=count)
				self.index_label.set_text(label_text)
		else:
			self.index_label.set_text("∅")
			
		sensible_list = [
			("remove", can_remove),
			("clear", len(self.album) > 0),
			("go-next", can_next),
			("go-previous", can_previous),
			("go-first", can_goto_first),
			("go-last", can_goto_last),
			("go-random", len(self.album) > 1)
		]
		
		for action_name, sensitivity in sensible_list:
			self.actions.get_action(action_name).set_sensitive(sensitivity)
		
	def _refresh_transform(self):
		focused_image = self.avl.focus_image
		if focused_image:
			if focused_image.is_bad:
				# This just may happen
				status_text = _("Error")
				status_tooltip_text = _("Something went wrong")
				size_text = ""
				
			elif focused_image.on_memory:
				metadata = focused_image.metadata
				# The width and height are from the source
				size_text = "{width}×{height}".format(
					width=metadata.width, height=metadata.height
				)
				
				status_text, status_tooltip_text = "", ""
				                                
			else:
				# If it's not on memory and then it must be loading
				status_text = _("Loading")
				status_tooltip_text = _("Please wait...")
				size_text = ""
				
			# Set zoom text for zoom label
			mag = round(self.view.magnification, 3)
			if mag:
				zoom_text = _("{zoom:n}×").format(zoom=mag)
				
			else:
				zoom_text = ""
			
			# Set flip symbol for flip label and adjust rotation variable
			rot = self.view.rotation
			hflip, vflip = self.view.flipping
			if hflip or vflip:
				# If the view is flipped in either direction apply this
				# intricate looking math stuff to rotation. Normally, there
				# would be another expression if both are true, but in that
				# is handled beforehand by rotating the view by 180°
				    
				#rot = (rot + (45 - ((rot + 45) % 180)) * 2) % 360
				
				if hflip:
					flip_text = "↔"
					
				else:
					flip_text = "↕"
					
			else:
				flip_text = ""
				
			# Format angle text for label
			if rot:
				angle_text = _("{degrees:d}°").format(degrees=int(rot))
				
			else:
				angle_text = ""
				
			
			# Set label text, hide labels without text
			self.status_label.set_text(status_text)
			self.status_label.set_tooltip_text(status_tooltip_text)
			
			self.size_label.set_text(size_text)
			self.zoom_label.set_text(zoom_text)
			self.angle_label.set_text(angle_text)
			self.flip_label.set_text(flip_text)
			
			self.status_label.set_visible(bool(status_text))			
			self.size_label.set_visible(bool(size_text))
			self.zoom_label.set_visible(bool(zoom_text))
			self.angle_label.set_visible(bool(angle_text))
			self.flip_label.set_visible(bool(flip_text))
			
		else:
			# Set the status label to "Nothing" and hide all other labels
			# since there is nothing to transform
			
			self.status_label.set_text(_("Nothing"))
			self.status_label.set_tooltip_text(_("Nothing to see here"))
			self.status_label.show()
			
			self.size_label.hide()
			self.zoom_label.hide()
			self.angle_label.hide()
			self.flip_label.hide()
			
	def set_view_rotation(self, angle):
		anchor = self.view.get_widget_point()
		pin = self.view.get_pin(anchor)
		self.view.rotation = angle % 360
		self.view.adjust_to_pin(pin)
	
	def set_view_zoom(self, magnification):
		anchor = self.view.get_widget_point()
		pin = self.view.get_pin(anchor)
		self.view.magnification = magnification
		self.view.adjust_to_pin(pin)
		
	def set_view_flip(self, horizontal, vertical):
		hflip, vflip = self.view.flipping
		
		if hflip != horizontal or vflip != vertical:
			# ih8triGNOMEtricks
			rot = self.view.rotation
			angle_change = (45 - ((rot + 45) % 180)) * 2
		
			# If the image if flipped both horizontally and vertically
			# Then it is rotated 180 degrees
			if horizontal and vertical:
				horizontal = vertical = False
				angle_change += 180
		
			anchor = self.view.get_widget_point()
			pin = self.view.get_pin(anchor)
			if angle_change:
				self.view.rotation = (rot + angle_change) % 360
			
			self.view.flipping = (horizontal, vertical)
			self.view.adjust_to_pin(pin)
		
	def zoom_view(self, power):
		''' Zooms the viewport '''		
		zoom_effect = self.app.zoom_effect
		if zoom_effect and power:
			old_zoom = self.view.magnification
			new_zoom = self.app.zoom_effect ** power * old_zoom
			self.set_view_zoom(new_zoom)
			
	def flip_view(self, vertically):
		''' Flips the viewport '''
		# Horizontal mirroring depends on the rotation of the image
		hflip, vflip = self.view.flipping
		if vertically:
			vflip = not vflip
		else:
			hflip = not hflip
		
		self.set_view_flip(hflip, vflip)
		
	def rotate_view(self, effect):
		''' Rotates the viewport '''
		change = self.app.spin_effect * effect
		if change < 0:
			change += (change // 360) * -360
			
		if change:
			self.set_view_rotation(self.view.rotation + change)
	
	def reset_view_transform(self):
		self.set_view_flip(False, False)
		self.set_view_rotation(0)
	
	def auto_zoom(self):
		''' Zooms automatically! '''
		
		frame = self.avl.focus_frame
		if frame and (self.auto_zoom_magnify or self.auto_zoom_minify):
			new_zoom = self.view.zoom_for_size(
			                      frame.size, self.auto_zoom_mode)
			                      
			if (new_zoom > 1 and self.auto_zoom_magnify) or \
			   (new_zoom < 1 and self.auto_zoom_minify):
				self.view.magnification = new_zoom
				self.auto_zoom_zoom_modified = False
			else:
				self.view.magnification = 1
					
	def change_auto_zoom(self, *data):
		mode = self.actions.get_action("auto-zoom-fit").get_current_value()
		magnify = self.actions.get_action("auto-zoom-magnify").get_active()
		minify = self.actions.get_action("auto-zoom-minify").get_active()
		enabled = self.actions.get_action("auto-zoom-enable").get_active()
		
		self.auto_zoom_magnify = magnify
		self.auto_zoom_minify = minify
		self.auto_zoom_mode = mode
		self.auto_zoom_enabled = enabled
		if self.auto_zoom_enabled:
			self.auto_zoom()
	
	
	def toggle_keep_above(self, *data):
		keep_above = self.actions.get_action("ui-keep-above")
		keep_below = self.actions.get_action("ui-keep-below")
		if keep_above.get_active() and keep_below.get_active():
			keep_below.set_active(False)
			
		self.set_keep_above(keep_above.get_active())
				
	def toggle_keep_below(self, *data):
		keep_above = self.actions.get_action("ui-keep-above")
		keep_below = self.actions.get_action("ui-keep-below")
		if keep_below.get_active() and keep_above.get_active():
			keep_above.set_active(False)
			
		self.set_keep_below(keep_below.get_active())
		
			
	def toggle_fullscreen(self, data=None):
		# This simply tries to fullscreen / unfullscreen
		fullscreenaction = self.actions.get_action("fullscreen")
		
		if fullscreenaction.get_active():
			self.fullscreen()
		else:
			self.unfullscreen()
	
	# --- Go go go!!! --- #
	def go_next(self, *data):
		self.avl.go_next()
		
	def go_previous(self, *data):
		self.avl.go_previous()
			
	def go_first(self, *data):
		self.avl.go_index(0)
		
	def go_last(self, *data):
		self.avl.go_index(-1)
		
	def go_random(self, *data):
		image_count = len(self.album)
		if image_count > 1:
			# Gets a new random index that is not the current one
			random_int = random.randint(0, image_count - 2)
			image_index = self.avl.album.index(self.avl.focus_image)
			if random_int >= image_index:
				random_int += 1
			
			self.avl.go_index(random_int)
			
	def handle_clear(self, *data):
		del self.album[:]
		
	def handle_remove(self, *data):
		focus = self.avl.focus_image
		if focus:
			self.album.remove(focus)
	
	def pasted_data(self, data=None):
		self.go_new = True
		some_uris = self.clipboard.wait_for_uris()
		
		if some_uris:
			self.app.open_files_for_album(self.album, uris=some_uris)
			
		some_pixels = self.clipboard.wait_for_image()
		if some_pixels:
			new_images = self.app.load_pixels(some_pixels)
			if new_images:
				self.album.extend(new_images)
				
		self.go_new = False
			
	def dragged_data(self, widget, context, x, y, selection, info, timestamp):
		self.go_new = True
		if info == DND_URI_LIST:
			some_uris = selection.get_uris()
			if some_uris:
				self.app.open_files_for_album(self.album, uris=some_uris,
				                                   search=len(some_uris) == 1,
				                                   replace=True)
				                                   
		elif info == DND_IMAGE:
			some_pixels = selection.get_pixbuf()
			if some_pixels:
				new_images = self.app.load_pixels(some_pixels)
				if new_images:
					self.album.extend(new_images)
					
		self.go_new = False
								
	def file_open(self, widget, data=None):
		self.app.open_image_dialog(self.album, self)
		
	def show_layout_dialog(self, *data):
		''' Shows a dialog with the layout settings widget '''
		
		if self.layout_dialog:
			self.layout_dialog.present()
			
		else:
			layout = self.avl.layout
			flags = Gtk.DialogFlags
			try:
				widget = layout.create_settings_widget()
				widget.connect("destroy", self._layout_widget_destroyed, layout)
				
			except Exception:
				message = _("Could not create layout settings dialog!")
				dialog = Gtk.MessageDialog(self,
				             flags.MODAL | flags.DESTROY_WITH_PARENT,
					         Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
					         message)
					         
				notification.log_exception(message)
				dialog.run()
				dialog.destroy()
			
			else:
				dialog = Gtk.Dialog(_("Layout Settings"), self,
					     flags.DESTROY_WITH_PARENT,
					     (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
				
				widget_pad = utility.PadDialogContent(widget)
				widget_pad.show()
				
				content_area = dialog.get_content_area()
				content_area.pack_start(widget_pad, True, True, 0)
				
				dialog.connect("response", self._layout_dialog_response)
				dialog.present()
				
				self.layout_dialog = dialog


	def _layout_widget_destroyed(self, widget, layout):
		layout.save_preferences()


	def _layout_dialog_response(self, *data):
		self.layout_dialog.destroy()
		self.layout_dialog = None

	
	''' Methods after this comment are actually kind of a big deal.
	    Do not rename them. '''
	
	def refresh_title(self, image=None):
		if image:
			if image.name == image.fullname:
				title_fmt = _("“{name}” - Pynorama")
			else:
				title_fmt = _("“{name}” [“{fullname}”] - Pynorama")
				
			new_title = title_fmt.format(
			                  name=image.name, fullname=image.fullname)
			self.set_title(new_title)
			
		else:
			self.set_title(_("Pynorama"))
			
	
	def do_destroy(self, *data):
		# Saves this window preferences
		preferences.SaveFromWindow(self)
		preferences.SaveFromAlbum(self.album)
		preferences.SaveFromView(self.view)
		try:
			# Tries to save the layout preferences
			self.avl.layout.save_preferences()
			
		except Exception:
			pass
		
		# Clean up the avl
		self.avl.clean()
		return Gtk.Window.do_destroy(self)
		
	
	def _image_added(self, album, image, index):
		image.lists += 1
		self._refresh_index.queue()
		
		if self.go_new:
			self.go_new = False
			self.avl.go_image(image)
			
		elif self.avl.focus_image is None:
			self.avl.go_image(image)
		
	def _image_removed(self, album, image, index):
		image.lists -= 1
		self._refresh_index.queue()
		
	def _album_order_changed(self, album):
		self._refresh_index.queue()


	def _focus_changed(self, avl, focused_image, hint):
		if self._focus_loaded_handler_id:
			self._old_focused_image.disconnect(self._focus_loaded_handler_id)
			self._focus_loaded_handler_id = None
		
		self._old_focused_image = focused_image
		self._focus_hint = hint
		
		self._refresh_index.queue()
		self.refresh_title(focused_image)
		
		loading_ctx = self.statusbar.get_context_id("loading")
		self.statusbar.pop(loading_ctx)
		
		if focused_image:
			if focused_image.on_memory or focused_image.is_bad:
				self.loading_spinner.hide()
				self.loading_spinner.stop()
				
				# Show error in status bar #
				if focused_image.error:
					message = notification.Lines.Error(focused_image.error)
					self.statusbar.push(loading_ctx, message)
					
				# Refresh frame #
				self._refresh_focus_frame()
			
			else:				
				# Show loading hints #
				message = notification.Lines.Loading(focused_image)
				self.statusbar.push(loading_ctx, message)
				self.loading_spinner.show()
				self.loading_spinner.start() # ~like a record~
				
				self._refresh_transform.queue()
				
				self._focus_loaded_handler_id = focused_image.connect(
					"finished-loading", self._focus_loaded
				)
		else:
			self.loading_spinner.hide()
			self.loading_spinner.stop()
			
	def _focus_loaded(self, image, error):
		focused_image = self.avl.focus_image
		if focused_image == image:
			# Hide loading hints #
			loading_ctx = self.statusbar.get_context_id("loading")
			self.statusbar.pop(loading_ctx)
			self.loading_spinner.hide()
			self.loading_spinner.stop()
			
			# Show error in status bar #
			if error:
				message = notification.Lines.Error(error)
				self.statusbar.push(loading_ctx, message)
				
			# Refresh frame #
			self._refresh_focus_frame()
				
		self._old_focused_image.disconnect(self._focus_loaded_handler_id)
		self._focus_loaded_handler_id = None
		
	def _refresh_focus_frame(self):
		if not self._focus_hint:
			if self.auto_zoom_enabled:
				self.auto_zoom()
				
			self._focus_hint = True
			
		self._refresh_transform.queue()
	
	#--- Properties down this line ---#
	
	view = GObject.Property(type=viewing.ImageView)
	album = GObject.Property(type=organization.Album)
	
	sort_automatically = GObject.Property(type=bool, default=True)
	ordering_mode = GObject.Property(type=int, default=0)
	reverse_ordering = GObject.Property(type=bool, default=False)
	
	toolbar_visible = GObject.Property(type=bool, default=True)
	statusbar_visible = GObject.Property(type=bool, default=True)
	hscrollbar_placement = GObject.Property(type=int, default=1) 
	vscrollbar_placement = GObject.Property(type=int, default=1)
	
	layout_option = GObject.Property(type=object)
	
	def get_auto_zoom(self):
		enabled = self.actions.get_action("auto-zoom-enable").get_active()
		minify = self.actions.get_action("auto-zoom-minify").get_active()
		magnify = self.actions.get_action("auto-zoom-magnify").get_active()
		return enabled, minify, magnify
		
	def set_auto_zoom(self, enabled, minify, magnify):
		self.actions.get_action("auto-zoom-minify").set_active(minify)
		self.actions.get_action("auto-zoom-magnify").set_active(magnify)
		self.actions.get_action("auto-zoom-enable").set_active(enabled)
		
	def get_auto_zoom_mode(self):
		return self.actions.get_action("auto-zoom-fit").get_current_value()
	def set_auto_zoom_mode(self, mode):
		self.actions.get_action("auto-zoom-fit").set_current_value(mode)
		
	def get_fullscreen(self):
		return self.actions.get_action("fullscreen").get_active()
		
	def set_fullscreen(self, value):
		self.actions.get_action("fullscreen").set_active(value)
	
	ui_description = '''\
<ui>
	<menubar>
		<menu action="file">
			<menuitem action="open" />
			<menuitem action="paste" />
			<separator />
			<menu action="ordering">
				<menuitem action="sort" />
				<separator />
				<menuitem action="sort-auto" />
				<menuitem action="sort-reverse" />
				<separator />
				<menuitem action="sort-name" />
				<menuitem action="sort-char" />
				<separator />
				<menuitem action="sort-file-date" />
				<menuitem action="sort-file-size" />
				<separator />
				<menuitem action="sort-img-size" />
				<menuitem action="sort-img-width" />
				<menuitem action="sort-img-height" />
			</menu>
			<separator />
			<menuitem action="remove" />
			<menuitem action="clear" />
			<separator />
			<menuitem action="quit" />
		</menu>
		<menu action="go">
			<menuitem action="go-next" />
			<menuitem action="go-previous" />
			<separator />
			<menuitem action="go-first" />
			<menuitem action="go-last" />
			<separator />
			<menuitem action="go-random" />
		</menu>
		<menu action="view">
			<menuitem action="zoom-in" />
			<menuitem action="zoom-out" />
			<menuitem action="zoom-none" />
			<menu action="auto-zoom" >
				<menuitem action="auto-zoom-enable" />
				<separator />
				<menuitem action="auto-zoom-fit" />
				<menuitem action="auto-zoom-fill" />
				<menuitem action="auto-zoom-match-width" />
				<menuitem action="auto-zoom-match-height" />
				<separator />
				<menuitem action="auto-zoom-magnify" />
				<menuitem action="auto-zoom-minify" />
			</menu>
			<separator />
			<menu action="transform">
				<menuitem action="rotate-ccw" />
				<menuitem action="rotate-cw" />
				<separator />
				<menuitem action="flip-h" />
				<menuitem action="flip-v" />
				<separator />
				<menuitem action="transform-reset" />
			</menu>
			<menu action="interpolation">
				<menuitem action="interp-nearest" />
				<menuitem action="interp-bilinear" />
				<separator />
				<menuitem action="interp-fast" />
				<menuitem action="interp-good" />
				<menuitem action="interp-best" />
			</menu>
			<separator />
			<menu action="layout">
				<placeholder name="layout-options"/>
				<separator />
				<menuitem action="layout-configure" />
				<separator />
				<placeholder name="layout-configure-menu"/>
			</menu>
			<menu action="interface">
				<menuitem action="ui-toolbar" />
				<menuitem action="ui-statusbar" />
				<separator />
				<menuitem action="ui-scrollbar-top" />
				<menuitem action="ui-scrollbar-bottom" />
				<menuitem action="ui-scrollbar-left" />
				<menuitem action="ui-scrollbar-right" />
				<separator />
				<menuitem action="ui-keep-above" />
				<menuitem action="ui-keep-below" />
			</menu>
			<menuitem action="fullscreen" />
			<separator />
			<menuitem action="preferences" />
		</menu>
		<menu action="help">
			<menuitem action="about" />
		</menu>
	</menubar>
	<toolbar>
		<toolitem action="open" />
		<toolitem action="paste" />
		<separator />
		<toolitem action="go-previous" />
		<toolitem action="go-next" />
		<separator/>
		<toolitem action="zoom-in" />
		<toolitem action="zoom-out" />
		<separator />
		<toolitem action="preferences" />
		<separator />
		<toolitem action="fullscreen" />
		<toolitem action="about" />
	</toolbar>
</ui>'''
	
if __name__ == "__main__":
	# Run the program
	app = ImageViewer()
	app.run(sys.argv)
