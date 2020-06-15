#-*- coding: utf-8 -*-

"""
Draw a timeline in viewport

!!! Very Dirty code.
"""

from collections import defaultdict
from statistics import mean

import gpu
import bgl, blf
import bpy
from gpu_extras.batch import batch_for_shader
import bpy_extras.view3d_utils as view3d_utils
import mathutils

font_info = { "font_id": 0,
              "handler": None }

def remap ( value, old_min, old_max, new_min, new_max ):
    value = clamp ( value, old_min, old_max )
    old_range = old_max - old_min
    if old_range == 0:
        new_value = new_min
    else:
         new_range = new_max - new_min
         new_value = ( ( ( value - old_min ) * new_range ) / old_range ) + new_min

    return new_value

def clamp ( value, minimum, maximum ):
    return min ( max ( value, minimum ), maximum )
#
# Geometry utils functions
#
class Square:
    UNIFORM_SHADER_2D = gpu.shader.from_builtin ( '2D_UNIFORM_COLOR' )
    def __init__ ( self, 
                   x, y,
                   sx, sy,
                   color = ( 1., 1., 1., 1. ) ):
        self._x = x
        self._y = y
        self._sx = sx
        self._sy = sy
        self._color = color

    @property
    def x ( self ):
        return self._x

    @x.setter
    def x ( self, value ):
        self._x = value

    @property
    def y ( self ):
        return  self._y

    @y.setter
    def y ( self, value ):
        self._y = value

    @property
    def sx ( self ):
        return  self._sx

    @sx.setter
    def sx ( self, value ):
        self._sx = value

    @property
    def sy ( self ):
        return  self._sy

    @sy.setter
    def sy ( self, value ):
        self.sy = value

    @property
    def color ( self ):
        return  self._color

    @color.setter
    def color ( self, value ):
        self._color = value

    def copy ( self ):
        return Square ( self.x, self.y, self.sx, self.sy, self.color )
        
    def draw ( self ):
        vertices = ((-self._sx + self._x, self._sy + self._y), (self._sx + self._x, self._sy + self._y),
                    (-self._sx + self._x, -self._sy + self._y), (self._sx + self._x, -self._sy + self._y))
        # vertices += [ pos_2d.x, pos_2d.y ]
        indices = (
            (0, 1, 2), (2, 1, 3))

        batch = batch_for_shader ( self.UNIFORM_SHADER_2D, 'TRIS', { "pos": vertices }, indices = indices )

        self.UNIFORM_SHADER_2D.bind ( )
        self.UNIFORM_SHADER_2D.uniform_float ( "color", self._color )
        batch.draw ( self.UNIFORM_SHADER_2D )


    def bbox ( self ):
        return ( -self._sx + self._x, -self.sy + self._y ), ( self._sx + self._x, self._sy + self._y )


#
# Blender windows system utils
#
def get_region_at_xy ( context, x, y ):
    """
    Does not support quadview right now

    :param context:
    :param x:
    :param y:
    :return: the region and the area containing this region
    """
    for area in context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        #is_quadview = len ( area.spaces.active.region_quadviews ) == 0
        i = -1
        for region in area.regions:
            if region.type == 'WINDOW':
                i += 1
                if (region.x <= x < region.width + region.x and
                        region.y <= y < region.height + region.y):

                    return region, area

    return None, None


class BL_UI_Cursor:
    def __init__ ( self, move_callback = None ):
        self.context = None

        self.range_min = 0
        self.range_max = 100
        self._value = 0

        self.posx = 0
        self.posy = 32

        self.sizex = 11
        self.sizey = 8

        # Is used for drawing the frame number and for cursor interaction
        self.bbox = Square ( self.posx + self.sizex,
                             self.posy,
                             self.sizex,
                             self.sizey )
        self.caret = Square ( self.posx,
                              self.posy - self.sizey,
                              3,
                              4 )

        self.hightlighted = False
        self.edit_time = 0
        self.color = ( .2, .2, 1., 1 )
        self.hightlighted_color = ( .5, .5, .5, 1 )
        self._p_mouse_x = 0
        self._mouse_down = False
        self._dragable = False
        self._move_callback = move_callback
        self.__inrect = False
        self.__area = None
        self.__region = None

    @property
    def value ( self ):
        return self._value

    @value.setter
    def value ( self, value ):
        self._value = clamp ( value, self.range_min, self.range_max )

    def init ( self, context ):
        self.context = context
        self.__area = context.area

    def draw ( self ):
        props = self.context.scene.UAS_shot_manager_props
        self.bbox.color = self.color
        self.caret.color = self.color
        if self.hightlighted:
            self.bbox.color = self.hightlighted_color
            self.caret.color = self.hightlighted_color

        box_to_draw = self.bbox.copy ( )
        box_to_draw.x = self.posx
        caret_to_draw = self.caret.copy ( )
        caret_to_draw.x = self.posx
        edit_start_frame = props.editStartFrame
        if not self._dragable:
            scene_edit_time = props.getEditCurrentTime ( ignoreDisabled = True )
            scene_edit_time = max ( edit_start_frame, scene_edit_time )
            val = remap ( scene_edit_time, edit_start_frame, props.getEditDuration ( ignoreDisabled = True ) + edit_start_frame, 0, self.context.area.width )
            self.value = remap ( val, 0, self.context.area.width, self.range_min, self.range_max )
        else:
            val = remap ( self.value, self.range_min, self.range_max, 0, self.context.area.width )

        box_to_draw.x = val
        caret_to_draw.x = val
        box_to_draw.x = max ( box_to_draw.sx, box_to_draw.x )
        box_to_draw.x = min ( box_to_draw.x, self.context.area.width - 1 - box_to_draw.sx )
        caret_to_draw.draw ( )
        box_to_draw.draw ( )

        blf.color ( 0, .9, .9, .9, 1  )
        blf.size ( 0, 12, 72 )
        frame = str ( max ( props.getEditCurrentTime ( ignoreDisabled = True ), edit_start_frame ) )
        font_width, font_height = blf.dimensions ( 0, frame )
        blf.position ( 0, box_to_draw.x - 0.5 * font_width, box_to_draw.y - 0.5 * font_height, 0 )
        blf.draw ( 0, frame )


    def is_in_rect ( self, x, y ):
        if self.__region is not None:
            x -= self.__region.x
            y -= self.__region.y
            self.bbox.x = remap ( self.value, self.range_min, self.range_max, 0, self.__area.width )
            self.bbox.x = clamp ( self.bbox.x, self.bbox.sx, self.__area.width - self.bbox.sx )
            bound_lo, bound_hi = self.bbox.bbox ( )
            if bound_lo[ 0 ] <= x < bound_hi[ 0 ] and bound_lo[ 1 ] <= y < bound_hi[ 1 ]:
                return True

        return False

    def handle_event ( self, event ):
        x = event.mouse_x
        y = event.mouse_y

        tmp_region, tmp_area = get_region_at_xy ( self.context, x, y )
        if tmp_area is not None:
            self.__region, self.__area = tmp_region, tmp_area
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self._mouse_down = True
                return self.mouse_down ( x, y )
            else:
                self._mouse_down = False
                self.mouse_up ( x, y )


        elif event.type == 'MOUSEMOVE':
            self.mouse_move ( x, y )
            inrect = self.is_in_rect ( x, y )

            # we enter the rect
            if not self.__inrect and inrect:
                self.__inrect = True
                self.mouse_enter ( event, x, y )

            # we are leaving the rect
            elif self.__inrect and not inrect:
                self.__inrect = False
                self.mouse_exit ( event, x, y )

            return False

        return False

    def mouse_down ( self, x, y ):
        if self.is_in_rect ( x, y ):
            self._p_mouse_x = x
            self._dragable = True
            return True

        return False

    def mouse_up ( self, x, y ):
        self._dragable = False
        self.hightlighted = False

    def mouse_enter ( self, event, x, y ):
        self.hightlighted = True

    def mouse_exit ( self, event, x, y ):
        self.hightlighted = False

    def mouse_move ( self, x, y ):
        if self._dragable and self.__area is not None:
            #self.posx += x - self._p_mouse_x
            self.value += ( x - self._p_mouse_x ) * ( self.range_max - self.range_min) / self.__area.width
            self._p_mouse_x = x
            if self._move_callback is not None:
                self._move_callback ( )


class BL_UI_Shot:
    def __init__ ( self, x, y, width, height, label, bypass_state ):
        self.x = x
        self.y = y
        self.x_screen = x
        self.y_screen = y
        self.width = width
        self.height = height
        self.label = label
        self.bypass_state = bypass_state
        self._bg_color = (0.8, 0.3, 0.3, 1.0)
        self._label_color = ( .05, .05, .05, 1 )
        self.context = None
        self.__inrect = False
        self._mouse_down = False

    def set_location ( self, x, y ):
        self.x = x
        self.y = y
        self.x_screen = x
        self.y_screen = y


    @property
    def bg_color ( self ):
        return self._bg_color

    @bg_color.setter
    def bg_color ( self, value ):
        self._bg_color = value
        if mean ( self._bg_color[ : -1] ) < .4:
            self._label_color = ( .9, .9, .9, 1 )

        if self.bypass_state:
            self._bg_color = ( .2, .2, .2, 1 )


    def init ( self, context ):
        self.context = context

    def draw ( self ):
        area_height = self.get_area_height ( )

        self.x_screen = self.x
        self.y_screen = area_height - self.y

        indices = ((0, 1, 2), (0, 2, 3))

        y_screen_flip = area_height - self.y_screen
        # bottom left, top left, top right, bottom right
        vertices = (
            (self.x_screen, y_screen_flip),
            (self.x_screen, y_screen_flip - self.height),
            (self.x_screen + self.width, y_screen_flip - self.height),
            (self.x_screen + self.width, y_screen_flip))

        shader = gpu.shader.from_builtin ( '2D_UNIFORM_COLOR' )
        batch_panel = batch_for_shader ( shader, 'TRIS', { "pos": vertices }, indices = indices )

        shader.bind ( )
        shader.uniform_float ( "color", self._bg_color )
        bgl.glEnable ( bgl.GL_BLEND )
        batch_panel.draw ( shader )
        bgl.glDisable ( bgl.GL_BLEND )

        blf.position ( 0, self.x_screen + 2, y_screen_flip  - self.height * .5, 0 )
        blf.color ( 0, *self._label_color )
        blf.shadow ( 0, 3, .1, .1, .1, 1 )
        blf.size ( 0, 14, 72 )
        blf.draw ( 0, self.label )

    def handle_event ( self, event ):
        x = event.mouse_region_x
        y = event.mouse_region_y

        if (event.type == 'LEFTMOUSE'):
            if (event.value == 'PRESS'):
                self._mouse_down = True
                return self.mouse_down ( x, y )
            else:
                self._mouse_down = False
                self.mouse_up ( x, y )


        elif (event.type == 'MOUSEMOVE'):
            self.mouse_move ( x, y )

            inrect = self.is_in_rect ( x, y )

            # we enter the rect
            if not self.__inrect and inrect:
                self.__inrect = True
                self.mouse_enter ( event, x, y )

            # we are leaving the rect
            elif self.__inrect and not inrect:
                self.__inrect = False
                self.mouse_exit ( event, x, y )

            return False

        return False

    def get_area_height ( self ):
        return self.context.area.height

    def is_in_rect ( self, x, y ):
        area_height = self.get_area_height ( )

        widget_y = area_height - self.y_screen
        if (
                (self.x_screen <= x <= (self.x_screen + self.width)) and
                (widget_y >= y >= (widget_y - self.height))
        ):
            return True

        return False

    def mouse_down ( self, x, y ):
        return self.is_in_rect ( x, y )

    def mouse_up ( self, x, y ):
        pass

    def mouse_enter ( self, event, x, y ):
        pass

    def mouse_exit ( self, event, x, y ):
        pass

    def mouse_move ( self, x, y ):
        pass



class BL_UI_Timeline:
    def __init__ ( self, x, y, width, height ):
        self.x = x
        self.y = y
        self.x_screen = x
        self.y_screen = y
        self.y_offset = 0
        self.width = width
        self.height = height
        self._mouse_y = 0
        self._bg_color = (0.1, 0.1, 0.1, .85)
        self.context = None
        self.__inrect = False
        self._mouse_down = False

        self.ui_shots = list ( )
        self.frame_cursor = BL_UI_Cursor ( self.frame_cursor_moved )

    def set_location ( self, x, y ):
        self.x = x
        self.y = y
        self.x_screen = x
        self.y_screen = y

    @property
    def bg_color ( self ):
        return self._bg_color

    @bg_color.setter
    def bg_color ( self, value ):
        self._bg_color = value

    def init ( self, context ):
        self.context = context
        self.frame_cursor.init ( context )

    def draw_caret ( self, x, color ):
        caret_width = 3
        area_height = self.get_area_height ( )

        y = self.height + self.y_offset
        x_screen = x

        indices = ((0, 1, 2), (0, 2, 3))

        y_screen_flip = area_height - self.y_screen
        # bottom left, top left, top right, bottom right
        vertices = (
            (x_screen, y_screen_flip),
            (x_screen, y_screen_flip - self.height),
            (x_screen + caret_width, y_screen_flip - self.height),
            (x_screen + caret_width, y_screen_flip))

        shader = gpu.shader.from_builtin ( '2D_UNIFORM_COLOR' )
        batch_panel = batch_for_shader ( shader, 'TRIS', { "pos": vertices }, indices = indices )

        shader.bind ( )
        #shader.uniform_float ( "color", ( 1., .1, .1, 1 ) )
        shader.uniform_float ( "color", color )
        bgl.glEnable ( bgl.GL_BLEND )
        batch_panel.draw ( shader )
        bgl.glDisable ( bgl.GL_BLEND )

    def draw_shots ( self ):
        total_range = 0
        shotmanager_props = self.context.scene.UAS_shot_manager_props
        shots = shotmanager_props.getShotsList(ignoreDisabled = True )
        currentShotIndex = shotmanager_props.getCurrentShotIndex(ignoreDisabled = True)

        self.ui_shots.clear ( )
        total_range += sum ( [ s.end + 1 - s.start for s in shots ] )
        offset_x = 0
        for i, shot in enumerate ( shots ):
            size_x = int ( self.width * float ( shot.end + 1 - shot.start ) / total_range )
            s = BL_UI_Shot ( offset_x , self.y, size_x, self.height, shot.name, not shot.enabled )
            self.ui_shots.append ( s )
            s.init ( self.context )
            s.bg_color =  tuple ( shot.color )

            s.draw ( )

            if self.context.window_manager.UAS_shot_manager_handler_toggle:
                if currentShotIndex == i:
                    self.draw_caret( offset_x + ( self.context.scene.frame_current - shot.start ) * size_x / float ( shot.end + 1 - shot.start ),
                                    ( 1.1, 0.1, 0.1, 1 ) )
            else:
                if shot.start <= self.context.scene.frame_current and self.context.scene.frame_current <= shot.end:
                    self.draw_caret( offset_x + ( self.context.scene.frame_current - shot.start ) * size_x / float ( shot.end + 1 - shot.start ),
                                    ( 0.1, 1.0, 0.1, 1 ) )


            offset_x += int ( self.width * float ( shot.end + 1 - shot.start ) / total_range )

    def draw ( self ):
        self.width = self.context.area.width
        area_height = self.get_area_height ( )

        self.y = self.height + self.y_offset
        self.x_screen = self.x
        self.y_screen = area_height - self.y

        indices = ((0, 1, 2), (0, 2, 3))

        y_screen_flip = area_height - self.y_screen
        # bottom left, top left, top right, bottom right
        vertices = (
            (self.x_screen, y_screen_flip),
            (self.x_screen, y_screen_flip - self.height),
            (self.x_screen + self.width, y_screen_flip - self.height),
            (self.x_screen + self.width, y_screen_flip))

        shader = gpu.shader.from_builtin ( '2D_UNIFORM_COLOR' )
        batch_panel = batch_for_shader ( shader, 'TRIS', { "pos": vertices }, indices = indices )

        shader.bind ( )
        shader.uniform_float ( "color", self._bg_color )
        bgl.glEnable ( bgl.GL_BLEND )
        batch_panel.draw ( shader )
        bgl.glDisable ( bgl.GL_BLEND )

        self.draw_shots ( )
        self.frame_cursor.draw ( )

    def handle_event ( self, event ):
        if self.frame_cursor.handle_event ( event ):
            return True

        x = event.mouse_region_x
        y = event.mouse_region_y

        if (event.type == 'LEFTMOUSE'):
            if (event.value == 'PRESS'):
                self._mouse_down = True
                return self.mouse_down ( x, y )
            else:
                self._mouse_down = False
                self.mouse_up ( x, y )


        elif (event.type == 'MOUSEMOVE'):
            self.mouse_move ( x, y )

            inrect = self.is_in_rect ( x, y )

            # we enter the rect
            if not self.__inrect and inrect:
                self.__inrect = True
                self.mouse_enter ( event, x, y )
                self.bg_color = (0.5, 0.5, 0.5, .85)

            # we are leaving the rect
            elif self.__inrect and not inrect:
                self.__inrect = False
                self.mouse_exit ( event, x, y )
                self.bg_color = (0.1, 0.1, 0.1, .85)

            return False

        return False

    def get_area_height ( self ):
        return self.context.area.height

    def is_in_rect ( self, x, y ):
        area_height = self.get_area_height ( )

        widget_y = area_height - self.y_screen
        if (
                (self.x_screen <= x <= (self.x_screen + self.width)) and
                (widget_y >= y >= (widget_y - self.height))
        ):
            return True

        return False

    def frame_cursor_moved ( self ):
        shotmanager_props = self.context.scene.UAS_shot_manager_props
        shots = shotmanager_props.getShotsList ( ignoreDisabled = not shotmanager_props.display_disabledshots_in_timeline )


        new_edit_frame = round ( remap ( self.frame_cursor.value, self.frame_cursor.range_min, self.frame_cursor.range_max, shotmanager_props.editStartFrame, shotmanager_props.editStartFrame + shotmanager_props.getEditDuration ( ) - 1 ) )
        sequence_current_frame = shotmanager_props.editStartFrame
        for shot in shots:
            if sequence_current_frame <=new_edit_frame < sequence_current_frame + shot.getDuration ( ):
                shotmanager_props.setCurrentShot ( shot )
                self.context.scene.frame_current = shot.start + new_edit_frame - sequence_current_frame
                break
            sequence_current_frame += shot.getDuration ( )

    def mouse_down ( self, x, y ):
        return False#self.is_in_rect ( x, y )

    def mouse_up ( self, x, y ):
        pass

    def mouse_enter ( self, event, x, y ):
        pass

    def mouse_exit ( self, event, x, y ):
        pass

    def mouse_move ( self, x, y ):
        pass


class UAS_ShotManager_DrawTimeline ( bpy.types.Operator ):
    bl_idname = "uas_shot_manager.draw_timeline"
    bl_label = "Draw Timeline"
    bl_description = "Draw the edting timeline in the viewport"
    bl_options = { 'REGISTER', "INTERNAL" }

    def __init__ ( self ):
        self.draw_handle = None
        self.draw_event = None

        self.widgets = [ ]

    def init_widgets ( self, context, widgets ):
        self.widgets = widgets
        for widget in self.widgets:
            widget.init ( context )

    def on_invoke ( self, context, event ):
        self.init_widgets ( context, [ BL_UI_Timeline ( 0, context.area.height - 25 , context.area.width, 25 ) ] )

    def invoke ( self, context, event ):

        self.on_invoke ( context, event )

        args = (self, context)

        self.register_handlers ( args, context )

        context.window_manager.modal_handler_add ( self )
        return { "RUNNING_MODAL" }

    def register_handlers ( self, args, context ):
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add ( self.draw_callback_px, args, "WINDOW", "POST_PIXEL" )
        self.draw_event = context.window_manager.event_timer_add ( 0.1, window = context.window )

    def unregister_handlers ( self, context ):
        context.window_manager.event_timer_remove ( self.draw_event )
        bpy.types.SpaceView3D.draw_handler_remove ( self.draw_handle, "WINDOW" )

        self.draw_handle = None
        self.draw_event = None

    def handle_widget_events ( self, event ):
        result = False
        for widget in self.widgets:
            if widget.handle_event ( event ):
                result = True
        return result

    def modal ( self, context, event ):
        if context.area:
            #context.area.tag_redraw ( )
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw ( )
            if self.handle_widget_events ( event ):
                return { 'RUNNING_MODAL' }

     #   if not context.window_manager.UAS_shot_manager_handler_toggle:
      #  if not context.scene.UAS_shot_manager_props.display_timeline:
        if not context.window_manager.UAS_shot_manager_display_timeline:
            self.unregister_handlers ( context )
            return { 'CANCELLED' }

        return { "PASS_THROUGH" }

    def cancel ( self, context ):
        self.unregister_handlers ( context )

    # Draw handler to paint onto the screen
    def draw_callback_px ( self, op, context ):
        for widget in self.widgets:
            widget.draw ( )



class UAS_ShotManager_DrawCameras_UI ( bpy.types.Operator ):
    bl_idname = "uas_shot_manager.draw_cameras_ui"
    bl_label = "ShotManager_DrawCameras_UI"
    bl_description = "ShotManager_DrawCameras_UI."
    bl_options = { "REGISTER", "INTERNAL" }

    def __init__ ( self ):
        self.draw_handle = None
        self.draw_event = None

    def invoke ( self, context, event ):
        self.register_handlers ( context )

        context.window_manager.modal_handler_add ( self )
        return { "RUNNING_MODAL" }

    def register_handlers ( self, context ):
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add ( self.draw_camera_ui, ( context, ), "WINDOW", "POST_PIXEL" )
        self.draw_event = context.window_manager.event_timer_add ( 0.1, window = context.window )

    def unregister_handlers ( self, context ):
        context.window_manager.event_timer_remove ( self.draw_event )
        bpy.types.SpaceView3D.draw_handler_remove ( self.draw_handle, "WINDOW" )

        self.draw_handle = None
        self.draw_event = None

    def modal ( self, context, event ):
        if not context.window_manager.UAS_shot_manager_display_timeline:
            self.unregister_handlers ( context )
            return { 'CANCELLED' }

        return { "PASS_THROUGH" }

    def cancel ( self, context ):
        self.unregister_handlers ( context )

    def draw_camera_ui ( self, context ):
        self.draw_shots_names ( context )

    def draw_shots_names ( self, context ):
        scn = context.scene
        shotmanager_props = context.scene.UAS_shot_manager_props
        shots = shotmanager_props.getShotsList()
        current_shot = shotmanager_props.getCurrentShot()

        shot_names_by_camera = defaultdict ( list )
        for shot in shots:
            if shot.enabled:
                shot_names_by_camera[ shot.camera.name ].append ( shot )

        #
        # Filter out shots in order to restrict the number of shots to be displayed as a list
        #
        shot_trim_info = dict ( )
        shot_trim_length = 2 # Limit the display of x shot before and after the current_shot

        for cam, shots in shot_names_by_camera.items ( ):
            shot_trim_info[ cam ] = [ False, False ]

            current_shot_index = 0
            if current_shot in shots:
                current_shot_index = shots.index ( current_shot )

            before_range = max ( current_shot_index - shot_trim_length, 0 )
            after_range = min ( current_shot_index + shot_trim_length + 1, len ( shots ) )
            shot_names_by_camera[ cam ]  = shots[ before_range : after_range ]

            if before_range > 0:
                shot_trim_info[ cam ][ 0 ] = True
            if after_range < len ( shots ):
                shot_trim_info[ cam ][ 1 ] = True

        font_size = 10

        # For all camera which have a shot draw on the ui a list of shots associated with it.
        blf.size ( 0, font_size, 72 )
        for obj in scn.objects:
            if obj.type == "CAMERA" and obj.name in shot_names_by_camera:
                pos_2d = view3d_utils.location_3d_to_region_2d ( context.region, context.space_data.region_3d, mathutils.Vector( obj.location ) )
                if pos_2d is not None:
                    blf.color ( 0, .9, .9, .9, .9 )
                    # Move underneath object name
                    y_offset = int ( obj.show_name ) * -12
                    x_offset = 12

                    # Draw ... if we don't display previous shots.
                    if shot_trim_info[ obj.name ][ 0 ]:
                        blf.position ( 0, pos_2d[ 0 ] + x_offset, pos_2d[ 1 ] + y_offset, 0 )
                        blf.draw ( 0, "..." )
                        y_offset -= font_size  # Seems to do the trick for this value

                    # Draw the shot names.
                    for s in shot_names_by_camera[ obj.name ]:
                        blf.position ( 0, pos_2d[ 0 ] + x_offset, pos_2d[ 1 ] + y_offset, 0 )
                        if current_shot == s:
                            blf.color ( 0, .8, 1, .2, 1 )
                        else:
                            blf.color ( 0, .9, .9, .9, .9 )
                        blf.draw ( 0, s.name )

                        Square ( pos_2d[ 0 ] + x_offset - 5, pos_2d[ 1 ] + y_offset + 3, 2.5, 2.5, s.color ).draw ( )
                        y_offset -= font_size # Seems to do the trick for this value

                    # Draw ... if we don't display next shots.
                    if shot_trim_info[ obj.name ][ 1 ]:
                        blf.position ( 0, pos_2d[ 0 ] + x_offset, pos_2d[ 1 ] + y_offset, 0 )
                        blf.draw ( 0, "..." )