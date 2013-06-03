''' organization.py contains code about collections of images. '''

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
    
import os
from gi.repository import GLib, GObject
from collections import MutableSequence

class Album(GObject.Object):
	''' It organizes images '''
	
	__gsignals__ = {
		"image-added" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"image-removed" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"order-changed" : (GObject.SIGNAL_RUN_FIRST, None, []),
	}
	def __init__(self):
		GObject.GObject.__init__(self)
		MutableSequence.__init__(self)
		
		self.connect("notify::reverse", self.__queue_autosort)
		self.connect("notify::autosort", self.__queue_autosort)
		self.connect("notify::comparer", self.__queue_autosort)
		
		self._store = []
		self.__autosort_signal_id = None
		
	# --- Mutable sequence interface down this line ---#
	def __len__(self):
		return len(self._store)
		
	def __getitem__(self, item):
		return self._store[item]
		
	def __setitem__(self, item, value):
		self._store[item] = value
		
	def __delitem__(self, item):
		if isinstance(item, slice):
			indices = item.indices(len(self._store))
			removed_indices = []
			for i in range(*indices):
				if item.step and item.step < 0:
					removed_indices.append(i)
				else:
					removed_indices.append(i - len(removed_indices))
					
			removed_images = self._store[item]
			del self._store[item]
			
			for i in range(len(removed_indices)):
				image, index = removed_images[i], removed_indices[i]
				self.emit("image-removed", image, index)
		else:
			image = self._store.pop(item)
			self.emit("image-removed", image, item)
	
	def insert(self, index, image):
		self._store.insert(index, image)
		self.emit("image-added", image, index)
		self.__queue_autosort()
	
	# --- "inheriting" down this line --- #
	
	__contains__ = MutableSequence.__contains__
	__iter__ = MutableSequence.__iter__
	__reversed__ = MutableSequence.__reversed__
	
	append = MutableSequence.append
	count = MutableSequence.count
	extend = MutableSequence.extend
	index = MutableSequence.index
	pop = MutableSequence.pop
	remove = MutableSequence.remove
	reverse = MutableSequence.reverse
	
	def sort(self):
		if self.__autosort_signal_id:
			GLib.source_remove(self.__autosort_signal_id)
			self.__autosort_signal_id = None
		
		if self.sort_list(self._store):
			self.emit("order-changed")
	
	def sort_list(self, a_list):
		if self.comparer and len(a_list) > 1:
			a_list.sort(key=self.comparer, reverse=self.reverse)
			return True
			
		else:
			return False
	
	def next(self, image):
		''' Returns the image after the input '''
		index = self._store.index(image)
		return self._store[(index + 1) % len(self._store)]
		
	def previous(self, image):
		''' Returns the image before the input '''
		index = self._store.index(image)
		return self._store[(index - 1) % len(self._store)]		
	
	def around(self, image, forward, backwards):
		''' Returns "forward" images after "image" and
		    "backwards" images before "image".
		    This method cycles around the list '''
		result = []
		if forward or backwards:
			start = self._store.index(image)
			count = len(self._store)
		
			for i in range(1, 1 + forward):
				result.append(self._store[(start + i) % count])
			
			for i in range(1, 1 + backwards):
				result.append(self._store[(start - i) % count])
			
		return result
	
	# --- properties down this line --- #
	
	autosort = GObject.property(type=bool, default=False)
	comparer = GObject.property(type=object, default=None)
	reverse = GObject.property(type=bool, default=False)
	
	def __queue_autosort(self, *data):
		if self.autosort and not self.__autosort_signal_id:
			self.__autosort_signal_id = GLib.idle_add(
			    self.__do_autosort, priority=GLib.PRIORITY_HIGH+10)
	
	def __do_autosort(self):
		self.__autosort_signal_id = None
		if self.autosort:
			self.sort()
		
		return False
		
class SortingKeys:
	''' Contains functions to get keys in images for sorting them '''
	
	@staticmethod
	def ByName(image):
		return GLib.utf8_collate_key_for_filename(image.fullname, -1)
		
	@staticmethod
	def ByCharacters(image):
		return image.fullname.lower()
			
	@staticmethod
	def ByFileSize(image):
		return image.get_metadata().data_size
		
	@staticmethod
	def ByFileDate(image):
		return image.get_metadata().modification_date
		
	@staticmethod
	def ByImageSize(image):
		return image.get_metadata().get_area()
		
	@staticmethod
	def ByImageWidth(image):
		return image.get_metadata().width
		
	@staticmethod
	def ByImageHeight(image):
		return image.get_metadata().height

from gi.repository import Gtk
import viewing

class AlbumViewLayout(GObject.Object):
	''' Used to tell layouts the album used for a view
	    Layouts should store data in this thing
	    Just call this avl for short '''
    
	__gsignals__ = {
		"focus-changed" : (GObject.SIGNAL_RUN_FIRST, None, [object])
	}
    
	def __init__(self, album, view, layout):
		GObject.Object.__init__(self)
		self.__is_clean = True
		self.__old_view = self.__old_album = self.__old_layout = None
		
		self.connect("notify::layout", self._layout_changed)
		
		self.layout = layout
		self.album = album
		self.view = view
	
	@property	
	def focus_image(self):
		return self.layout.get_focus_image(self)
	
	@property
	def focus_frame(self):
		return self.layout.get_focus_frame(self)
	
	def go_index(self, index):
		self.layout.go_image(self, self.album[index])
		
	def go_image(self, image):
		self.layout.go_image(self, image)
	
	def go_next(self):
		self.layout.go_next(self)
	
	def go_previous(self):
		self.layout.go_previous(self)
	
	def clean(self):
		if not self.__is_clean:
			self.__old_layout.clean(self)
			self.__is_clean = True
	
	def _layout_changed(self, *data):
		if self.__old_layout:
			self.clean()
		
		self.__old_layout = self.layout
		if self.layout:
			self.__is_clean = False
			self.layout.start(self)
		
	album = GObject.property(type=object, default=None)
	view = GObject.property(type=object, default=None)
	layout = GObject.property(type=object, default=None)
	
class AlbumLayout:
	''' Layout for an album '''
	def __init__(self):
		pass
	
	def get_focus_image(self, avl):
		''' Returns the image in focus '''
		raise NotImplementedError
	
	def get_focus_frame(self, avl):
		''' Returns the frame in focus '''
		raise NotImplementedError
				
	def go_image(self, avl, image):
		''' Lays out an image '''
		raise NotImplementedError
	
	def go_next(self, avl):
		focus = avl.focus_image
		next_image = avl.album.next(focus)
		avl.go_image(next_image)
	
	def go_previous(self, avl):
		focus = avl.focus_image
		previous_image = avl.album.previous(focus)
		avl.go_image(previous_image)		
		
	def start(self, avl):
		''' Set any initial variables in an AlbumViewLayout '''
		pass
		
	def clean(self, avl):
		''' Reverse whatever was done at start '''
		pass
	
	def update_setup(self, avl):
		pass
		
class SingleFrameLayout(AlbumLayout):
	''' Shows a single album image in a view '''
	def __init__(self):
		pass
	
	def start(self, avl):
		avl.current_image = None
		avl.current_frame = None
		avl.load_handle = None
		avl.old_album = None
		avl.removed_signal_id = None
		avl.album_notify_id = avl.connect(
		                          "notify::album", self._album_changed, avl)
		self._album_changed(avl)
		
	def clean(self, avl):
		if avl.load_handle:
			avl.current_image.disconnect(avl.load_handle)
		del avl.load_handle
		
		if avl.current_image:
			avl.current_image.uses -= 1
		del avl.current_image
		
		if avl.current_frame:
			avl.view.remove_frame(avl.current_frame)
		del avl.current_frame
		
		avl.disconnect(avl.album_notify_id)
		del avl.album_notify_id
		
		if not avl.old_album is None:
			avl.old_album.disconnect(avl.removed_signal_id)
			
		del avl.old_album
		del avl.removed_signal_id
			
	def get_focus_image(self, avl):
		return avl.current_image
	
	def get_focus_frame(self, avl):
		return avl.current_frame
	
	def go_image(self, avl, target_image):
		if avl.current_image == target_image:
			pass
			
		previous_image = avl.current_image
		avl.current_image = target_image
		
		if previous_image:
			previous_image.uses -= 1 # decrement use count
			if avl.load_handle: # remove "finished-loading" handle
				previous_image.disconnect(avl.load_handle)
				avl.load_handle = None
				
		if target_image is None:
			# Current image being none means nothing is displayed #
			self._refresh_frame(avl)
			
		else:
			target_image.uses += 1
			if target_image.on_memory or target_image.is_bad:
				self._refresh_frame(avl)
				
			else:
				avl.load_handle = avl.current_image.connect(
				                  "finished-loading", self._image_loaded, avl)
		
		avl.emit("focus-changed", avl.current_image)
		
	def _refresh_frame(self, avl):
		if avl.current_frame:
			avl.view.remove_frame(avl.current_frame)
			
		if avl.current_image:
			try:
				new_frame = avl.current_image.create_frame(avl.view)
				
			except Exception:
				new_frame = None
				
			finally:				
				if new_frame is None:
					# Create a missing icon frame #
					error_icon = avl.view.render_icon(Gtk.STOCK_MISSING_IMAGE,
						                              Gtk.IconSize.DIALOG)
						                            
					error_surface = viewing.SurfaceFromPixbuf(error_icon)
					new_frame = viewing.ImageSurfaceFrame(error_surface)
					
			avl.current_frame = new_frame
			avl.view.add_frame(new_frame)
	
	def _album_changed(self, avl, *data):
		if not avl.old_album is None:
			avl.old_album.disconnect(avl.removed_signal_id)
			avl.removed_signal_id = None
		
		avl.old_album = avl.album
		if not avl.album is None:
			avl.removed_signal_id = avl.album.connect(
			                        "image-removed", self._image_removed, avl)
			                        
	def _image_added(self, album, image, index, avl):
		pass
	
	def _image_removed(self, album, image, index, avl):
		if image == avl.current_image:
			count = len(album)
			if index <= count:
				if count >= 1:
					new_index = index - 1 if index == count else index
					new_image = album[new_index]
				else:
					new_image = None
					
				self.go_image(avl, new_image)
	
	def _image_loaded(self, image, error, avl):
		self._refresh_frame(avl)

class FrameStripLayout(AlbumLayout):
	''' Shows a strip of album images in a view '''
	def __init__(self):
		# Min number of pixels before and after the center image
		self.space_after = 3840
		self.space_before = 2560
		# Max number of images, has priority over min number of pixesl
		self.limit_after = 20
		self.limit_before = 10
		
	def start(self, avl):
		avl.center_index = avl.center_frame = avl.center_image = None
		avl.shown_images, avl.shown_frames = [], []
		avl.space_before = avl.space_after = 0
		avl.load_handles = {}
		
		avl.old_album = None
		avl.idle_update_sides_id = None
		avl.album_signals = []
		avl.album_notify_id = avl.connect(
		                          "notify::album", self._album_changed, avl)
		self._album_changed(avl)
		
	def clean(self, avl):
		for an_image in avl.shown_images:
			an_image.uses -= 1
			
		for a_frame in avl.shown_frames:
			if a_frame:
				avl.view.remove_frame(a_frame)
				
		for an_image, a_handle_id in avl.load_handles.items():
			an_image.disconnect(a_handle_id)				
		
		del avl.center_image, avl.center_frame
		del avl.shown_images, avl.shown_frames
		del avl.space_before, avl.space_after
		del avl.load_handles
		
		avl.disconnect(avl.album_notify_id)
		del avl.album_notify_id
		
		if not avl.old_album is None:
			for signal_id in avl.album_signals:
				avl.old_album.disconnect(signal_id)
		
		if avl.idle_update_sides_id:
			GLib.source_remove(avl.idle_update_sides_id)
			
		del avl.idle_update_sides_id
		del avl.old_album
		del avl.album_signals
			
	def get_focus_image(self, avl):
		return avl.center_image
	
	def get_focus_frame(self, avl):
		return avl.center_frame
	
	def go_next(self, avl):
		if avl.center_frame:
			new_index = avl.center_index + 1
			if new_index < len(avl.shown_images):
				avl.center_image = avl.shown_images[new_index]
				avl.center_frame = avl.shown_frames[new_index]
				avl.center_index = new_index
				avl.emit("focus-changed", avl.center_image)
				
			else:
				avl.center_image = None
				new_image = avl.album.next(avl.center_image)
				self._insert_image(avl, new_index, new_image)
				
			self._queue_update_sides(avl)
		
	def go_previous(self, avl):
		if avl.center_frame:
			new_index = avl.center_index - 1
			if new_index >= 0:
				avl.center_image = avl.shown_images[new_index]
				avl.center_frame = avl.shown_frames[new_index]
				avl.center_index = new_index
				avl.emit("focus-changed", avl.center_image)
				
			else:
				new_image = avl.album.previous(avl.center_image)
				avl.center_index = avl.center_frame = avl.center_image = None
				self._insert_image(avl, 0, new_image)
				
			self._queue_update_sides(avl)
			
	def go_image(self, avl, image):
		if avl.center_image is image:
			return
			
		self._clear_images(avl)
		avl.center_index = avl.center_image = avl.center_frame = None
		self._insert_image(avl, 0, image)
		
	def _album_changed(self, avl, *data):
		# Handler for album changes in avl
		if not avl.old_album is None:
			for signal_id in avl.album_signals:
				avl.old_album.disconnect(signal_id)
				
			avl.album_signals = None
			
		avl.old_album = avl.album
		if not avl.album is None:
			avl.album_signals = [
				avl.album.connect("image-removed", self._image_removed, avl),
				avl.album.connect("image-added", self._image_added, avl),
				avl.album.connect("order-changed", self._order_changed, avl),
			]
	
	def _image_added(self, album, image, index, avl):
		# Handles an iamge added to an album
		next = album.next(image)
		prev = album.previous(image)
		
		if prev is image or prev is next:
			prev = None
			
		if next is image:
			next = None
			
		if prev or next:
			change = 0
			inserted_prev = False
			for i in range(len(avl.shown_images)):
				j = i + change
				an_image = avl.shown_images[j]
				if an_image is next and not inserted_prev:
					self._insert_image(avl, j, image)
					change += 1
					inserted_prev = False
					
				elif an_image is prev:
					self._insert_image(avl, j + 1, image)
					change += 1
					inserted_prev = True
					
				else:
					inserted_prev = False
					
	def _image_removed(self, album, image, index, avl):
		# Handles an image removed from an album
		removed_frame = False
		while image in avl.shown_images:
			removed_index = avl.shown_images.index(image)
			self._remove_image(avl, removed_index)
			removed_frame = True
				
		if removed_frame:
			if image is avl.center_image:
				new_index = avl.center_index
				if new_index < len(avl.shown_images):
					avl.center_image = avl.shown_images[new_index]
					avl.center_frame = avl.shown_frames[new_index]
					avl.center_index = new_index
					avl.emit("focus-changed", avl.center_image)
			
				else:
					avl.center_index = None
					avl.center_frame = avl.center_image = None
					if avl.album:
						new_image = avl.album.next(avl.album[index - 1])
						self._insert_image(avl, new_index, new_image)
			
			self._queue_update_sides(avl)
			self._reposition_frames(avl)
	
	def _order_changed(self, album, avl):
		self._clear_images(avl)
		old_center_image = avl.center_image
		avl.center_index = avl.center_image = avl.center_frame = None
		self._insert_image(avl, 0, old_center_image)
	
	def _insert_image(self, avl, index, image):
		avl.shown_images.insert(index, image)
		avl.shown_frames.insert(index, None)
		
		image.uses += 1
		
		if not avl.center_image:
			avl.center_index = index
			avl.center_image = image
			avl.emit("focus-changed", image)
		
		elif index <= avl.center_index:
			avl.center_index += 1
		
		self._load_frame(avl, image)
	
	def _remove_image(self, avl, index):
		image = avl.shown_images.pop(index)
		frame = avl.shown_frames.pop(index)
		
		image.uses -= 1
		
		if index < avl.center_index:
			avl.center_index -= 1
		
		if frame:
			avl.view.remove_frame(frame)
	
	def _append_image(self, avl, image):
		self._insert_image(avl, len(avl.shown_images), image)
		
	def _prepend_image(self, avl, image):
		self._insert_image(avl, 0, image)
	
	def _clear_images(self, avl):
		while avl.shown_images:
			self._remove_image(avl, 0)
			
	def _load_frame(self, avl, image):
		if image.on_memory or image.is_bad:
			self._refresh_frames(avl, image)
			self._queue_update_sides(avl)
			
		else:
			load_handle_id = avl.load_handles.get(image, None)
			if not load_handle_id:
				load_handle_id = image.connect("finished-loading", 
				                               self._image_loaded, avl)
				avl.load_handles[image] = load_handle_id
				
	def _image_loaded(self, image, error, avl):
		load_handle_id = avl.load_handles.pop(image, None)
		if load_handle_id:
			image.disconnect(load_handle_id)
			
		if image in avl.shown_images:
			self._refresh_frames(avl, image)
			self._queue_update_sides(avl)
	
	# Use PRIORITY_DEFAULT_IDLE - 10 to create frames after they
	# are drawn but before they can be unloaded (avoiding having to reload
	# images after a _clear_images(...)
	def _queue_update_sides(self, avl):
		if not avl.idle_update_sides_id:
			avl.idle_update_sides_id = GLib.idle_add(
			                           self._idly_update_sides, avl,
			                           priority=GLib.PRIORITY_DEFAULT_IDLE - 10)
	
	def _idly_update_sides(self, avl):
		avl.idle_update_sides_id = None
		self._update_sides(avl)
	
	def _update_sides(self, avl):
		# Adds or removes images at either side
		if avl.idle_update_sides_id:
			GLib.source_remove(avl.idle_update_sides_id)
		
		if avl.center_frame and len(avl.album) > 1:
			self._compute_lengths(avl)
			
			before_count = avl.center_index
			after_count = len(avl.shown_images) - avl.center_index - 1
			
			while after_count > self.limit_after:
				avl.space_after -= self._get_length(avl.shown_frames[-1])
				self._remove_image(avl, len(avl.shown_frames) -1)
				after_count -= 1
				
			if after_count < self.limit_after:
				foremost_frame = avl.shown_frames[-1]
				if avl.space_after < self.space_after:
					if foremost_frame:
						foremost_image = avl.shown_images[-1]
						beyond_foremost_image = avl.album.next(foremost_image)
						self._append_image(avl, beyond_foremost_image)
				else:
					foremost_length = self._get_length(foremost_frame)
					while avl.space_after - foremost_length > self.space_after \
						  if foremost_frame \
						  else avl.space_after > self.space_after:
						self._remove_image(avl, len(avl.shown_frames) -1)
						avl.space_after -= foremost_length
						foremost_frame = avl.shown_frames[-1]
						foremost_length = self._get_length(foremost_frame)
			
			while before_count > self.limit_before:
				avl.space_before -= self._get_length(avl.shown_frames[0])
				self._remove_image(avl, 0)
				before_count -= 1
			
			if before_count < self.limit_before:
				backmost_frame = avl.shown_frames[0]
				if avl.space_before < self.space_before:	
					if backmost_frame:
						backmost_image = avl.shown_images[0]
						beyond_backmost_image = avl.album.previous(backmost_image)
						self._prepend_image(avl, beyond_backmost_image)
				else:
					backmost_length = self._get_length(backmost_frame)
					while avl.space_before - backmost_length > self.space_before \
						  if backmost_frame \
						  else avl.space_before > self.space_before:
						self._remove_image(avl, 0)
						avl.space_before -= backmost_length
						backmost_frame = avl.shown_frames[0]
						backmost_length = self._get_length(backmost_frame)
					
	def _refresh_frames(self, avl, image, overwrite=False):
		# Create frames to represent an image
		error_surface = None
		new_frames = []
		for i in range(len(avl.shown_images)):
			shown_image = avl.shown_images[i]
			if image is shown_image:
				shown_frame = avl.shown_frames[i]
				if not shown_frame or overwrite:
					try:
						shown_frame = image.create_frame(avl.view)
						
					except Exception:
						if not error_surface:
							pixbuf = avl.view.render_icon(
							                 Gtk.STOCK_MISSING_IMAGE,
							                 Gtk.IconSize.DIALOG)
							                 
							error_surface = viewing.SurfaceFromPixbuf(pixbuf)
							
						shown_frame = viewing.ImageSurfaceFrame(error_surface)
					
					self._set_frame(avl, i, shown_frame)
					new_frames.append(shown_frame)
					
		if new_frames:
			if image is avl.center_image and not avl.center_frame:
				avl.center_frame = new_frames[0]
			
			self._reposition_frames(avl)
		
	def _set_frame(self, avl, index, new_frame):
		old_frame = avl.shown_frames[index]
		if new_frame is not old_frame:
			if old_frame:
				avl.view.remove_frame(old_frame)
			
			avl.shown_frames[index] = new_frame
			if new_frame:
				avl.view.add_frame(new_frame)
	
	def _reposition_frames(self, avl):
		# Place frames around the center frame of images around the center image
		if avl.center_frame:
			side_ranges = (range(avl.center_index - 1, -1, -1),
			               range(avl.center_index + 1, len(avl.shown_frames)))
			               
			frame_placers = self._place_before, self._place_after
			
			for i in range(2):
				a_side_range = side_ranges[i]
				frame_beside = avl.center_frame
				a_frame_placer = frame_placers[i]
				for j in a_side_range:
					a_frame = avl.shown_frames[j]
					if a_frame:
						a_frame_placer(frame_beside, a_frame)
						frame_beside = a_frame
	
	def _compute_lengths(self, avl):
		# Recalculate the space used by images after and before the center image
		if avl.center_frame:
			side_ranges = (range(avl.center_index),
			               range(avl.center_index + 1, len(avl.shown_frames)))
			side_lengths = []
			
			for i in range(2):
				a_side_range = side_ranges[i]
				a_side_length = 0
				for j in a_side_range:
					a_frame = avl.shown_frames[j]
					if a_frame:
						a_side_length += self._get_length(a_frame)
				
				side_lengths.append(a_side_length)
				
			avl.space_before, avl.space_after = side_lengths
			
		else:
			avl.space_after = 0
			avl.space_before = 0
	
	def _place_after(self, frame, next_frame):
		rect = frame.rectangle.shift(frame.origin)
		
		next_rect = next_frame.rectangle
		ox, oy = next_frame.origin
		ox = rect.right - next_rect.left
		next_frame.origin = ox, oy
	
	def _place_before(self, frame, previous_frame):
		rect = frame.rectangle.shift(frame.origin)
		
		previous_rect = previous_frame.rectangle
		ox, oy = previous_frame.origin
		ox = rect.left - previous_rect.right
		previous_frame.origin = ox, oy
				
	def _get_length(self, frame):
		return frame.rectangle.width if frame else 0
