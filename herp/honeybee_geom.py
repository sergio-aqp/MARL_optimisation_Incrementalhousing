"""THESE ARE FUNCTIONS FROM HONEYBEE FOR GRASSHOPPER THAT ARE FREED FROM THEIR
GRASSHOPPER DEPENDENCIES, SO THEY ARE ABLE TO WORK ON CPYTHON WITH rhino.inside()"""

# Import dependencies
import Rhino
import os
import re
import json

from ladybug.epw import EPW
from ladybug.futil import preparedir, nukedir
from ladybug_rhino.config import tolerance, angle_tolerance, conversion_to_meters, \
    units_system
#from ladybug_rhino.grasshopper import all_required_inputs

import honeybee.config as hb_config
from honeybee.boundarycondition import boundary_conditions, Outdoors
from honeybee.face import Face
from honeybee.model import Model
from honeybee.orientation import check_matching_inputs, angles_from_num_orient, \
    face_orient_index, inputs_by_index
from honeybee.room import Room
from honeybee.search import filter_array_by_keywords
from honeybee.shade import Shade
from honeybee.typing import clean_and_id_string, clean_string, clean_and_id_ep_string, clean_ep_string
from honeybee.facetype import Wall, RoofCeiling, Floor, face_types

from ladybug_geometry.geometry3d.polyface import Polyface3D
from ladybug_geometry.geometry3d.face import Face3D
from ladybug_geometry.geometry3d.pointvector import Vector3D, Point3D
from ladybug_geometry.geometry3d.plane import Plane
import ladybug_rhino.planarize as _planar

from honeybee_energy.constructionset import ConstructionSet
from honeybee_energy.construction.opaque import OpaqueConstruction
from honeybee_energy.construction.window import WindowConstruction
from honeybee_energy.lib.programtypes import STANDARDS_REGISTRY, program_type_by_identifier, \
    building_program_type_by_identifier, office_program, PROGRAM_TYPES
from honeybee_energy.lib.schedules import schedule_by_identifier
from honeybee_energy.lib.scheduletypelimits import schedule_type_limit_by_identifier
from honeybee_energy.lib.constructions import shade_construction_by_identifier
from honeybee_energy.lib.constructionsets import construction_set_by_identifier
from honeybee_energy.lib.materials import OPAQUE_MATERIALS, opaque_material_by_identifier
from honeybee_energy.lib.materials import WINDOW_MATERIALS, window_material_by_identifier
from honeybee_energy.programtype import ProgramType
from honeybee_energy.run import to_openstudio_osw, run_osw, run_idf, \
    output_energyplus_files
from honeybee_energy.result.osw import OSW
from honeybee_energy.schedule.ruleset import ScheduleRuleset
from honeybee_energy.simulation.parameter import SimulationParameter
from honeybee_energy.result.err import Err
from honeybee_energy.result.eui import eui_from_sql

from honeybee_radiance.lib.modifiersets import modifier_set_by_identifier
from honeybee_radiance.lib.modifiers import modifier_by_identifier

from lbt_recipes.version import check_openstudio_version

#####
# Customized Functions from IronPython modules
####

'''CUSTOMIZED FUNCTIONS FROM OTHER MODULES 
REPLACED DUE TO THEIR GRASSHOPPER DEPENDENCIES'''

def longest_list(values, index):
    try:
        return values[index]
    except IndexError:
        return values[-1]
    
def to_point3d(point):
    return Point3D(point.X, point.Y, point.Z)

def to_polyface3d(geo, meshing_parameters=None):
    mesh_par = meshing_parameters or Rhino.Geometry.MeshingParameters.Default  # default
    return Polyface3D.from_faces(to_face3d(geo, mesh_par), tolerance)

def to_vector3d(vector):
    return Vector3D(vector.X, vector.Y, vector.Z)

def to_plane(pl):
    return Plane(
        to_vector3d(pl.ZAxis), to_point3d(pl.Origin), to_vector3d(pl.XAxis))

def _remove_dup_verts(vertices):
    """Remove vertices from an array of Point3Ds that are equal within the tolerance."""
    return [pt for i, pt in enumerate(vertices)
            if not pt.is_equivalent(vertices[i - 1], tolerance)]    
    
def to_face3d(geo, meshing_parameters=None):
    faces = []  # list of Face3Ds to be populated and returned
    if isinstance(geo, Rhino.Geometry.Mesh):  # convert each Mesh face to a Face3D
        pts = tuple(to_point3d(pt) for pt in geo.Vertices)
        for face in geo.Faces:
            if face.IsQuad:
                all_verts = (pts[face[0]], pts[face[1]], pts[face[2]], pts[face[3]])
                lb_face = Face3D(all_verts)
                if lb_face.area != 0:
                    for _v in lb_face.vertices:
                        if lb_face.plane.distance_to_point(_v) >= tolerance:
                            # non-planar quad split the quad into two planar triangles
                            verts1 = (pts[face[0]], pts[face[1]], pts[face[2]])
                            verts2 = (pts[face[3]], pts[face[0]], pts[face[1]])
                            faces.append(Face3D(verts1))
                            faces.append(Face3D(verts2))
                            break
                    else:
                        faces.append(lb_face)
            else:
                all_verts = (pts[face[0]], pts[face[1]], pts[face[2]])
                lb_face = Face3D(all_verts)
                if lb_face.area != 0:
                    faces.append(lb_face)
    else:  # convert each Brep Face to a Face3D
        meshing_parameters = meshing_parameters or Rhino.Geometry.MeshingParameters.Default
        for b_face in geo.Faces:
            if b_face.IsPlanar(tolerance):
                try:
                    bf_plane = to_plane(b_face.FrameAt(0, 0)[-1])
                except Exception:  # failed to extract the plane from the geometry
                    bf_plane = None  # auto-calculate the plane from the vertices
                all_verts = []
                for count in range(b_face.Loops.Count):  # Each loop is a boundary/hole
                    success, loop_pline = \
                        b_face.Loops[count].To3dCurve().TryGetPolyline()
                    if not success:  # Failed to get a polyline; there's a curved edge
                        loop_verts = _planar.planar_face_curved_edge_vertices(
                            b_face, count, meshing_parameters)
                    else:  # we have a polyline representing the loop
                        loop_verts = tuple(to_point3d(loop_pline[i])
                                           for i in range(loop_pline.Count - 1))
                    all_verts.append(_remove_dup_verts(loop_verts))
                if len(all_verts[0]) >= 3:
                    if len(all_verts) == 1:  # No holes in the shape
                        faces.append(Face3D(all_verts[0], plane=bf_plane))
                    else:  # There's at least one hole in the shape
                        hls = [hl for hl in all_verts[1:] if len(hl) >= 3]
                        faces.append(Face3D(
                            boundary=all_verts[0], holes=hls, plane=bf_plane))
            else:  # curved face must be meshed into planar Face3D objects
                faces.extend(_planar.curved_surface_faces(b_face, meshing_parameters))
    return faces

######
# From here on, Grasshopper components
####

'''Create a new construction set'''
# Each subset is a list with the given number of elements
def NewConstSet(_name_, _exterior_subset_, _ground_subset_, _interior_subset_, _subface_subset_):
    # get the base construction set
    name = clean_ep_string(_name_)
    
    # Create the base set with the given name
    constr_set = ConstructionSet(name)
    
    # Add each of the subsets
    if len(_exterior_subset_) != 0:
        assert len(_exterior_subset_) == 3, 'Input _exterior_subset_ is not valid.'
        if _exterior_subset_[0] is not None:
            constr_set.wall_set.exterior_construction = _exterior_subset_[0]
        if _exterior_subset_[1] is not None:
            constr_set.roof_ceiling_set.exterior_construction = _exterior_subset_[1]
        if _exterior_subset_[2] is not None:
            constr_set.floor_set.exterior_construction = _exterior_subset_[2]
    
    if len(_ground_subset_) != 0:
        assert len(_ground_subset_) == 3, 'Input _ground_subset_ is not valid.'
        if _ground_subset_[0] is not None:
            constr_set.wall_set.ground_construction = _ground_subset_[0]
        if _ground_subset_[1] is not None:
            constr_set.roof_ceiling_set.ground_construction = _ground_subset_[1]
        if _ground_subset_[2] is not None:
            constr_set.floor_set.ground_construction = _ground_subset_[2]
    
    if len(_interior_subset_) != 0:
        assert len(_interior_subset_) == 6, 'Input _interior_subset_ is not valid.'
        if _interior_subset_[0] is not None:
            constr_set.wall_set.interior_construction = _interior_subset_[0]
        if _interior_subset_[1] is not None:
            constr_set.roof_ceiling_set.interior_construction = _interior_subset_[1]
        if _interior_subset_[2] is not None:
            constr_set.floor_set.interior_construction = _interior_subset_[2]
        if _interior_subset_[3] is not None:
            constr_set.aperture_set.interior_construction = _interior_subset_[3]
        if _interior_subset_[4] is not None:
            constr_set.door_set.interior_construction = _interior_subset_[4]
        if _interior_subset_[5] is not None:
            constr_set.door_set.interior_glass_construction = _interior_subset_[5]
    
    if len(_subface_subset_) != 0:
        assert len(_subface_subset_) == 6, 'Input _subface_subset_ is not valid.'
        if _subface_subset_[0] is not None:
            constr_set.aperture_set.window_construction = _subface_subset_[0]
        if _subface_subset_[1] is not None:
            constr_set.aperture_set.skylight_construction = _subface_subset_[1]
        if _subface_subset_[2] is not None:
            constr_set.aperture_set.operable_construction = _subface_subset_[2]
        if _subface_subset_[3] is not None:
            constr_set.door_set.exterior_construction = _subface_subset_[3]
        if _subface_subset_[4] is not None:
            constr_set.door_set.overhead_construction = _subface_subset_[4]
        if _subface_subset_[5] is not None:
            constr_set.door_set.exterior_glass_construction = _subface_subset_[5]
    
    return constr_set

'''Create an exterior subset to use as input for the new construction set'''
def OpaqueConst(_name_, _materials):
    name = clean_and_id_ep_string('OpaqueConstruction') if _name_ is None else \
        clean_ep_string(_name_)

    material_objs = []
    for material in _materials:
        if isinstance(material, str):
            material = opaque_material_by_identifier(material)
            #material_objs.append(material)
        material_objs.append(material)

    constr = OpaqueConstruction(name, material_objs)
    if len(material_objs) > 1:
        constr.materials = material_objs
    if _name_ is not None:
        constr.display_name = _name_
        
    return constr

def WindConst(_name_, _materials, frame_):
    name = clean_and_id_ep_string('WindowConstruction') if _name_ is None else \
        clean_ep_string(_name_)

    material_objs = []
    for material in _materials:
        if isinstance(material, str):
            material = window_material_by_identifier(material)
        material_objs.append(material)

    #constr = WindowConstruction(name, material_objs, frame_)
    constr = WindowConstruction(name, material_objs)
    if _name_ is not None:
        constr.display_name = _name_
# To get any subset just get a list of materials as long as required from above
#from honeybee_energy.construction.opaque import OpaqueConstruction
#from honeybee_energy.construction.window import WindowConstruction
#constr = OpaqueConstruction(name, material_objs) # append each of this to a list
# latter use that list as input for new const set
# for windows
#constr = WindowConstruction(name, material_objs, frame_)

'''Get materials objects from keywords'''
# Get a list of materials by keyword
def OpaqueFromKwords(keywords_):
    #split_words = True if join_words_ is None else not join_words_
    split_words = True
    opaque_mats = sorted(filter_array_by_keywords(OPAQUE_MATERIALS, keywords_, split_words))
    return opaque_mats

def WindowFromKwords(keywords_):
    split_words = True
    opaque_mats = sorted(filter_array_by_keywords(WINDOW_MATERIALS, keywords_, split_words))
    return opaque_mats
    
''' Get a recomended construction set considering the climate'''

CONSTRUCTION_TYPES = ('SteelFramed', 'WoodFramed', 'Mass', 'Metal Building')

def ConstSetClimate(_climate_zone, _vintage_, _constr_type_):
    # check the climate zone
    # _climate_zone = _climate_zone[0]  # strip out any qualifiers like A, C, or C
    assert 1 <= int(_climate_zone) <= 8, 'Input _climate_zone "{}" is not valid. ' \
                                         'Climate zone must be between 1 and 8.'.format(_climate_zone)

    # check and set the default vintage
    if _vintage_ is not None:
        assert _vintage_ in STANDARDS_REGISTRY.keys(), \
            'Input _vintage_ "{}" is not valid. Choose from:\n' \
            '{}'.format(_vintage_, '\n'.join(STANDARDS_REGISTRY.keys()))
    else:
        _vintage_ = '2019'

    # check and set the default _constr_type_
    if _constr_type_ is not None:
        assert _constr_type_ in CONSTRUCTION_TYPES, \
            'Input _constr_type_ "{}" is not valid. Choose from:\n' \
            '{}'.format(_vintage_, '\n'.join(CONSTRUCTION_TYPES))
    else:
        _constr_type_ = 'SteelFramed'

    # join vintage, climate zone and construction type into a complete string
    constr_set = '{}::{}{}::{}'.format(_vintage_, 'ClimateZone', _climate_zone, _constr_type_)

    return constr_set

''' SEARCH PROGRAMME TYPE COMPONENT'''

def SearchPType(bldg_prog_, _vintage_, keywords_):
    if bldg_prog_ is not None:
        # set the default vintage
        _vintage_ = _vintage_ if _vintage_ is not None else '2019'
        try:  # get the available programs for the vintage
            vintage_subset = STANDARDS_REGISTRY[_vintage_]
        except KeyError:
            raise ValueError(
                'Input _vintage_ "{}" is not valid. Choose from:\n'
                '{}'.format(_vintage_, '\n'.join(STANDARDS_REGISTRY.keys())))
        try:  # get the available programs for the building type
            room_programs = vintage_subset[bldg_prog_]
        except KeyError:
            raise ValueError(
                'Input bldg_prog_ "{}" is not avaible for vintage "{}". Choose from:\n'
                '{}'.format(bldg_prog_, _vintage_, '\n'.join(vintage_subset.keys())))
        # apply any keywords
        if keywords_ != []:
            room_programs = filter_array_by_keywords(room_programs, keywords_, False)
        # join vintage, building program and room programs into a complete string
        room_prog = ['{}::{}::{}'.format(_vintage_, bldg_prog_, rp) for rp in room_programs]
    else:
        # return all programs in the library filtered by keyword
        room_prog = sorted(PROGRAM_TYPES)
        if _vintage_ is not None:
            room_prog = filter_array_by_keywords(room_prog, [_vintage_], False)
        if keywords_ != []:
            room_prog = filter_array_by_keywords(room_prog, keywords_, False)

    return room_prog

'''Create a new programme type'''
def NewProgramme(_name_, _people_, _lighting_, _electric_equip_, _gas_equip_,
                 _hot_water_, _infiltration_, _ventilation_, _setpoint_):
    # make sure the input name is in the right format
    name = clean_ep_string(_name_)
    
    # create new programme and assign name
    program = ProgramType(_name_)
    program.display_name = name

    # go through each input load and assign it to the set
    if _people_ is not None:
        program.people = _people_
    if _lighting_ is not None:
        program.lighting = _lighting_
    if _electric_equip_ is not None:
        program.electric_equipment = _electric_equip_
    if _gas_equip_ is not None:
        program.gas_equipment = _gas_equip_
    if _hot_water_ is not None:
        program.service_hot_water = _hot_water_
    if _infiltration_ is not None:
        program.infiltration = _infiltration_
    if _ventilation_ is not None:
        program.ventilation = _ventilation_
    if _setpoint_ is not None:
        program.setpoint = _setpoint_
        
    return program

'''Create each of the objects to generate a new programme'''
# Create each object with the following functions

# People
#from honeybee_energy.load.people import People
#people = People(name, _ppl_per_area, _occupancy_sch, _activity_sch_)
#people.display_name = _name_

# Lighting
#from honeybee_energy.load.lighting import Lighting
# return_fract_ = 0.0 # default value
# _radiant_fract_ = 0.32 # default value
# _visible_fract_ = 0.25 # default value
#lighting = Lighting(name, _watts_per_area, _schedule,
                    #return_fract_, _radiant_fract_, _visible_fract_)
#lighting.display_name = _name_
#lighting.baseline_watts_per_area # NO BASELINE, default: 11.084029 W/m2

# Electric equipment
#from honeybee_energy.load.equipment import ElectricEquipment, GasEquipment
#radiant_fract_, latent_fract_, lost_fract_ = 0, 0, 0 # default values
#equip = ElectricEquipment(name, _watts_per_area, _schedule,
                          #radiant_fract_, latent_fract_, lost_fract_)
#equip.display_name = _name_

# Gas equipment
#radiant_fract_, latent_fract_, lost_fract_ = 0, 0, 0 # default values
#equip = GasEquipment(name, _watts_per_area, _schedule,
                     #radiant_fract_, latent_fract_, lost_fract_)
#equip.display_name = _name_

# Hot water
#from honeybee_energy.load.hotwater import ServiceHotWater
#_target_temp_ = 60 # default
#_sensible_fract_ = 0.2 # default
#_latent_fract_ = 0.05 # default
#hot_water = ServiceHotWater(name, _flow_per_area, _schedule, _target_temp_,
                                #_sensible_fract_, _latent_fract_)
#hot_water.display_name = _name_

# Infiltration
#from honeybee_energy.load.infiltration import Infiltration
#infil = Infiltration(name, _flow_per_ext_area, _schedule_)
#infil.display_name = _name_

# Setpoints
#from honeybee_energy.load.setpoint import Setpoint
#setpoint = Setpoint(name, _heating_sch, _cooling_sch)
#setpoint.display_name = _name_
# add humidification and dehumidification setpoints if needed
#setpoint.humidifying_setpoint = humid_setpt_
#setpoint.dehumidifying_setpoint = dehumid_setpt_

'''Create schedules'''
# Check that inputs are in adequate format (list of 24 values, one per hour)
def check_sched_values(values):
    """Check that input schedules are valid and format them to all be 24 values."""
    if len(values) == 24:
        return values
    elif len(values) == 1:
        return values * 24
    else:
        raise ValueError(
            'Schedule values must be either 24 or 1. Not {}.'.format(len(values)))

# Create a weekly schedule object (only fractional)
def WeeklySch (_name_, weekday_sch, weekend_sch):
    # process any lists of single values such that they are all 24
    _sun = check_sched_values(weekend_sch)
    _mon = check_sched_values(weekday_sch)
    _tue = check_sched_values(weekday_sch)
    _wed = check_sched_values(weekday_sch)
    _thu = check_sched_values(weekday_sch)
    _fri = check_sched_values(weekday_sch)
    _sat = check_sched_values(weekend_sch)
    _holiday_ = _sun
    _summer_des_ = None
    _winter_des_ = None

    # get the ScheduleTypeLimit object
    _type_limit_ = schedule_type_limit_by_identifier('Fractional')

    # create the schedule object
    name = clean_ep_string(_name_)
    schedule = ScheduleRuleset.from_week_daily_values(
        name, _sun, _mon, _tue, _wed, _thu, _fri, _sat, _holiday_,
        timestep=1, schedule_type_limit=_type_limit_,
        summer_designday_values=_summer_des_, winter_designday_values=_winter_des_)
    
    schedule.display_name = _name_

    return schedule
    
# create a constant schedule
def ConstantSch(_name_, _type_limit_, _values):
    # get the ScheduleTypeLimit object
    # _type_limit_ can be: Fractional, On-off, Temperature, Activity level,
    # Power, humidity, angle, delta temperature, control level
    if _type_limit_ is None:
        _type_limit_ = schedule_type_limit_by_identifier('Fractional')
    elif isinstance(_type_limit_, str):
        _type_limit_ = schedule_type_limit_by_identifier(_type_limit_)

    # create the schedule object
    name = clean_ep_string(_name_)
    
    if len(_values) == 1:
        schedule = ScheduleRuleset.from_constant_value(name, _values[0], _type_limit_)
        #idf_text, constant_none = schedule.to_idf()
    else:
        schedule = ScheduleRuleset.from_daily_values(name, _values, timestep=1,
            schedule_type_limit=_type_limit_)
        #idf_year, idf_week = schedule.to_idf()
        #idf_days = [day_sch.to_idf(_type_limit_) for day_sch in schedule.day_schedules]
        #idf_text = [idf_year] + idf_week + idf_days if idf_week is not None \
    
    schedule.display_name = _name_
    
    return schedule

''' ROOM SOLID COMPONENT'''

def RoomSolid(_geo, _name_, _mod_set_, _constr_set_, _program_, conditioned_, _roof_angle_):
    # set the default roof angle
    roof_angle = _roof_angle_ if _roof_angle_ is not None else 60
    floor_angle = 180 - roof_angle

    rooms = []  # list of rooms that will be returned
    for i, geo in enumerate(_geo):
        
        # get the name for the Room        
        display_name = '{}_{}'.format(longest_list(_name_, i), i + 1) \
            if len(_name_) != len(_geo) else longest_list(_name_, i)
        name = clean_and_id_string(display_name)

        # create the Room
        room = Room.from_polyface3d(
            name, to_polyface3d(geo), roof_angle=roof_angle,
            floor_angle=floor_angle, ground_depth=tolerance)
        room.display_name = display_name

        # check that the Room geometry is closed.
        if room.check_solid(tolerance, angle_tolerance, False) != '':
            msg = 'Input _geo is not a closed volume.\n' \
                  'Room volume must be closed to access most honeybee features.\n' \
                  'Preview the output Room to see the holes in your model.'
            print(msg)
            #give_warning(ghenv.Component, msg)

        # try to assign the modifier set
        if len(_mod_set_) != 0:
            mod_set = longest_list(_mod_set_, i)
            if isinstance(mod_set, str):
                mod_set = modifier_set_by_identifier(mod_set)
            room.properties.radiance.modifier_set = mod_set

        # try to assign the construction set
        if len(_constr_set_) != 0:
            constr_set = longest_list(_constr_set_, i)
            if isinstance(constr_set, str):
                constr_set = construction_set_by_identifier(constr_set)
            room.properties.energy.construction_set = constr_set

        # try to assign the program
        if len(_program_) != 0:
            program = longest_list(_program_, i)
            if isinstance(program, str):
                try:
                    program = building_program_type_by_identifier(program)
                except ValueError:
                    program = program_type_by_identifier(program)
            room.properties.energy.program_type = program
        else:  # generic office program by default
            try:
                room.properties.energy.program_type = office_program
            except (NameError, AttributeError):
                pass  # honeybee-energy is not installed

        # try to assign an ideal air system
        if len(conditioned_) == 0 or longest_list(conditioned_, i):
            try:
                room.properties.energy.add_default_ideal_air()
            except (NameError, AttributeError):
                pass  # honeybee-energy is not installed

        rooms.append(room)

    return rooms


''' SOLVE ADJACENCY COMPONENT'''


def reversed_opaque_constr(construction):
    """Get a version of a given OpaqueConstruction that is reversed."""
    if construction.is_symmetric:
        return construction
    return OpaqueConstruction('{}_Rev'.format(construction.identifier),
                              [mat for mat in reversed(construction.materials)])


def reversed_window_constr(construction):
    """Get a version of a given WindowConstruction that is reversed."""
    if construction.is_symmetric:
        return construction
    return WindowConstruction('{}_Rev'.format(construction.identifier),
                              [mat for mat in reversed(construction.materials)])


def apply_constr_to_face(adjacent_faces, construction, face_type):
    """Apply a given construction to adjacent faces of a certain type."""
    rev_constr = reversed_opaque_constr(construction)
    for face_pair in adjacent_faces:
        if isinstance(face_pair[0].type, face_type):
            face_pair[0].properties.energy.construction = construction
            face_pair[1].properties.energy.construction = rev_constr
        elif isinstance(face_pair[1].type, face_type):
            face_pair[1].properties.energy.construction = construction
            face_pair[0].properties.energy.construction = rev_constr


def apply_constr_to_door(adjacent_doors, construction, is_glass):
    """Apply a given construction to adjacent doors of a certain type."""
    rev_constr = reversed_window_constr(construction) if is_glass else \
        reversed_opaque_constr(construction)
    for dr_pair in adjacent_doors:
        if dr_pair[0].is_glass is is_glass:
            dr_pair[1].properties.energy.construction = construction
            dr_pair[0].properties.energy.construction = rev_constr


def apply_ep_int_constr(adj_info, ep_int_constr):
    """Apply the interior construction subset list to adjacent objects."""
    assert len(ep_int_constr) == 6, 'Input ep_int_constr_ is not valid.'

    if ep_int_constr[0] is not None:
        apply_constr_to_face(adj_info['adjacent_faces'], ep_int_constr[0], Wall)
    if ep_int_constr[1] is not None:
        apply_constr_to_face(adj_info['adjacent_faces'], ep_int_constr[1], RoofCeiling)
    if ep_int_constr[2] is not None:
        apply_constr_to_face(adj_info['adjacent_faces'], ep_int_constr[2], Floor)
    if ep_int_constr[3] is not None:
        rev_constr = reversed_window_constr(ep_int_constr[3])
        for ap_pair in adj_info['adjacent_apertures']:
            ap_pair[1].properties.energy.construction = ep_int_constr[3]
            ap_pair[0].properties.energy.construction = rev_constr
    if ep_int_constr[4] is not None:
        apply_constr_to_door(adj_info['adjacent_doors'], ep_int_constr[4], False)
    if ep_int_constr[5] is not None:
        apply_constr_to_door(adj_info['adjacent_doors'], ep_int_constr[5], True)


def apply_mod_to_face(adjacent_faces, modifier, face_type):
    """Apply a given modifier to adjacent faces of a certain type."""
    for face_pair in adjacent_faces:
        if isinstance(face_pair[0].type, face_type):
            face_pair[0].properties.radiance.modifier = modifier
            face_pair[1].properties.radiance.modifier = modifier
        elif isinstance(face_pair[1].type, face_type):
            face_pair[1].properties.radiance.modifier = modifier
            face_pair[0].properties.radiance.modifier = modifier


def apply_mod_to_door(adjacent_doors, modifier, is_glass):
    """Apply a given modifier to adjacent doors of a certain type."""
    for dr_pair in adjacent_doors:
        if dr_pair[0].is_glass is is_glass:
            dr_pair[1].properties.radiance.modifier = modifier
            dr_pair[0].properties.radiance.modifier = modifier


def apply_rad_int_mod(adj_info, rad_int_mod):
    """Apply the interior modifier subset list to adjacent objects."""
    assert len(rad_int_mod) == 6, 'Input rad_int_mod_ is not valid.'

    if rad_int_mod[0] is not None:
        apply_mod_to_face(adj_info['adjacent_faces'], rad_int_mod[0], Wall)
    if rad_int_mod[1] is not None:
        apply_mod_to_face(adj_info['adjacent_faces'], rad_int_mod[1], RoofCeiling)
    if rad_int_mod[2] is not None:
        apply_mod_to_face(adj_info['adjacent_faces'], rad_int_mod[2], Floor)
    if rad_int_mod[3] is not None:
        for ap_pair in adj_info['adjacent_apertures']:
            ap_pair[1].properties.radiance.modifier = rad_int_mod[3]
            ap_pair[0].properties.radiance.modifier = rad_int_mod[3]
    if rad_int_mod[4] is not None:
        apply_mod_to_door(adj_info['adjacent_doors'], rad_int_mod[4], False)
    if rad_int_mod[5] is not None:
        apply_mod_to_door(adj_info['adjacent_doors'], rad_int_mod[5], True)


def SolveAdjacency(_rooms, ep_int_constr_, rad_int_mod_, adiabatic_, air_boundary_, overwrite_, _run):
    adj_rooms = [room.duplicate() for room in _rooms]  # duplicate the initial objects

    # solve adjacnecy
    if overwrite_:  # find adjscencies and re-assign them
        adj_aps = []
        adj_doors = []
        adj_faces = Room.find_adjacency(adj_rooms, tolerance)
        for face_pair in adj_faces:
            face_info = face_pair[0].set_adjacency(face_pair[1])
            adj_aps.extend(face_info['adjacent_apertures'])
            adj_doors.extend(face_info['adjacent_doors'])
        adj_info = {
            'adjacent_faces': adj_faces,
            'adjacent_apertures': adj_aps,
            'adjacent_doors': adj_doors
        }
    else:  # just solve for new adjacencies
        adj_info = Room.solve_adjacency(adj_rooms, tolerance)

    # try to assign the energyplus constructions if specified
    if len(ep_int_constr_) != 0:
        apply_ep_int_constr(adj_info, ep_int_constr_)

    # try to assign the radiance modifiers if specified
    if len(rad_int_mod_) != 0:
        apply_rad_int_mod(adj_info, rad_int_mod_)

    # try to assign the adiabatic boundary condition
    if adiabatic_:
        for face_pair in adj_info['adjacent_faces']:
            face_pair[0].boundary_condition = boundary_conditions.adiabatic
            face_pair[1].boundary_condition = boundary_conditions.adiabatic

    # try to assign the air boundary face type
    if air_boundary_:
        for face_pair in adj_info['adjacent_faces']:
            face_pair[0].type = face_types.air_boundary
            face_pair[1].type = face_types.air_boundary

    # report all of the adjacency information
    for adj_face in adj_info['adjacent_faces']:
        print('"{}" is adjacent to "{}"'.format(adj_face[0], adj_face[1]))

    return adj_rooms


''' APERTURES BY RATIO COMPONENT'''


def can_host_apeture(face):
    """Test if a face is intended to host apertures (according to this component)."""
    return isinstance(face.boundary_condition, Outdoors) and \
        isinstance(face.type, Wall)


def assign_apertures(face, sub, rat, hgt, sil, hor, vert, op):
    """Assign apertures to a Face based on a set of inputs."""
    if sub:
        face.apertures_by_ratio_rectangle(rat, hgt, sil, hor, vert, tolerance)
    else:
        face.apertures_by_ratio(rat, tolerance)

    # try to assign the operable property
    if op:
        for ap in face.apertures:
            ap.is_operable = op


def ApertByRatio(_hb_objs, _ratio, _subdivide_, _win_height_, _sill_height_, _horiz_separ_,
                 vert_separ_, operable_):
    # duplicate the initial objects
    hb_objs = [obj.duplicate() for obj in _hb_objs]

    # set defaults for any blank inputs
    conversion = conversion_to_meters()
    _subdivide_ = _subdivide_ if len(_subdivide_) != 0 else [True]
    _win_height_ = _win_height_ if len(_win_height_) != 0 else [2.0 / conversion]
    _sill_height_ = _sill_height_ if len(_sill_height_) != 0 else [0.8 / conversion]
    _horiz_separ_ = _horiz_separ_ if len(_horiz_separ_) != 0 else [3.0 / conversion]
    vert_separ_ = vert_separ_ if len(vert_separ_) != 0 else [0.0]
    operable_ = operable_ if len(operable_) != 0 else [False]

    # gather all of the inputs together
    all_inputs = [_subdivide_, _ratio, _win_height_, _sill_height_, _horiz_separ_,
                  vert_separ_, operable_]

    # ensure matching list lengths across all values
    all_inputs, num_orient = check_matching_inputs(all_inputs)

    # get a list of angles used to categorize the faces
    angles = angles_from_num_orient(num_orient)

    # loop through the input objects and add apertures
    for obj in hb_objs:
        if isinstance(obj, Room):
            for face in obj.faces:
                if can_host_apeture(face):
                    orient_i = face_orient_index(face, angles)
                    sub, rat, hgt, sil, hor, vert, op = inputs_by_index(orient_i, all_inputs)
                    assign_apertures(face, sub, rat, hgt, sil, hor, vert, op)
        elif isinstance(obj, Face):
            if can_host_apeture(obj):
                orient_i = face_orient_index(obj, angles)
                sub, rat, hgt, sil, hor, vert, op = inputs_by_index(orient_i, all_inputs)
                assign_apertures(obj, sub, rat, hgt, sil, hor, vert, op)
        else:
            raise TypeError(
                'Input _hb_objs must be a Room or Face. Not {}.'.format(type(obj)))

    return hb_objs


''' SHADE COMPONENT'''
meshing_parameters = Rhino.Geometry.MeshingParameters.FastRenderMesh


def Shd(_geo, _name_, attached_, ep_constr_, ep_trans_sch_, rad_mod_):
    shades = []  # list of shades that will be returned
    for j, geo in enumerate(_geo):
        if len(_name_) == 0:  # make a default Shade name
            name = display_name = clean_and_id_string('Shade')
        else:
            display_name = '{}_{}'.format(longest_list(_name_, j), j + 1) \
                if len(_name_) != len(_geo) else longest_list(_name_, j)
            name = clean_and_id_string(display_name)
        is_detached = not longest_list(attached_, j) if len(attached_) != 0 else True

        lb_faces = to_face3d(geo, meshing_parameters)
        for i, lb_face in enumerate(lb_faces):
            shd_name = '{}_{}'.format(name, i) if len(lb_faces) > 1 else name
            hb_shd = Shade(shd_name, lb_face, is_detached)
            hb_shd.display_name = display_name

            # try to assign the energyplus construction
            if len(ep_constr_) != 0:
                ep_constr = longest_list(ep_constr_, j)
                if isinstance(ep_constr, str):
                    ep_constr = shade_construction_by_identifier(ep_constr)
                hb_shd.properties.energy.construction = ep_constr

            # try to assign the energyplus transmittance schedule
            if len(ep_trans_sch_) != 0:
                ep_trans_sch = longest_list(ep_trans_sch_, j)
                if isinstance(ep_trans_sch, str):
                    ep_trans_sch = schedule_by_identifier(ep_trans_sch)
                hb_shd.properties.energy.transmittance_schedule = ep_trans_sch

            # try to assign the radiance modifier
            if len(rad_mod_) != 0:
                rad_mod = longest_list(rad_mod_, j)
                if isinstance(rad_mod, str):
                    rad_mod = modifier_by_identifier(rad_mod)
                hb_shd.properties.radiance.modifier = rad_mod

            shades.append(hb_shd)  # collect the final Shades
            i += 1  # advance the iterator
    # shades = wrap_output(shades)

    return shades


''' MODEL COMPONENT '''

def Mdl(rooms_, faces_, shades_, apertures_, doors_, _name_):
    # set a default name and get the Rhino Model units
    name = clean_string(_name_) if _name_ is not None else clean_and_id_string('unnamed')
    units = units_system()

    # create the model
    model = Model(name, rooms_, faces_, shades_, apertures_, doors_,
                  units=units, tolerance=tolerance, angle_tolerance=angle_tolerance)
    model.display_name = _name_ if _name_ is not None else 'unnamed'

    return model

'''Send model to local open studio'''
def ModToOSM(_model, _epw_file, _sim_par_, measures_, add_str_, _folder_, _write, run_):
    if _write:
        # check the presence of openstudio and check that the version is compatible
        check_openstudio_version()

        # process the simulation parameters
        if _sim_par_ is None:
            _sim_par_ = SimulationParameter()
            _sim_par_.output.add_zone_energy_use()
            _sim_par_.output.add_hvac_energy_use()
        else:
            _sim_par_ = _sim_par_.duplicate()  # ensure input is not edited

        # assign design days from the DDY next to the EPW if there are None
        if len(_sim_par_.sizing_parameter.design_days) == 0:
            msg = None
            folder, epw_file_name = os.path.split(_epw_file)
            ddy_file = os.path.join(folder, epw_file_name.replace('.epw', '.ddy'))
            if os.path.isfile(ddy_file):
                try:
                    _sim_par_.sizing_parameter.add_from_ddy_996_004(ddy_file)
                except AssertionError:
                    msg = 'No ddy_file_ was input into the _sim_par_ sizing ' \
                          'parameters\n and no design days were found in the .ddy file ' \
                          'next to the _epw_file.'
            else:
                msg = 'No ddy_file_ was input into the _sim_par_ sizing parameters\n' \
                      'and no .ddy file was found next to the _epw_file.'
            if msg is not None:
                epw_obj = EPW(_epw_file)
                des_days = [epw_obj.approximate_design_day('WinterDesignDay'),
                            epw_obj.approximate_design_day('SummerDesignDay')]
                _sim_par_.sizing_parameter.design_days = des_days
                msg = msg + '\nDesign days were generated from the input _epw_file but this ' \
                            '\nis not as accurate as design days from DDYs distributed with the EPW.'
                print(msg)

        # process the simulation folder name and the directory
        _folder_ = hb_config.folders.default_simulation_folder if _folder_ is None else _folder_
        clean_name = re.sub(r'[^.A-Za-z0-9_-]', '_', _model.display_name)
        directory = os.path.join(_folder_, clean_name, 'openstudio')

        # duplicate model to avoid mutating it as we edit it for energy simulation
        _model = _model.duplicate()
        # scale the model if the units are not meters
        if _model.units != 'Meters':
            _model.convert_to_units('Meters')
        # remove degenerate geometry within native E+ tolerance of 0.01 meters
        try:
            if _model.tolerance < 0.01:
                for room in _model.rooms:
                    try:
                        room.remove_colinear_vertices_envelope(
                            tolerance=_model.tolerance, delete_degenerate=True)
                    except AssertionError as e:  # room removed; likely wrong units
                        error = 'Failed to remove degenerate geometry.\n{}'.format(e)
                        raise ValueError(error)
            _model.remove_degenerate_geometry(0.01)
        except ValueError:
            error = 'Failed to remove degenerate Rooms.\nYour Model units system is: {}. ' \
                    'Is this correct?'.format(units_system())
            raise ValueError(error)

        # auto-assign stories if there are none since most OpenStudio measures need these
        if len(_model.stories) == 0 and len(_model.rooms) != 0:
            _model.assign_stories_by_floor_height()

        # delete any existing files in the directory and prepare it for simulation
        nukedir(directory, True)
        preparedir(directory)
        sch_directory = os.path.join(directory, 'schedules')
        preparedir(sch_directory)

        # write the model parameter JSONs
        model_dict = _model.to_dict(triangulate_sub_faces=True)
        _model.properties.energy.add_autocal_properties_to_dict(model_dict)
        model_json = os.path.join(directory, '{}.hbjson'.format(clean_name))
        try:
            with open(model_json, 'w') as fp:
                json.dump(model_dict, fp)
        except UnicodeDecodeError:  # non-unicode character in display_name
            with open(model_json, 'w') as fp:
                json.dump(model_dict, fp, ensure_ascii=False)

        # write the simulation parameter JSONs
        sim_par_dict = _sim_par_.to_dict()
        sim_par_json = os.path.join(directory, 'simulation_parameter.json')
        with open(sim_par_json, 'w') as fp:
            json.dump(sim_par_dict, fp)

        # process any measures input to the component
        measures = None if len(measures_) == 0 or measures_[0] is None else measures_
        no_report_meas = True if measures is None else \
            all(meas.type != 'ReportingMeasure' for meas in measures)
        str_inject = None if no_report_meas or add_str_ == [] or add_str_[0] is None \
            else '\n'.join(add_str_)

        # collect the two jsons for output and write out the osw file
        jsons = [model_json, sim_par_json]
        osw = to_openstudio_osw(
            directory, model_json, sim_par_json, additional_measures=measures,
            epw_file=_epw_file, schedule_directory=sch_directory,
            strings_to_inject=str_inject)

        # run the measure to translate the model JSON to an openstudio measure
        silent = True if run_ == 3 else False
        if run_ > 0 and not no_report_meas:  # everything must run with OS CLI
            if run_ == 1:  # simulate everything at once
                osm, idf = run_osw(osw, measures_only=False, silent=silent)
                sql, zsz, rdd, html, err = output_energyplus_files(os.path.dirname(idf))
            else:  # remove reporting measure and give a warning
                m_to_remove = [m.identifier for m in measures if m.type == 'ReportingMeasure']
                with open(osw, 'r') as op:
                    osw_data = json.load(op)
                s_to_remove = []
                for i, step in enumerate(osw_data['steps']):
                    if step['measure_dir_name'] in m_to_remove:
                        s_to_remove.append(i)
                for i in reversed(s_to_remove):
                    osw_data['steps'].pop(i)
                with open(osw, 'wb') as fp:
                    workflow_str = json.dumps(osw_data, indent=4, ensure_ascii=False)
                    fp.write(workflow_str.encode('utf-8'))
                msg = 'The following were reporting measures and were not\n' \
                      'included in the OSW to avoid running the simulation:\n{}'.format(
                    '\n'.join(m_to_remove))
                print(msg)
                osm, idf = run_osw(osw, silent=silent)
        elif run_ > 0:  # no reporting measure; simulate separately from measure application
            print ("OSW, silent", osw, silent)
            osm, idf = run_osw(osw, silent=silent)
            print ("OSM, IDF", osw, idf)
            # process the additional strings
            if len(add_str_) != 0 and add_str_[0] is not None and idf is not None:
                add_str = '\n'.join(add_str_)
                with open(idf, "a") as idf_file:
                    idf_file.write(add_str)
            if idf is None:  # measures failed to run correctly; parse out.osw
                log_osw = OSW(os.path.join(directory, 'out.osw'))
                #log_osw = OSW(os.path.join(directory, 'workflow.osw'))
                errors = []
                for error, tb in zip(log_osw.errors, log_osw.error_tracebacks):
                    if 'Cannot create a surface' in error:
                        error = 'Your Rhino Model units system is: {}. ' \
                                'Is this correct?\n{}'.format(units_system(), error)
                    print(tb)
                    errors.append(error)
                raise Exception('Failed to run OpenStudio CLI:\n{}'.format('\n'.join(errors)))
            elif run_ in (1, 3):  # run the resulting idf throught EnergyPlus
                sql, zsz, rdd, html, err = run_idf(idf, _epw_file, silent=silent)

        # parse the error log and report any warnings
        if run_ in (1, 3) and err is not None:
            err_obj = Err(err)
            print(err_obj.file_contents)
            for warn in err_obj.severe_errors:
                print(warn)
            for error in err_obj.fatal_errors:
                raise Exception(error)

        return jsons, osw, osm, idf, sql, zsz, rdd, html
    
'''Read results from local open studio'''
# Use the SQLiteResult class to parse the result files directly on Windows.
def get_results_windows(sql_files):
    results = eui_from_sql(sql_files)
    return results['eui'], results['total_floor_area'], results['end_uses']

def getEUI(_sql):    
    _sql = [_sql]

    # get the results
    eui, gross_floor, end_use_pairs = get_results_windows(_sql)

    # create separate lists for end use values and labels
    eui_end_use = end_use_pairs.values()
    end_uses = [use.replace('_', ' ').title() for use in end_use_pairs.keys()]

    return eui, eui_end_use, end_uses, gross_floor