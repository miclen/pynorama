''' navigation.py defines viewing.py related navigation. '''

''' ...And this file is part of Pynorama.
    
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

from gi.repository import Gtk, Gdk, GLib, GObject
from gettext import gettext as _
import math, time
import point

class MouseAdapter(GObject.GObject):
	''' Adapts a widget mouse events '''
	EventMask = (Gdk.EventMask.BUTTON_PRESS_MASK |
	             Gdk.EventMask.BUTTON_RELEASE_MASK |
	             Gdk.EventMask.SCROLL_MASK |
	             Gdk.EventMask.SMOOTH_SCROLL_MASK |
	             Gdk.EventMask.ENTER_NOTIFY_MASK |
	             Gdk.EventMask.POINTER_MOTION_MASK |
	             Gdk.EventMask.POINTER_MOTION_HINT_MASK)
	
	# According to the docs, Gtk uses +10 for resizing and +20 for redrawing
	# +15 should dispatch events after resizing and before redrawing
	# TODO: Figure out whether that is a good idea
	IdlePriority = GLib.PRIORITY_HIGH_IDLE + 15
	
	__gsignals__ = {
		"motion" : (GObject.SIGNAL_RUN_FIRST, None, [object, object]),
		"drag" : (GObject.SIGNAL_RUN_FIRST, None, [object, object, int]),
		"pression" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"click" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"scroll" : (GObject.SIGNAL_RUN_FIRST, None, [object, object]),
		"start-dragging" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"stop-dragging" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
	}
	
	def __init__(self, widget=None):
		GObject.GObject.__init__(self)
		
		self.__from_point = None
		self.__pressure = dict()
		self.__widget = None
		
		self.__delayed_motion_id = None
		self.__widget_handler_ids = None
		self.__ice_cubes = 0
		self.__motion_from_outside = 2
		self.__pressure_from_outside = True
		
		if widget:
			self.set_widget(widget)
			
	def get_widget(self):
		return self.__widget
		
	def set_widget(self, widget):
		if self.__widget != widget:
			if self.__widget:
				self.__pressure.clear()
				
				for a_handler_id in self.__widget_handler_ids:
					self.__widget.disconnect(a_handler_id)
				self.__widget_handler_ids = None
				
				if self.__delayed_motion_id:
					GLib.source_remove(self.__delayed_motion_id)
					self.__delayed_motion_id = None
				
			self.__widget = widget
			if widget:			
				widget.add_events(MouseAdapter.EventMask)
				self.__widget_handler_ids = [
					widget.connect("button-press-event", self._button_press),
					widget.connect("button-release-event", self._button_release),
					widget.connect("scroll-event", self._mouse_scroll),
					widget.connect("enter-notify-event", self._mouse_enter),
					widget.connect("motion-notify-event", self._mouse_motion),
				]
				
	widget = GObject.property(get_widget, set_widget, type=Gtk.Widget)
	
	# icy-wut-i-did-thaw
	@property
	def is_frozen(self):
		return self.__ice_cubes > 0
		
	def freeze(self):
		self.__ice_cubes += 1
		
	def thaw(self):
		self.__ice_cubes -= 1
	
	def is_pressed(self, button=None):
		return bool(self.__pressure if button is None \
		            else self.__pressure.get(button, 0))
	
	# begins here the somewhat private functions
	def _button_press(self, widget, data):
		self.__pressure.setdefault(data.button, 1)
		if not self.is_frozen:
			point = data.x, data.y
			self.emit("pression", point, data.button)
		
	def _button_release(self, widget, data):
		if data.button in self.__pressure:
			if not self.is_frozen:
				button_pressure = self.__pressure.get(data.button, 0)
				if button_pressure:
					point = data.x, data.y
					if button_pressure == 2:
						self.emit("stop-dragging", point, data.button)
					
					self.emit("click", point, data.button)
				
			del self.__pressure[data.button]
			
	def _mouse_scroll(self, widget, data):
		if not self.is_frozen:
			point = data.x, data.y
			# I don't have one of those cool mice with smooth scrolling
			got_delta, xd, yd = data.get_scroll_deltas()
			if not got_delta:
				# So I'm not sure this is how it maps
				got_direction, direction = data.get_scroll_direction()
				if got_direction:
					xd, yd = [
						(0, -1), (0, 1),
						(-1, 0), (1, 0)
					][int(data.direction)] # it is [Up, right, down, left]
					got_delta = True
			
			if got_delta:
				self.emit("scroll", point, (xd, yd))
	
	def _mouse_enter(self, *data):
		self.__motion_from_outside = 2
		if not self.__pressure:
			self.__pressure_from_outside = True
								
	def _mouse_motion(self, widget, data):
		# Motion events are handled idly
		self.__current_point = data.x, data.y
		if not self.__delayed_motion_id:
			if not self.__from_point:
				self.__from_point = self.__current_point
			
			if self.__motion_from_outside:
				self.__motion_from_outside -= 1
				if not self.__motion_from_outside:
					self.__pressure_from_outside = False
			
			self.__delayed_motion_id = GLib.idle_add(
			                                self.__delayed_motion, widget,
			                                priority=MouseAdapter.IdlePriority)
			     
	def __delayed_motion(self, widget):
		self.__delayed_motion_id = None
		
		if not self.is_frozen:
			# You got to love tuple comparation
			if self.__from_point != self.__current_point:
				if not self.__pressure_from_outside:
					for button, pressure in self.__pressure.items():
						if pressure == 1:
							self.__pressure[button] = 2
							self.emit("start-dragging",
								      self.__current_point, button)
						
						if pressure:
							self.emit("pression", self.__current_point, button)
						
				if not self.__motion_from_outside:
					self.emit("motion", self.__current_point, self.__from_point)
					
				for button, pressure in self.__pressure.items():
					if pressure == 2:
						self.emit("drag",
						          self.__current_point, self.__from_point,
						          button)
				
		self.__from_point = self.__current_point
		return False
		
class MouseEvents:
	Nothing   =  0 #000000
	Moving    =  3 #000011
	Hovering  =  1 #000001
	Pressing  = 22 #010110
	Dragging  = 14 #001110
	Clicking  = 20 #010100
	Scrolling = 32 #100000
	
class MetaMouseHandler:
	''' Handles mouse events from mouse adapters for mouse handlers '''
	# It's So Meta Even This Acronym
	def __init__(self):
		self.__handlers_data = dict()
		self.__adapters = dict()
		self.__pression_handlers = set()
		self.__hovering_handlers = set()
		self.__dragging_handlers = set()
		self.__scrolling_handlers = set()
		self.__button_handlers = dict()
	
	
	def __getitem__(self, handler):
		return self.__handlers_data[handler]
		
	
	def add(self, handler, button=0):
		''' Adds a handler to be handled '''
		if not handler in self.__handlers_data:
			handler_data = MouseHandlerData()
			handler_data.connect("notify::button",
			                     self._changed_handler_data_button, handler)
			
			self.__handlers_data[handler] = handler_data
			for handler_set in self.__get_handler_sets(handler):
				handler_set.add(handler)
			
			if button:
				handler_data.button = button
				
			return handler_data
	
	
	def remove(self, handler):
		''' Removes a handler to be handled '''
		handler_data = self.__handlers_data.pop(handler, None)
		if handler_data:
			for handler_set in self.__get_handler_sets(handler):
				handler_set.discard(handler)
			
			for a_button_set in self.__button_handlers.values():
				a_button_set.discard(handler_data)
				
		handler_data.emit("removed")
		
			
	def get_handlers(self):
		return self.__handlers_data.keys()
	
	
	def _changed_handler_data_button(self, handler_data, spec, handler):
		for a_button_set in self.__button_handlers.values():
			a_button_set.discard(handler)
		
		button = handler_data.button
		button_set = self.__button_handlers.get(button, set())
		button_set.add(handler)
		self.__button_handlers[button] = button_set
	
	def __get_handler_sets(self, handler):
		if handler.handles(MouseEvents.Scrolling):
			yield self.__scrolling_handlers
			
		if handler.handles(MouseEvents.Pressing):
			yield self.__pression_handlers
			
		if handler.handles(MouseEvents.Hovering):
			yield self.__hovering_handlers
			
		if handler.handles(MouseEvents.Dragging):
			yield self.__dragging_handlers
	
				
	def attach(self, adapter):
		if not adapter in self.__adapters:
			signals = [
				adapter.connect("motion", self._motion),
				adapter.connect("pression", self._pression),
				adapter.connect("scroll", self._scroll),
				adapter.connect("start-dragging", self._start_dragging),
				adapter.connect("drag", self._drag),
				adapter.connect("stop-dragging", self._stop_dragging),
			]
			self.__adapters[adapter] = signals
	
	
	def detach(self, adapter):
		signals = self.__adapters.get(adapter, [])
		for a_signal in signals:
			adapter.disconnect(a_signal)
			
		del self.__adapters[adapter]
		
	
	def __overlap_button_set(self, handler_set, button):
		button_handlers = self.__button_handlers.get(button, set())
		
		if button_handlers:
			return handler_set & button_handlers
		else:
			return button_handlers
	
	
	def __basic_event_dispatch(self, adapter, event_handlers,
	                           function_name, *params):
	                           
		widget = adapter.get_widget()
		
		for a_handler in event_handlers:
			handler_data = self.__handlers_data[a_handler]
			
			function = getattr(a_handler, function_name)
			
			adapter_data = handler_data[adapter]
			adapter_data = function(widget, *(params + (adapter_data,)))
			if adapter_data:
				handler_data[adapter] = adapter_data
	
	
	def _scroll(self, adapter, point, direction):
		if self.__scrolling_handlers:
			self.__basic_event_dispatch(adapter, self.__scrolling_handlers,
			                            "scroll", point, direction)
	
	
	def _motion(self, adapter, to_point, from_point):
		if adapter.is_pressed():
			# If the adapter is pressed but there is no handler for any button
			# then we pretend it is not pressed
			g = (adapter.is_pressed(a_button) for a_button, a_button_handlers \
			     in self.__button_handlers.items() if a_button_handlers)
			hovering = not any(g)
			
		else:
			hovering = True
			
		if hovering:
			self.__basic_event_dispatch(adapter, self.__hovering_handlers,
			                            "hover", to_point, from_point)
	
	
	def _pression(self, adapter, point, button):
		active_handlers = self.__overlap_button_set(
		                       self.__pression_handlers, button)
		                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
			                            "press", point)
	
		
	def _start_dragging(self, adapter, point, button):
		active_handlers = self.__overlap_button_set(
		                       self.__dragging_handlers, button)
		                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
			                            "start_dragging", point)
		
	
	def _drag(self, adapter, to_point, from_point, button):		
		active_handlers = self.__overlap_button_set(
		                       self.__dragging_handlers, button)
		                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
					                    "drag", to_point, from_point)
			
	
	def _stop_dragging(self, adapter, point, button):
		active_handlers = self.__overlap_button_set(
                       self.__dragging_handlers, button)
                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
				                        "stop_dragging", point)

class MouseHandlerData(GObject.Object):
	''' MetaMouseHandler data associated to a MouseHandler  '''
	__gsignals__ = {
		"removed" : (GObject.SIGNAL_ACTION, None, []),
	}
		
	def __init__(self):
		GObject.Object.__init__(self)
		self.adapter_data = dict()

		
	def __getitem__(self, key):
		return self.adapter_data.get(key, None)


	def __setitem__(self, key, value):
		self.adapter_data[key] = value
		
		
	button = GObject.Property(type=int, default=0)

class MouseHandler(GObject.Object):
	''' Handles mouse events sent by MetaMouseHandler. '''
	# The base of the totem pole
	
	def __init__(self):
		GObject.Object.__init__(self)
		self.events = MouseEvents.Nothing
		
		# These are set by the app.
		self.factory = None # The factory that made the handler
	
	# An user-set nickname for this instance
	nickname = GObject.Property(type=str)
	
	def handles(self, event_type):
		return self.events & event_type == event_type \
		       if event_type != MouseEvents.Nothing \
		       else not bool(self.events)
		       
		       
	@property
	def needs_button(self):
		return bool(self.events & MouseEvents.Pressing)
		
	
	def scroll(self, widget, point, direction, data):
		''' Handles a scroll event '''
		pass
		
	
	def press(self, widget, point, data):
		''' Handles the mouse being pressed somewhere '''
		pass
	
	
	def hover(self, widget, to_point, from_point, data):
		''' Handles the mouse just hovering around '''
		pass
	
	
	def start_dragging(self, widget, point, data):
		''' Setup dragging variables '''
		pass
	
	
	def drag(self, widget, to_point, from_point, data):
		''' Drag to point A from B '''
		pass
		
	
	def stop_dragging(self, widget, point, data):
		''' Finish dragging '''
		pass
		
class PivotMode:
	Mouse = 0
	Alignment = 1
	Fixed = 2
	
	
class MouseHandlerPivot(GObject.Object):
	mode = GObject.Property(type=int, default=PivotMode.Mouse)
	# Fixed pivot point
	fixed_x = GObject.Property(type=float, default=.5)
	fixed_y = GObject.Property(type=float, default=.5)
	
	@property
	def fixed_point(self):
		return self.fixed_x, self.fixed_y
	
	@fixed_point.setter
	def fixed_point(self, value):
		self.fixed_x, self.fixed_y = value
	
	def convert_point(self, view, point):
		if self.mode == PivotMode.Mouse:
			result = point
		else:
			w, h = view.get_allocated_width(), view.get_allocated_height()
			
			if self.mode == PivotMode.Alignment:
				sx, sy = view.alignment_point
			else:
				sx, sy = self.fixed_point
				
			result = sx * w, sy * h
		return result
		
class HoverHandler(MouseHandler):
	''' Pans a view on mouse hovering '''
	def __init__(self, speed=1.0, relative_speed=True):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Hovering
		
		self.speed = speed
		self.relative_speed = relative_speed
	
	def hover(self, view, to_point, from_point, data):
		shift = point.subtract(to_point, from_point)
		
		scale = self.speed
		if self.relative_speed:
			scale /= view.magnification
		
		scaled_shift = point.scale(shift, scale)
		view.pan(scaled_shift)
		
	
	speed = GObject.Property(type=float, default=1)
	relative_speed = GObject.Property(type=bool, default=True)
	
class DragHandler(HoverHandler):
	''' Pans a view on mouse dragging '''
	
	def __init__(self, speed=-1.0, relative_speed=True):
		HoverHandler.__init__(self, speed, relative_speed)
		self.events = MouseEvents.Dragging
		
		
	def start_dragging(self, view, *etc):
		fleur_cursor = Gdk.Cursor(Gdk.CursorType.FLEUR)
		view.get_window().set_cursor(fleur_cursor)
	
	
	drag = HoverHandler.hover # lol.
	
	
	def stop_dragging(self, view, *etc):
		view.get_window().set_cursor(None)


class MapHandler(MouseHandler):
	''' Adjusts a view to match a point inside.
	    In it's most basic way for "H" being a point in the widget,
	    "C" being the resulting adjustment, "B" being the widget size and
	    "S" being the boundaries of the viewing widget model: C = H / B * S '''
	def __init__(self, margin=32, mapping_mode="proportional"):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Pressing
		self.mapping_mode = mapping_mode
		self.margin = margin
		
	def press(self, view, point, data):
		# Clamp mouse pointer to map
		rx, ry, rw, rh = self.get_map_rectangle(view)
		mx, my = point
		x = max(0, min(rw, mx - rx))
		y = max(0, min(rh, my - ry))
		# The adjustments
		hadjust = view.get_hadjustment()
		vadjust = view.get_vadjustment()
		# Get content bounding box
		full_width = hadjust.get_upper() - hadjust.get_lower()
		full_height = vadjust.get_upper() - vadjust.get_lower()
		full_width -= hadjust.get_page_size()
		full_height -= vadjust.get_page_size()
		# Transform x and y to picture "adjustment" coordinates
		tx = x / rw * full_width + hadjust.get_lower()
		ty = y / rh * full_height + vadjust.get_lower()
		view.adjust_to(tx, ty)
		
	def get_map_rectangle(self, view):
		allocation = view.get_allocation()
		
		allocation.x = allocation.y = self.margin
		allocation.width -= self.margin * 2
		allocation.height -= self.margin * 2
		
		if allocation.width <= 0:
			diff = 1 - allocation.width
			allocation.width += diff
			allocation.x -= diff / 2
			
		if allocation.height <= 0:
			diff = 1 - allocation.height
			allocation.height += diff
			allocation.y -= diff / 2
		
		if self.mapping_mode == "square":
			if allocation.width > allocation.height:
				smallest_side = allocation.height
			else:
				smallest_side = allocation.width
			
			half_width_diff = (allocation.width - smallest_side) / 2
			half_height_diff = (allocation.height - smallest_side) / 2
			
			return (allocation.x + half_width_diff,
				    allocation.y + half_height_diff,
				    allocation.width - half_width_diff * 2,
				    allocation.height - half_height_diff * 2)
			
		elif self.mapping_mode == "proportional":
			hadjust = view.get_hadjustment()
			vadjust = view.get_vadjustment()
			full_width = hadjust.get_upper() - hadjust.get_lower()
			full_height = vadjust.get_upper() - vadjust.get_lower()
			fw_ratio = allocation.width / full_width
			fh_ratio = allocation.height / full_height
						
			if fw_ratio > fh_ratio:
				smallest_ratio = fh_ratio
			else:
				smallest_ratio = fw_ratio
			
			transformed_width = smallest_ratio * full_width
			transformed_height = smallest_ratio * full_height
			
			half_width_diff = (allocation.width - transformed_width) / 2
			half_height_diff = (allocation.height - transformed_height) / 2
			
			return (allocation.x + half_width_diff,
				    allocation.y + half_height_diff,
				    allocation.width - half_width_diff * 2,
				    allocation.height - half_height_diff * 2)
			
		else:
			return (allocation.x, allocation.y,
			        allocation.width, allocation.height)
		
class SpinHandler(MouseHandler):
	''' Spins a view '''
	
	SpinThreshold = 5
	SoftRadius = 25
	
	def __init__(self, frequency=1, pivot_mode=PivotMode.Mouse,
	             fixed_pivot=(.5, .5)):
		MouseHandler.__init__(self)
		
		self.events = MouseEvents.Dragging
		
		self.frequency = frequency 
		self.pivot = MouseHandlerPivot()
		self.pivot.fixed_point = fixed_pivot
		self.pivot.mode = pivot_mode
	
	# Number of complete turns in the view per revolution around the pivot
	frequency = GObject.Property(type=float, default=1)
	
	def start_dragging(self, view, point, data):
		widget_pivot = self.pivot.convert_point(view, point)
		
		return widget_pivot, view.get_pin(widget_pivot)
	
	def drag(self, view, to_point, from_point, data):
		pivot, pin = data
		
		# Get vectors from the pivot
		(tx, ty), (fx, fy), (px, py) = to_point, from_point, pivot
		tdx, tdy = tx - px, ty - py
		fdx, fdy = fx - px, fy - py
		
		# Get rotational delta, multiply it by frequency
		ta = math.atan2(tdy, tdx) / math.pi * 180
		fa = math.atan2(fdy, fdx) / math.pi * 180
		rotation_effect = (ta - fa) * self.frequency
		
		# Modulate degrees
		rotation_effect %= 360 if rotation_effect >= 0 else -360
		if rotation_effect > 180:
			rotation_effect -= 360
		if rotation_effect < -180:
			rotation_effect += 360 
			
		# Thresholding stuff
		square_distance = tdx ** 2 + tdy ** 2
		if square_distance > SpinHandler.SpinThreshold ** 2:
			# Falling out stuff
			square_soft_radius = SpinHandler.SoftRadius ** 2
			if square_distance < square_soft_radius:
				fallout_effect = square_distance / square_soft_radius
				rotation_effect *= fallout_effect
			
			# Changing the rotation(finally)
			view.rotation = (view.rotation + rotation_effect) % 360
			# Anchoring!!!
			view.adjust_to_pin(pin)
			
		return data

class StretchHandler(MouseHandler):
	''' Stretches/shrinks a view '''
	
	MinDistance = 10
	
	def __init__(self, fixed_pivot=(.5, .5), pivot_mode=PivotMode.Fixed):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Dragging
		
		self.pivot = MouseHandlerPivot()
		
		self.pivot.mode = pivot_mode
		self.pivot.fixed_point = fixed_pivot
		
	def start_dragging(self, view, start_point, data):
		widget_size = view.get_widget_size()
		widget_pivot = self.pivot.convert_point(view, start_point)
		
		start_diff = point.subtract(start_point, widget_pivot)
		distance = max(StretchHandler.MinDistance, point.length(start_diff))
		
		zoom = view.magnification
		zoom_ratio = zoom / distance
		
		return zoom_ratio, widget_pivot, view.get_pin(widget_pivot)
	
	def drag(self, view, to_point, from_point, data):
		zoom_ratio, widget_pivot, pin = data
		
		# Get vectors from the pivot
		point_diff = point.subtract(to_point, widget_pivot)
		distance = max(StretchHandler.MinDistance, point.length(point_diff))
		
		new_zoom = distance * zoom_ratio
		
		view.magnification = new_zoom
		view.adjust_to_pin(pin)
		
		return data


class SwapMode:
	NoSwap = 0 # Don't swap anything
	Swap = 1 # Swap axes
	VerticalGreater = 2 # Map vertical scrolling with greater axis
	HorizontalGreater = 3 # Map horizontal scrolling with greater axis

class ScrollHandler(MouseHandler):
	''' Scrolls a view '''
	
	def __init__(self, relative_speed=.3, pixel_speed = 300,
	                   relative_scrolling=True, inverse = (False, False),
	                   swap_mode = SwapMode.NoSwap, rotate=False):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Scrolling
		
		self.pixel_speed = pixel_speed
		self.relative_speed = relative_speed
		self.relative_scrolling = relative_scrolling
		self.inverse_horizontal, self.inverse_vertical = inverse
		self.rotate = rotate
		self.swap_mode = swap_mode
	
	# Scrolling speed
	pixel_speed = GObject.Property(type=int, default=300)
	relative_speed = GObject.Property(type=float, default=.3)
	# If this is true, speed is scaled to the view dimensions
	relative_scrolling = GObject.Property(type=bool, default=False)
	# Inverse horizontal and vertical axis, this happens after everything else
	inverse_horizontal = GObject.Property(type=bool, default=False)
	inverse_vertical = GObject.Property(type=bool, default=False)
	# Axes swapping mode
	swap_mode = GObject.Property(type=int, default=0)
	# Rotate scrolling shift with view rotation
	rotate = GObject.Property(type=bool, default=False)
	
	
	def scroll(self, view, position, direction, data):
		xd, yd = direction
		view_size = view.get_view()[2:]
		if self.relative_scrolling:
			scaled_view_size = point.scale(view_size, self.relative_speed)
			xd, yd = point.multiply((xd, yd), scaled_view_size)
			
		else:
			xd, yd = point.scale((xd, yd), self.pixel_speed)
			
		if self.rotate:
			xd, yd = point.spin((xd, yd), view.get_rotation_radians())
			scroll_along_size = view.get_frames_outline()[2:]
			
		else:
			scroll_along_size = view.get_boundary()[2:]
				
		if self.swap_mode & SwapMode.VerticalGreater:
			unviewed_ratio = point.divide(scroll_along_size, view_size)
			
			if point.is_wide(unviewed_ratio):
				xd, yd = yd, xd
			
		if self.swap_mode & SwapMode.Swap:
			xd, yd = yd, xd
		
		if self.inverse_horizontal:
			xd = -xd
			
		if self.inverse_vertical:
			yd = -yd
			
		view.pan((xd, yd))


class ZoomHandler(MouseHandler):
	''' Zooms a view '''
	
	def __init__(self, minify_pivot=None, magnify_pivot=None,
	             horizontal=False, effect=2):
	             
		MouseHandler.__init__(self)
		self.events = MouseEvents.Scrolling
		
		if not minify_pivot:
			minify_pivot = MouseHandlerPivot(mode=PivotMode.Fixed)
			
		if not magnify_pivot:
			magnify_pivot = MouseHandlerPivot(mode=PivotMode.Fixed)
			
		self.minify_pivot = minify_pivot
		self.magnify_pivot = magnify_pivot
		
		if effect < 0:
			self.effect = 1.0 / effect
			self.inverse_effect = True
		else:
			self.effect = effect
			
		self.horizontal = horizontal
	
	effect = GObject.Property(type=float, default=2)
	inverse_effect = GObject.Property(type=bool, default=False)
	horizontal = GObject.Property(type=bool, default=False)
	
	def scroll(self, view, point, direction, data):
		dx, dy = direction
		delta = (dx if self.horizontal else dy) * -1
		
		if delta and self.effect:
			if self.inverse_effect:
				power = (1.0 / self.effect) ** delta
			else:
				power = self.effect ** delta
			
			pivot = self.minify_pivot if power < 0 else self.magnify_pivot
			anchor_point = pivot.convert_point(view, point)
			
			pin = view.get_pin(anchor_point)
			view.magnification *= power
			view.adjust_to_pin(pin)


class GearHandler(MouseHandler):
	''' Spins a view with each scroll tick '''
	
	def __init__(self, anchor=None, horizontal=False, inverse=False, effect=45):
	             
		MouseHandler.__init__(self)
		self.events = MouseEvents.Scrolling
		self.anchor = anchor
		self.effect = effect
	
	horizontal = GObject.Property(type=bool, default=False)
	inverse = GObject.Property(type=bool, default=False)
	
	def scroll(self, view, point, direction, data):
		dx, dy = direction
		delta = dx if self.horizontal else dy
			
		if self.anchor:
			w, h = view.get_allocated_width(), view.get_allocated_height()
			anchor_point = self.anchor[0] * w, self.anchor[1] * h
		else:
			anchor_point = point
			
		pin = view.get_pin(anchor_point)
		
		angle = view.rotation
		angle += self.effect * delta
		view.rotation = angle % 360
		
		view.adjust_to_pin(pin)
		
#-- Factories down this line --#

import extending
from gettext import gettext as _

class HoverAndDragHandlerSettingsWidget(Gtk.Box):
	''' A settings widget made for a HoverMouseHandler and DragMouseHandler ''' 
	def __init__(self, handler, drag=True):
		Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
		                 spacing=12)
		
		label = _("Panning speed")
		speed_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
		                     spacing=20)
		speed_label = Gtk.Label(label)
		speed_label.set_alignment(0, .5)
		
		speed_adjustment = Gtk.Adjustment(0, -10, 10, .1, 1, 0)
		speed_entry = Gtk.SpinButton(adjustment=speed_adjustment, digits=2)
		label = _("Speed relative to zoom")
		speed_relative = Gtk.CheckButton(label)
		
		
		speed_line.pack_start(speed_label, False, False, 0)
		speed_line.pack_start(speed_entry, False, False, 0)
		speed_line.pack_start(speed_relative, False, False, 0)
		
		speed_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
		                        adjustment=speed_adjustment)
		
		# Setup speed scale marks
		mark_pos = Gtk.PositionType.BOTTOM
		speed_scale.add_mark(-10, mark_pos, _("Pan Image"))
		speed_scale.add_mark(-1, mark_pos, None, )
		speed_scale.add_mark(0, mark_pos, _("Inertia"))
		speed_scale.add_mark(1, mark_pos, None)
		speed_scale.add_mark(10, mark_pos, _("Pan View"))
		speed_scale.set_has_origin(False)
		# Show as percent
		value_to_percent = lambda w, v: "{:.0%}".format(abs(v))
		speed_scale.connect("format-value", value_to_percent)
		
		self.pack_start(speed_line, False, True, 0)
		self.pack_start(speed_scale, False, True, 0)
		
		# Bind properties
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		both_flags = bidi_flag | sync_flag
		
		handler.bind_property("speed", speed_adjustment, "value", both_flags)
		handler.bind_property("relative-speed", speed_relative,
		                      "active", both_flags)
		self.show_all()


class HoverHandlerFactory(extending.MouseHandlerFactory):
	def __init__(self):
		codename = "hover"
		self.create_default = HoverHandler
		self.create_settings_widget = HoverAndDragHandlerSettingsWidget
		
		
	@property
	def label(self):
		return _("Move Mouse to Pan")
HoverHandlerFactory = HoverHandlerFactory()


class DragHandlerFactory(extending.MouseHandlerFactory):
	def __init__(self):
		codename = "drag"
		self.create_default = DragHandler
		self.create_settings_widget = HoverAndDragHandlerSettingsWidget
		
		
	@property
	def label(self):
		return _("Drag to Pan")
DragHandlerFactory = DragHandlerFactory()


# TODO: Fix MapHandler for multi-image layouts and create its factory

from preferences import PointScale
class PivotedHandlerSettingsWidget:
	def __init__(self):
		self.pivot_widgets = dict()
		self.pivot_radios = dict()
	
	def create_pivot_widgets(self, pivot):
		label = _("Use mouse pointer as pivot")
		pivot_mouse = Gtk.RadioButton(label=label)
		label = _("Use view alignment as pivot")
		pivot_alignment = Gtk.RadioButton(label=label, group=pivot_mouse)
		label = _("Use a fixed point as pivot")
		pivot_fixed = Gtk.RadioButton(label=label, group=pivot_alignment)
		                                   
		fixed_point_grid = fixed_point_grid = Gtk.Grid()
		fixed_point_grid.set_row_spacing(12)
		fixed_point_grid.set_column_spacing(20)
		
		xadjust = Gtk.Adjustment(.5, 0, 1, .1, .25, 0)
		yadjust = Gtk.Adjustment(.5, 0, 1, .1, .25, 0)
		
		xlabel = Gtk.Label("Pivot X")
		xspin = Gtk.SpinButton(adjustment=xadjust, digits=2)
		ylabel = Gtk.Label("Pivot Y")
		yspin = Gtk.SpinButton(adjustment=yadjust, digits=2)
		
		point_scale = PointScale(xadjust, yadjust)
		
		fixed_point_grid.attach(pivot_fixed, 0, 0, 2, 1)
		fixed_point_grid.attach(xlabel, 0, 1, 1, 1)
		fixed_point_grid.attach(ylabel, 0, 2, 1, 1)
		fixed_point_grid.attach(xspin, 1, 1, 1, 1)
		fixed_point_grid.attach(yspin, 1, 2, 1, 1)
		fixed_point_grid.attach(point_scale, 2, 0, 1, 3)
		
		self.pivot_radios[pivot] = pivot_radios = {
			PivotMode.Mouse : pivot_mouse,
			PivotMode.Alignment : pivot_alignment,
			PivotMode.Fixed : pivot_fixed
		}
		self.pivot_widgets[pivot] = pivot_widgets = [
			pivot_mouse, pivot_alignment, fixed_point_grid
		]
		
		# Bind properties
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		both_flags = bidi_flag | sync_flag
		
		pivot.bind_property("fixed-x", xadjust, "value", both_flags)
		pivot.bind_property("fixed-y", yadjust, "value", both_flags)
		pivot.connect("notify::mode", self._refresh_pivot_mode)
		
		fixed_pivot_widgets = [xlabel, xspin, ylabel, yspin, point_scale]
		for a_pivot_widget in fixed_pivot_widgets:		
			pivot_fixed.bind_property("active", a_pivot_widget,
			                          "sensitive", sync_flag)
			                               
		for value, radio in pivot_radios.items():
			radio.connect("toggled", self._pivot_mode_chosen, pivot, value)
		
		self._refresh_pivot_mode(pivot)
		
		return pivot_widgets
		
	def _refresh_pivot_mode(self, pivot, *data):
		self.pivot_radios[pivot][pivot.mode].set_active(True)
	
	def _pivot_mode_chosen(self, radio, pivot, value):
		if radio.get_active() and pivot.mode != value:
			pivot.mode = value
	
	
class SpinHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
	def __init__(self, handler):
		Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
		                 spacing=12)
		
		PivotedHandlerSettingsWidget.__init__(self)
		
		self.handler = handler
		
		frequency_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
		                         spacing=20)
		label = _("Frequency of turns")
		frequency_label = Gtk.Label(label)
		
		frequency_adjustment = Gtk.Adjustment(1, -9, 9, .1, 1, 0)
		frequency_entry = Gtk.SpinButton(adjustment=frequency_adjustment,
		                                 digits=2)
		frequency_line.pack_start(frequency_label, False, True, 0)
		frequency_line.pack_start(frequency_entry, False, True, 0)
		
		pivot_widgets = self.create_pivot_widgets(handler.pivot)
		
		self.pack_start(frequency_line, False, True, 0)
		for pivot_widget in pivot_widgets:
			self.pack_start(pivot_widget, False, True, 0)
		
		self.show_all()
		
		# Bind properties
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		both_flags = bidi_flag | sync_flag
		
		handler.bind_property("frequency", frequency_adjustment,
		                      "value", both_flags)


class SpinHandlerFactory(extending.MouseHandlerFactory):
	def __init__(self):
		codename = "spin"
		self.create_default = SpinHandler
		self.create_settings_widget = SpinHandlerSettingsWidget
		
		
	@property
	def label(self):
		return _("Drag to Spin")
SpinHandlerFactory = SpinHandlerFactory()


class StretchHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
	def __init__(self, handler):
		Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
		                 spacing=12)
		
		PivotedHandlerSettingsWidget.__init__(self)
		
		mouse, alignment, fixed = self.create_pivot_widgets(handler.pivot)
		self.pack_start(alignment, False, True, 0)
		self.pack_start(fixed, False, True, 0)
		
		self.show_all()


class StretchHandlerFactory(extending.MouseHandlerFactory):
	def __init__(self):
		codename = "stretch"
		self.create_default = StretchHandler
		self.create_settings_widget = StretchHandlerSettingsWidget
		
		
	@property
	def label(self):
		return _("Drag to Stretch")
StretchHandlerFactory = StretchHandlerFactory()


class ScrollHandlerSettingsWidget(Gtk.Box):
	def __init__(self, handler):
		Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
		                 spacing=12)
		
		self.handler = handler
		
		label = _("Relative percentage scrolling speed")
		relative_radio = Gtk.RadioButton(label=label)
		relative_adjust = Gtk.Adjustment(1, 0, 3, .05, .5, 0)
		relative_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
		                           adjustment=relative_adjust, digits=2)
		
		value_to_percent = lambda w, v: "{:.0%}".format(v)
		relative_scale.connect("format-value", value_to_percent)
		relative_scale.add_mark(0, Gtk.PositionType.BOTTOM, _("Inertia"))
		relative_scale.add_mark(1, Gtk.PositionType.BOTTOM, _("Entire Window"))
		self.relative_radio = relative_radio
		
		label = _("Fixed pixel scrolling speed")
		pixel_radio = Gtk.RadioButton(label=label, group=relative_radio)
		pixel_adjust = Gtk.Adjustment(300, 0, 9001, 20, 150, 0)
		pixel_entry = Gtk.SpinButton(adjustment=pixel_adjust)
		pixel_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
		                     spacing=20)
		pixel_line.pack_start(pixel_radio, False, True, 0)
		pixel_line.pack_start(pixel_entry, False, True, 0)
		self.pixel_radio = pixel_radio
		
		label = _("Inverse vertical scrolling")
		inversev = Gtk.CheckButton(label=label)
		label = _("Inverse horizontal scrolling")
		inverseh = Gtk.CheckButton(label=label)
		
		label = _("Rotate scrolling to image coordinates")
		rotate = Gtk.CheckButton(label)
		
		label = _("Do not swap axes")
		noswap = Gtk.RadioButton(label=label)
		label = _("Swap vertical and horizontal scrolling")
		doswap = Gtk.RadioButton(label=label, group=noswap)
		label = _("Vertical scrolling scrolls greatest side")
		vgreater = Gtk.RadioButton(label=label, group=doswap)
		label = _("Vertical scrolling scrolls smallest side")
		hgreater = Gtk.RadioButton(label=label, group=vgreater)
		
		self.pack_start(pixel_line, False, True, 0)
		self.pack_start(relative_radio, False, True, 0)
		self.pack_start(relative_scale, False, True, 0)
		self.pack_start(inverseh, False, True, 0)
		self.pack_start(inversev, False, True, 0)
		self.pack_start(rotate, False, True, 0)
		self.pack_start(noswap, False, True, 0)
		self.pack_start(doswap, False, True, 0)
		self.pack_start(vgreater, False, True, 0)
		self.pack_start(hgreater, False, True, 0)
		
		self.show_all()
		
		# Bind properties
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		both_flags = bidi_flag | sync_flag
		inv_flag = GObject.BindingFlags.INVERT_BOOLEAN
		
		handler.connect("notify::pivot-mode", self._refresh_swap_mode)
		self.swap_options = {
			SwapMode.NoSwap : noswap, SwapMode.Swap : doswap,
			SwapMode.VerticalGreater : vgreater,
			SwapMode.HorizontalGreater : hgreater
		}
		
		for value, radio in self.swap_options.items():
			radio.connect("toggled", self._swap_mode_chosen, value)
		
		handler.connect("notify::relative-scrolling", self._refresh_speed_mode)
		pixel_radio.connect("toggled", self._speed_mode_chosen, False)
		relative_radio.connect("toggled", self._speed_mode_chosen, True)
		
		pixel_radio.bind_property("active", pixel_entry,
		                          "sensitive", sync_flag)
		relative_radio.bind_property("active", relative_scale,
		                             "sensitive", sync_flag)
		                             
		handler.bind_property("relative-speed", relative_adjust,
		                      "value", both_flags)
		handler.bind_property("pixel-speed", pixel_adjust,
		                      "value", both_flags)
		handler.bind_property("inverse-horizontal", inverseh,
		                      "active", both_flags)
		handler.bind_property("inverse-vertical", inversev,
		                      "active", both_flags)
		handler.bind_property("rotate", rotate, "active", both_flags)
			
		self._refresh_swap_mode(handler)
		self._refresh_speed_mode(handler)
		
		
	def _refresh_swap_mode(self, handler, *data):
		self.swap_options[handler.swap_mode].set_active(True)
		
		
	def _swap_mode_chosen(self, radio, value):
		if radio.get_active() and self.handler.swap_mode != value:
			self.handler.swap_mode = value
	
	
	def _refresh_speed_mode(self, handler, *data):
		if handler.relative_scrolling:
			self.relative_radio.set_active(True)
		else:
			self.pixel_radio.set_active(True)
	
	
	def _speed_mode_chosen(self, radio, value):
		if radio.get_active() and self.handler.relative_scrolling != value:
			self.handler.relative_scrolling = value
			
	
class ScrollHandlerFactory(extending.MouseHandlerFactory):
	def __init__(self):
		codename = "scroll"
		self.create_default = ScrollHandler
		self.create_settings_widget = ScrollHandlerSettingsWidget
		
		
	@property
	def label(self):
		return _("Scroll to Pan")
ScrollHandlerFactory = ScrollHandlerFactory()

class ZoomHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
	def __init__(self, handler):
		Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
		                 spacing=12)
		
		PivotedHandlerSettingsWidget.__init__(self)
		
		label = _("Zoom effect")
		effect_label = Gtk.Label(label)
		
		effect_adjust = Gtk.Adjustment(0, 0, 4, .05, .25, 0)
		effect_entry = Gtk.SpinButton(adjustment=effect_adjust, digits=2)
		
		effect_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
		                      spacing=20)
		label = _("Inverse effect")
		effect_inverse = Gtk.CheckButton(label)
		
		effect_line.pack_start(effect_label, False, True, 0)
		effect_line.pack_start(effect_entry, False, True, 0)
		effect_line.pack_start(effect_inverse, False, True, 0)
		
		label = _("Activate with horizontal scrolling")		
		horizontal_check = Gtk.CheckButton(label)
		
		# Create magnify and minify pivot widgets in a notebook
		pivot_book = Gtk.Notebook()
		pivot_labels = (
			(handler.magnify_pivot, _("Zoom in anchor")),
			(handler.minify_pivot, _("Zoom out anchor")),
		)
		for a_pivot, a_label in pivot_labels:
			a_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
			a_box_widgets = self.create_pivot_widgets(a_pivot)
			for a_widget in a_box_widgets:
				a_box.pack_start(a_widget, False, True, 0)
			
			# Add widgets to notebook
			an_alignment = Gtk.Alignment()
			an_alignment.set_padding(12, 12, 12, 12)
			an_alignment.add(a_box)
			a_tab_label = Gtk.Label(a_label)		
			pivot_book.append_page(an_alignment, a_tab_label)
		
		self.pack_start(effect_line, False, True, 0)
		self.pack_start(pivot_book, False, True, 0)
		self.pack_start(horizontal_check, False, True, 0)
		
		self.show_all()
		
		# Bind properties
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		both_flags = bidi_flag | sync_flag
		
		handler.bind_property("effect", effect_adjust, "value", both_flags)
		handler.bind_property("inverse-effect", effect_inverse,
		                       "active", both_flags)
		handler.bind_property("horizontal", horizontal_check,
		                      "active", both_flags)

		
class ZoomHandlerFactory(extending.MouseHandlerFactory):
	def __init__(self):
		codename = "zoom"
		self.create_default = ZoomHandler
		self.create_settings_widget=ZoomHandlerSettingsWidget
		
	@property
	def label(self):
		return _("Scroll to Zoom")
ZoomHandlerFactory = ZoomHandlerFactory()


class GearHandlerFactory(extending.MouseHandlerFactory):
	def __init__(self):
		codename = "gear"
		self.create_default = GearHandler
		
	@property
	def label(self):
		return _("Scroll to Spin")
		
	def create_settings_widget(self, handler):
		''' Creates a widget for configuring a mouse handler '''
		
		raise NotImplementedError
GearHandlerFactory = GearHandlerFactory()

extending.MouseHandlerBrands.extend([
	DragHandlerFactory, HoverHandlerFactory, SpinHandlerFactory,
	StretchHandlerFactory, ScrollHandlerFactory,
	ZoomHandlerFactory, GearHandlerFactory
])
