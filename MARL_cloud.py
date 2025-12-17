# Install rhinoinside pip install rhinoinside
# Install ladybug-core pip install ladybug-core
# Install pollination streamlite pip install pollination-streamlit
# Install ladybug rhino pip install ladybug-rhino
# Install Rhino pip install Rhino
# Install honeybee pip install -U honeybee-core
# Install honeybee energy pip install honeybee-energy
# Install honeybee radiance pip install honeybee-radiance
# Install lbt_recipes pip install lbt-recipes


import rhinoinside
rhinoinside.load()

import pathlib
import json
import csv
import math
from datetime import datetime
import time
import os, shutil
import copy

from ladybug.epw import EPW

from pollination_streamlit.api.client import ApiClient
from pollination_streamlit.interactors import NewJob, Recipe

# The main dependency is lbt-honeybee
from herp.geo_gen_canvas_wneigh import Neighbourhood
from herp.honeybee_geom import NewConstSet, OpaqueFromKwords, WindowFromKwords,\
    ConstSetClimate, SearchPType, NewProgramme, WeeklySch, ConstantSch, RoomSolid\
    ,SolveAdjacency, ApertByRatio, Shd, Mdl, ModToOSM, getEUI, OpaqueConst, WindConst
from herp.honeybee_model import SimOut, SimPars, ShadCalc
from herp.pollination_interact import upload_models, check_study_status,\
    download_study_results, read_jsons, _download_results
    
from honeybee_energy.load.people import People
from honeybee_energy.load.lighting import Lighting
from honeybee_energy.load.equipment import ElectricEquipment, GasEquipment
from honeybee_energy.load.hotwater import ServiceHotWater
from honeybee_energy.load.infiltration import Infiltration
from honeybee_energy.load.setpoint import Setpoint
from honeybee_energy.lib.schedules import schedule_by_identifier
    
# Delete all the previously exisitng files in a folder
# REQUIRES AT LEAST ONE PRE EXISITNG FILE IN THE FOLDER
def clear_folder(fold_name):                
    for filename in os.listdir(fold_name):
        file_path = os.path.join(fold_name, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))
            
#####
# BASIC INPUTS
#####

#### TO MINIMISE OR MAXIMISE COMMENT OR UNCOMMENT THE LINES IN THE LEARNING SECTION

# Local or cloud execution
# On local execution you need to execute in admin mode to allow OS delete files
poss_execution = ["Cloud", "Local"]
execution = poss_execution[1]

# Cooperative or competitve interaction between agents
mode_keyw = ["Cooperative", "Competitive"]
mode = mode_keyw[1]

recom_tolerances = {"Cooperative":0.01, "Competitive":0.01}

tolerance = recom_tolerances[mode]

# Location
poss_locations = ["Arequipa", "Piura", "Juliaca", "Tarapoto"]
my_location = poss_locations[3]

# Identified initial sequence of actions to achieve basic module shape
# (we test in rhino until we get a desired initial shape)
basic_mod_stps = [2, 1, 2, 5, 7]

# Initial non-dormitories (socio csv only counts dormitories)
initial_nondorm = 4

# Name of the csv file resulting from the socio-economic simulation
socio_econ_result = 'final_soc_mod.csv'

# Choose the computer from where execute
computer_choices = ["my_laptop", "my_desktop", "area21", "test_C"]
computer_choice = computer_choices[3]

# Project folder name when executed in the cloud
cloud_pj_name = "Juliaca_max"

# If you want to avoid the learning simply reproduce the results
avoid_learn = False
# when the above is set to true, it will read my_recoverpath ("recover_years.csv")
            
#####
# Set working directories
#####
if computer_choice == computer_choices[0]:
    # The root folder contains all subfolders
    root_fold = pathlib.Path(f'C:/Users/arr18sep/Desktop/Tests/pollination')
    
    # In string version (for certain functions only accept string)
    csv_out = 'C:/Users/arr18sep/Desktop/Tests/pollination'

elif computer_choice == computer_choices[1]:
    # The root folder contains all subfolders
    root_fold = pathlib.Path(f'C:/Users/arr18sep/Desktop/pollination')

    # In string version (for certain functions only accept string)
    csv_out = "C:/Users/arr18sep/Desktop/pollination"
    
elif computer_choice == computer_choices[2]:
    # The root folder contains all subfolders
    root_fold = pathlib.Path(f'D:/SERGIO/PHDandMORE/PAPERS/New_results')

    # In string version (for certain functions only accept string)
    csv_out = "D:/SERGIO/PHDandMORE/PAPERS/New_results"
    
elif computer_choice == computer_choices[3]:
    # The root folder contains all subfolders
    root_fold = pathlib.Path(f'C:/New_results')

    # In string version (for certain functions only accept string)
    csv_out = "C:/New_results"

# The UP folder contains all common files to upload and a subfolder with models
up_folder_pth = pathlib.Path(root_fold.joinpath('UP'))

# The MODELS subfolder contains all the models, replaced each generation
model_fld = pathlib.Path(up_folder_pth.joinpath('MODELS')) # save here the hbjsons

# Location to save jsons for local execution in string version
model_fld_2 = str(up_folder_pth) + '/LOCAL'

# The DOWN folder contains all the results of the cloud process
down_folder = pathlib.Path(root_fold.joinpath('DOWN')) # get resulting jsons from here

######
# Recovery Mode
######
# Recover actions learned in past years
my_recoverpath = csv_out + "\\" + "recover_years.csv"
if os.path.isfile(my_recoverpath):
    # Get dictionary from csv
    with open(my_recoverpath, 'r') as file:
        dict_reader = csv.DictReader(file)
        list_of_years = list(dict_reader)        
    recover_years = True
else:
    recover_years = False


# Recover an incomplete learning process
# If there is a recover file open it a keep it as a list of dicts
my_savepath = csv_out + "\\" + "recover_data.csv"
if os.path.isfile(my_savepath):
    # Get dictionary from csv
    with open(my_savepath, 'r') as file:
        dict_reader = csv.DictReader(file)
        list_of_dict = list(dict_reader)
    
    recover_file = True
else:
    recover_file = False

#####
# Import epw and get ddy (if unexistent)
#####
# List of possible epw
epw_list = {'Arequipa': 'PER_Arequipa.847520_IWEC',
            'Piura': 'PER_PIU_Piura-Iberico.Intl.AP.844010_TMYx.2007-2021',
            'Juliaca': 'PER_PUN_Juliaca-Manco.AP.847350_TMYx.2007-2021',
            'Tarapoto': 'PER_SAM_Tarapoto-Paredes.AP.844550_TMYx.2007-2021'}

# Import EPW
epw_path = up_folder_pth.joinpath(epw_list[my_location] + '.epw')
epwpath_str = str(epw_path)
my_epw = EPW(epw_path)

# Transform to ddy if it does not exist
ddy_path = up_folder_pth.joinpath(epw_list[my_location] + '.ddy')
if not ddy_path.is_file():
    _percentile_ = 0.4    
    ddy_str = str(ddy_path)
    my_epw.to_ddy(ddy_str, _percentile_)

#####
# Import csv file from socio-economic model
######
# Name of the socio-economic output file
soc_input = csv_out + '/' + socio_econ_result # Name of the file
input_file = csv.DictReader(open(soc_input))

# Recover learning inputs from social model
# Get number of years that the social model ran and number of agents to generate
years_l = []
agents_l = []

for row in input_file:
    years_l.append(int(row["Year"]))
    agents_l.append(int(row["Agents"]))

years = max(years_l) + 1
nr_agents = max(agents_l) + 1

'''GET SETTINGS FOR ENERGY PLUS SIMULATION'''
#####
# Set common inputs for geometry transformation (rhino to hbjson)
####
# Get rooms from solids
my_modset = [] # These should be radiance modifier sets
myConditioned = [True]
my_roofangle = 60

# Solve the adjacency among rooms
#my_intconst_sset = [] # This is the interior construction subset
#my_radind_mod = [] # This is a radiance interior material subset modifier
#my_adiabatic = False
#my_airbound = False
#my_overwrite = False
#solve_now = True

# Get Apertures by ratio
my_aper_ratio = [0.25]
my_subdivision = [False]
my_win_hgt = [] # This is the target height of the aperture
my_sill_hgt = [] # This is the target height of the sill
my_h_sep = [] # This is the horizontal separation between apertures on one face
my_v_sep = [] # This is the vertical separation between apertures on one face
my_oper_apert = [False] # If the apertures are operable

# Get shades
context_attach = [False] # Not attached to other object
my_shade_energyconst = [] # A string, only tells reflectance, defined by ShadeConstr
my_shd_transm = []
my_radshd_mod = [] # Radiance modifier for shade, can be text

# Get model
my_faces = []
my_shades2 = []
my_apertures = []
my_doors = []

#####
# Get a construction set
#####
## Exterior subset
### Walls
extw_name = "My_ext_walls"
print (OpaqueFromKwords("stucco 7/8"))
extw1 = OpaqueFromKwords("stucco 7/8")[0]
extw2 = OpaqueFromKwords("4 in concrete wall")[0]
extw = OpaqueConst(extw_name, [extw1, extw2, extw1])

### Roof
extr_name = "My_ext_roof"
extr1 = OpaqueFromKwords("generic membrane")[0]
extr2 = OpaqueFromKwords("8 in concrete floor")[0]
extr3 = extw1
extr = OpaqueConst(extr_name, [extr1, extr2, extr3])

### Exposed floor
expfl_name = "My_exp_floor"
expfl_ = extr2
expfl = OpaqueConst(expfl_name, [expfl_])

## Ground subset
### Walls and roof are the same as previous
### Ground floor
grdfl_name = "my_groundfloor_fl"
grdfl_ = OpaqueFromKwords("concrete pavement")[0]
grdfl = OpaqueConst(grdfl_name, [grdfl_])

## Interior subset
### No interior subset

## Subface subset
### Windows
wind_mat_name = "My_window_mat"
wind_mat = WindowFromKwords("u 0.11 0.34")[0]
windows_ = WindConst(wind_mat_name, [wind_mat], None) # frame, which is optional

### Skylight
# None

### Operable
# Same as windows

### Exterior door
door_mat_name = "my_door_mat"
door_mat1 = OpaqueFromKwords("plywood cbes")[0]
door_mat2 = OpaqueFromKwords("generic wall air")[0]
doors_ = OpaqueConst(door_mat_name, [door_mat1, door_mat2, door_mat1]) # frame, which is optional

### Overhead door
# None

### Glass door
# None

## Create a new construction set
my_ext_sset = [extw, extr, expfl] # exterior subset
my_ground_set = [extw, extr, grdfl] # ground subset
_interior_subset_ = []
my_sface_sset = [windows_, None, None, doors_, None, None] # subface subset

name_const_set = "My_const_set"
my_CSetClim = NewConstSet(name_const_set, my_ext_sset, my_ground_set, 
                           _interior_subset_, my_sface_sset)

# Get a recommended construction set by climate zone (ASHRAE)
# climzs = ["Very Hot", "Hot", "Warm", "Mixed", "Cool", "Cold", "Very Cold", "Subarctic"]
# my_climz = climzs.index("Warm") + 1 # Because ASHRAE starts in 1

# vintages = ["2019", "2016", "2013", "2010", "2007", "2004", "1980_2004", "pre_1980"]
# my_vintage = vintages[0]

# cons_types = ["SteelFramed", "WoodFramed", "Mass", "Metal Building"]
# my_ctype = cons_types[2]

# my_CSetClim = ConstSetClimate(my_climz, my_vintage, my_ctype)

#####
# Get a programme
#####
# Schedules
## People occupancy schedule
peop_sleep = [1 for i in range(6)]
peop_wakeup = [0.5 for i in range(2)]
peop_work = [0.25 for i in range(9)]
peop_comeback = [0.5 for i in range(4)]
peop_goodnight = [1 for i in range(3)]
peop_wday = peop_sleep + peop_wakeup + peop_work + peop_comeback + peop_goodnight
peop_rest = [0.75 for i in range(15)]
peop_wend = peop_sleep + peop_rest + peop_goodnight
peop_sch = WeeklySch("people_schedule", peop_wday, peop_wend)

## Light use schedule
light_sleep = [0.0 for i in range(6)]
light_dawn = [0.5 for i in range(2)]
light_day = [0.0 for i in range(9)]
light_dusk = [0.5 for i in range(2)]
light_night = [1 for i in range(3)]
light_sleep2 = [0.0 for i in range(2)]
light_use = light_sleep + light_dawn + light_day + light_dusk + light_night + light_sleep2
light_sch = WeeklySch("light_schedule", light_use, light_use)

## Equipment use schedule
eq_sleep = light_sleep # 0-6hrs
eq_dawn = light_dawn # 6-8hrs
eq_day = peop_work # 8-17hrs
eq_dusk = light_dusk # 17-19hrs
eq_night = [0.5 for i in range(3)] # 19-22hrs
eq_sleep2 = light_sleep2 # 22-24hrs
eq_use = eq_sleep + eq_dawn + eq_day + eq_dusk + eq_night + eq_sleep2
eq_rest = [0.5 for i in range(11)] # 8-19hrs
eq_wend = eq_sleep + eq_dawn + eq_rest + eq_night + eq_sleep2
eq_sch = WeeklySch("equipment_schedule", eq_use, eq_wend)

## Gas equipment schedule
gas_sleep = light_sleep # 0-6hrs
gas_breakfast = [1.0 for i in range(1)] # 6-7hrs
gas_morning = [0.0 for i in range(4)] # 7-11hrs
gas_lunch = [1.0 for i in range(2)] # 11-13hrs
gas_afternoon = [0.0 for i in range(4)] # 13-17hrs
gas_diner = [1.0 for i in range(1)] # 17-18hrs
gas_night = [0.0 for i in range(6)] # 18-24hrs
gas_use = gas_sleep + gas_breakfast + gas_morning + gas_lunch + gas_afternoon + gas_diner + gas_night
gas_sch = WeeklySch("gas_schedule", gas_use, gas_use)

## Hot water use schedule
hotw_sleep = light_sleep # 0-6hrs
hotw_early = [0.5 for i in range(1)] # 6-7hrs
hotw_day = [0.0 for i in range(11)] # 7-18hrs
hotw_late = [0.5 for i in range(1)] # 18-19hrs
hotw_night = [0.0 for i in range(5)] # 19-24hrs
hotw_use = hotw_sleep + hotw_early + hotw_day + hotw_late + hotw_night
hotw_sch = WeeklySch("hotwater_schedule", hotw_use, hotw_use)

## Setpoint temp/humid schedule
cool_spoint = [24]
heat_spoint = [18]
hum_spoint = [30]
dhum_spoint = [70]

cool_sch = ConstantSch("cooling_schedule", "Temperature", cool_spoint)
heat_sch = ConstantSch("heating_schedule", "Temperature", heat_spoint)

# Get objects needed for the programme
## People
my_pep_name = "My_People"
my_human_density = 0.1
my_people = People(my_pep_name, my_human_density, peop_sch, None) # None is activity schedule

## Lighting
my_light_name = "My_lights"
watts_light = 3.15
return_fract_ = 0.0 # default value
_radiant_fract_ = 0.32 # default value
_visible_fract_ = 0.25 # default value
lighting = Lighting(my_light_name, watts_light, light_sch,
                    return_fract_, _radiant_fract_, _visible_fract_)
#lighting.baseline_watts_per_area # NO BASELINE, default: 11.084029 W/m2

## Electric equipment
my_eq_name = "My_equipement"
watts_eq = 6.56
radiant_fract_, latent_fract_, lost_fract_ = 0, 0, 0 # default values
equip = ElectricEquipment(my_eq_name, watts_eq , eq_sch,
                          radiant_fract_, latent_fract_, lost_fract_)

## Gas equipment
my_gas_name = "My_gas_equipement"
watts_gas = 2.93
radiant_fract_, latent_fract_, lost_fract_ = 0, 0, 0 # default values
Gequip = GasEquipment(my_gas_name, watts_gas, gas_sch,
                     radiant_fract_, latent_fract_, lost_fract_)

## Hot water
my_hotw_name = "My_hot_water"
my_hotw_flow = 0.2
_target_temp_, _sensible_fract_, _latent_fract_ = 60, 0.2, 0.05 # default
hot_water = ServiceHotWater(my_hotw_name, my_hotw_flow, hotw_sch, _target_temp_,
                                _sensible_fract_, _latent_fract_)

## Infiltration
my_infil_name = "My_infiltration"
my_flow = 0.0003 # recommended for average building
infil = Infiltration(my_infil_name, my_flow, schedule_by_identifier('Always On'))

## Setpoints
my_spoint_name = "My_setpoint"
setpoint = Setpoint(my_spoint_name, heat_sch, cool_sch)

# add humidification and dehumidification setpoints if needed
#setpoint.humidifying_setpoint = hum_spoint
#setpoint.dehumidifying_setpoint = dhum_spoint

# Finally, create programme object
my_ptype_name = "MyProgramme"
my_ventilation = None
myPType = NewProgramme(my_ptype_name, my_people, lighting, equip, Gequip,
                 hot_water, infil, my_ventilation, setpoint)

# Get a pre existing programme type from honeybee
# bldg_progs = ["LargeOffice", "MediumOffice", "SmallOffice", "MidriseApartment", "HighriseApartment",
#               "Retail", "StripMall", "PrimarySchool", "SecondarySchool", "SmallHotel", "LargeHotel",
#               "Hospital", "Outpatient", "Laboratory", "Warehouse", "SuperMarket", "FullServiceRestaurant",
#               "QuickServiceRestaurant", "Courthouse", "LargeDataCenterHighITE", "LargeDataCenterLowITE",
#               "SmallDataCenterHighITE", "SmallDataCenterLowITE"]
# my_bldgprog = "MidriseApartment"
# poss_keyw = ["Apartment", "Corridor", "Office"] # Possible programmes in a midrise apartment
# my_keyw = poss_keyw[0]

# myPType = SearchPType(my_bldgprog , my_vintage, my_keyw)

####
# Set simulation parameters
####
# Set simulation outputs
my_zone_eu = True
my_hvac_eu = False
my_gains_loses = False
my_comfort_m = False
my_surf_temp = False
my_surf_e_flow = False
load_types = ["All", "Total", "Sensible", "Latent"]
freq_types = ["Annual", "Monthly", "Daily", "Hourly", "Timestep"]
my_load_type = load_types[0]
my_freq_type = freq_types[0]

my_simout = SimOut(my_zone_eu, my_hvac_eu, my_gains_loses, my_comfort_m, my_surf_temp,
    my_surf_e_flow, my_load_type, my_freq_type)

# Set simulation parameters
my_north = 180
my_run_period = None #ladybug AnalysisPeriod
my_daylight_saving = None #ladybug AnalysisPeriod
my_holidays = [] #ladybug Date object
my_startday = "Sunday"
my_tstep = 1 # Number of timesteps per hour
my_terrain = "Urban" # type of terrain, can be Ocean, Country, Suburbs, Urban, City
my_simcontrol = None #HB Simulation control object
my_shadow_calc = ShadCalc(None, None, None, 365, None) #HB Shadow calculation
# with default params but perform one shadow calc per day
my_sizing = None #HB sizing parameter (sizing of heating and cooling)

my_simPars = SimPars(my_north, my_simout, my_run_period, my_daylight_saving, my_holidays, my_startday,
                     my_tstep, my_terrain, my_simcontrol , my_shadow_calc, my_sizing)
    
#####
# Prepare files for the cloud (or local execution)
#####    
if execution == poss_execution[0]: # Cloud mode
    api_key = '88CC1590.FA6740239222CB769DB9573C'
    assert api_key is not None, 'You must provide valid Pollination API key.'
    
    # project details
    owner = 'centipede-llc'
    project = cloud_pj_name
    name = 'MARL'
    api_client = ApiClient(api_token=api_key)
    
    # Convert HB sim parameter option to json
    dict_simpars = my_simPars.to_dict()
    simpar_path = up_folder_pth.joinpath('sim_pars.json')
    
    with open(simpar_path, 'w') as outfile:
        json.dump(dict_simpars, outfile)
    
    # Upload persistent setting files to the cloud (ddy/sim_par/epw)
    study_name = "Piura Individual"
    
    recipe = Recipe('ladybug-tools', 'annual-energy-use', '0.5.3', client=api_client)
    new_study = NewJob(owner, project, recipe, client=api_client)
    new_study.name = study_name
    new_study.description = f'Annual Energy Simulation {study_name}'
    
    epw_cloud = new_study.upload_artifact(epw_path, target_folder='weather-data')
    ddy_cloud = new_study.upload_artifact(ddy_path, target_folder='weather-data')
    pars_cloud = new_study.upload_artifact(simpar_path, target_folder='sim-par')


'''NOW CREATE THE AGENTS ACCORDING TO THE SOCIO-ECONOMIC SETTINGS'''
#####
# Generate Agents
#####
"""Distribute the agents in blocks
This script only accepts even number of agents, 
as all blocks are identical and double sided"""

if nr_agents % 2 != 0:
    nr_agents -= 1

n_neighrows = 2
n_neighcols = 3
n_blocks = n_neighrows * n_neighcols

lots_per_side = (nr_agents/2)/n_blocks

# TEMPORARILY OVERRIDE NUMBER OF AGENTS
#nr_agents = 10

# region Create agents
lotorigx = 0
lotorigy = 0
lotsizex = 3
lotsizey = 3
my_module = 2.7
coreorigx = 0
coreorigy = 0
coresizex = 1
coresizey = 1
maxheight = 3

NrlotsOnSide = int(lots_per_side)
doubleside = True

mainsideXorY = True
radius_neighid = my_module * 4

# Not working inputs
space_needed = 0
my_wcost = 200
my_rcost = 500

# Exlusive to neighbourhood class
my_nrblocksX = n_neighcols
my_nrblocksY = n_neighrows
my_streetwith = 11

# Does not matter how many inputs are
# divide among two (number of rows) and floor()
# then that between 6 (number of blocks)
# That is the number of lots on one side
# always set doubleside to true

my_neigh = Neighbourhood(lotorigx, lotorigy, my_nrblocksX, my_nrblocksY, my_streetwith, 
                         lotsizex, lotsizey, my_module, coreorigx, coreorigy, coresizex,
                         coresizey, maxheight, NrlotsOnSide, doubleside, 
                         mainsideXorY, radius_neighid, space_needed, my_wcost,
                         my_rcost)   

#####
# Finally set learning settings
#####
'''Number of steps, space needed, epsilon and learning rate are defined for each year of sim
budget is not useful for the type of CSV input'''
episodes = 200
GOAL_REWARD = 25
TIME_PENALTY = 1
DISCOUNT = 0.9
lowest_lr = 0.1
lowest_ep = 0.005

# Set learning auto-stop inputs
'''We look back a determinate number of episodes (related to the max possible episodes) to get a percentage
of losing episodes. When the proportion of losing episodes is low enough, stop'''
lookback_f = 10  # factor to look back, the higher the less episode we see in the past
n_count_epis = int(math.ceil(episodes / lookback_f))  # Number of episodes to count to determine stop learning
stop_prop = 0.75 # Wining are 75% or more



'''HERE STARTS THE ACTUAL SIMULATION'''
#####
# Learning process
#####
if not avoid_learn:
    # time for processing performance
    outer_start = time.time()
    
    # Time for file names
    current_date = datetime.now().strftime("%d%m%Y_%H%M")
    
    # If you want to have an internal calculation of the cost (related to the const size)
    # you can put here a list that stores the accumulated savings per household
    # the input of the CSV will then be number of members and yearly balance
    # on python you add balance to acc savings, detemrmine need,
    # take out money for construction and take loans
    
    # Performances for each agent/size
    perm_perfs = {agent_nr:{} for agent_nr in my_neigh.AgInNeigh}
    
    # Winning actions store the latest set of actions leading to victory every year
    winact_rec = {agent_num:{} for agent_num in my_neigh.AgInNeigh}
    
    if recover_years: # when recovery file, fill the dictionary
        for dct in list_of_years:
            # Get list of int for actions from joined string
            real_act = list(dct["actions"].split('_'))
            real_act = [int(i) for i in real_act]
            
            # Replace values on winact list
            winact_rec[dct["agent_id"]][int(dct["year"])] = real_act
    
    # Dictionary to store performances and avoid double simulation
    avoid_sim = {}
    
    autostop, kill_flag = False, False
    
    # The following is a attribute of the neigh class
    # Make sure to create deep copies to avoid modyfing this variable
    every_n = my_neigh.RangeViewN()
    
    # Run our sim for the same amount of year that the soc sim ran
    print ("##########")
    print ("__________")
    print ("Starting simulation. Mode :{}".format(mode))
    print ("__________")
    print ("##########")
    for year in range(years):
        print ("++++++++++")
        print ("Starting Year {} out of {}".format(year, years))
        print ("++++++++++")
        
        # temporary skip year 0
        #if year == 0:
            #continue
        
        # If year on recovery file, avoid the current year
        if recover_years:
            for dct in list_of_years:
                if int(dct["year"]) == year:
                    year_found = True
                    break
                else:
                    year_found = False
            if year_found:
                print ("Policy found for this year, continuing with next")
                continue
        
        # Read current year from socio-economic CSV file
        exp_size = {}  # agent, size tuples for this year
        # read socio economic file
        input_file = csv.DictReader(open(soc_input))
        for row in input_file:
            if row["Year"] == str(year):
                # Add non-doritories to size
                thiy_szs = int(row["Size"]) + initial_nondorm
                
                # From csv ID to system ID
                ag_sysID = my_neigh.AgInNeigh[int(row["Agents"])]
                
                # Save
                exp_size[ag_sysID] = thiy_szs
    
        # Get sizes and agents
        act_sizes = {} #  Size at the beggining of the year
        spaces_needed = {} # How much we need to meet need
        particip2 = [] # who needs at least one space this year
        
        # Modify geometry to start the learning process and save coords in csv           
        for agent_ID in my_neigh.AgInNeigh:
            this_agent = my_neigh.GetAgentbyID(agent_ID)
            
            # re-start geometry
            this_agent.Extend(-1) 
            
            # Extend to the basic module size
            for init_actn in basic_mod_stps:
                this_agent.Extend(init_actn)
            
            # Add additional actions from past years
            sum_acts = []
            for this_yy in range(year): # visits all past years
                if this_yy in winact_rec[agent_ID]:
                    if len(winact_rec[agent_ID][this_yy]) > 0:
                        # add latest winning policy to current list
                        sum_acts += winact_rec[agent_ID][this_yy]
            if len(sum_acts) > 0:
                for act in sum_acts:
                    this_agent.Extend(act)
            
            # Record size at the beggining of the year
            act_sizes[agent_ID] = this_agent.NOccupiedPts
    
            # Determine size of space needed and if participating (>0)
            need = exp_size[agent_ID] - this_agent.NOccupiedPts
            if need < 0: # Error, not possible
                print ("expected size is lower than actual size")
                break 
            elif need == 0: # Agent does not grow, but record the figure
                spaces_needed[agent_ID] = need 
            else: # Agent grows this yy, keep how much and store ID in a list
                particip2.append(agent_ID)
                spaces_needed[agent_ID] = need
                
            # Save coordinates and construction activity per year
            # PUT PART OF THIS IN A MODULE IMPORT
            ######
            my_coords = this_agent.VertixLots
            
            myxs = []
            myys = []
            for vertxx in my_coords:
                myxs.append(vertxx.X)
                myys.append(vertxx.Y)
            
            maxx, maxy = max(myxs), max(myys)
            minx, miny = min(myxs), min(myys)

            if mainsideXorY: # alter it considering open spaces    
                minx -= this_agent.Module/2
                maxx += this_agent.Module
            else:
                miny -= this_agent.Module/2
                maxy += this_agent.Module

            this_line = {} 
            this_line["Origin"] = str(minx) + "_" + str(miny)
            this_line["Width"] = str(maxx - minx)
            this_line["Heigth"] = str(maxy - miny)
            this_line["Agent_Id"] = agent_ID
            this_line["Socec_Id"] = my_neigh.AgInNeigh.index(agent_ID)
            this_line["Year"] = year
            this_line["Build"] = need
            this_line["Mode"] = mode
            this_line["Location"] = my_location
            
            # Save the year construction activity in a csv
            my_coord_csv = csv_out + "\\" + "coords" + current_date + ".csv"
            tew_file = not os.path.isfile(my_coord_csv)
            with open(my_coord_csv, 'a', newline='') as out_file:
                fc = csv.DictWriter(out_file, this_line.keys())
                if tew_file:
                    fc.writeheader()
                fc.writerow(this_line)
            #####
            
    
        # Get all neighbours for participating agents (to build q tables)
        all_neighs2 = [value for key, value in every_n.items() if key in particip2]
        # flatten list of lists
        all_neighs2 = [item for slist in all_neighs2 for item in slist]    
        # delete duplicates
        all_neighs2 = list(dict.fromkeys(all_neighs2))    
        # Join the neighbours list with the participants list
        particip3 = particip2 + all_neighs2
        # delete dupliucates
        particip3 = list(dict.fromkeys(particip3))
        # When in a cooperative mode , I need the geometries of the neighs of neighs as shadows
        if mode == mode_keyw[0]:
            neighs_of_neighs = [value for key, value in every_n.items() if key in all_neighs2] 
            # flatten list of lists
            neighs_of_neighs = [item for slist in neighs_of_neighs for item in slist]
            # delete dupolicates
            neighs_of_neighs = list(dict.fromkeys(neighs_of_neighs))
            # Join participants, neighbours and neighbours of neighbours
            particip4 = particip3 + neighs_of_neighs
            # delete duplicates
            particip4 = list(dict.fromkeys(particip4))
        else:
            particip4 = particip3
                
        # Set the rest of inputs for the learning process (expire with year)
        steps = max(spaces_needed.values())  # according to the max need
        if steps > 0: # AT LEAST ONE AGENT GROWS!
            max_tot_iters = steps * episodes
        
            # budget = 10000 # Not useful yet!
            LEARNING_RATE = 0.99  # Restart every year
            EPSILON = 0.99  # Restart every year
            EPS_DECAY = (lowest_ep / EPSILON) ** (1 / max_tot_iters)  # depends on the number of steps
            LR_DECAY = (lowest_lr / LEARNING_RATE) ** (1 / max_tot_iters)  # depends on the number of steps
            
            # episode results (winning or losing, triggers auto-stop)
            results = {}
            
            # Only work with the active agents
            # list of dictionaries to remember when episodes are successful
            #count_wins = {agent_num:{} for agent_num in my_neigh.AgInNeigh}
            count_wins = {agent_num:{} for agent_num in particip2}
            
            # The partial winning policies dictionary to be renewed each year
            #part_winact = {agent_num:{} for agent_num in my_neigh.AgInNeigh}
            part_winact = {agent_num:{} for agent_num in particip2}
            
            # Manually override the code of the study submited to the cloud
            #study_codes = ['26b04468-d13d-4502-9ad1-75c6a357100d']
            
            # Create the learning tables to be used this year
            poss_acts_0 = my_neigh.GetInitPossActsN(particip3) # Must include neighbours as q table asks
            jstates_0 = my_neigh.GetInitJStatesN(particip3) # Must include neighbours as q table asks
    
            qtables, st_ja_tab = my_neigh.GetMultiQtablesN(poss_acts_0, jstates_0, particip2)  # Get selected q-tables
            
            # Because we do not start from 0, use this to retrieve current state
            # GET NEW STATES AND POSSIBLE ACTIONS
            states_add = my_neigh.GetJStatesN(particip3) # Must include all agents as q table asks for neighbours
            poss_acts_add = my_neigh.GetAvailActsN(particip3) # Must include all agents as q table asks for neighbours
    
            # CHECK IF NEW STATE AND POSSIBLE ACTIONS EXIST IN CURRENT Q-TABLE. IF NOT, ADD
            qtables, st_ja_tab = my_neigh.CheckQtableN(qtables, st_ja_tab, states_add, poss_acts_add, particip2)
    
            # Performance record dictionaries
            #my_rdicts = {agent_num:{} for agent_num in my_neigh.AgInNeigh}
            my_rdicts = {agent_num:{} for agent_num in particip2}
            
            # time
            inner_start = time.time()
            
        else: # if no agent grows this year, end the year
            continue    
    
        ####
        # LEARNING PROCESS
        ####
        for episode in range(episodes):
            print ("________________")
            print ("Continuing with episode {} of year {}".format(episode, year))
            print ("________________")
            
            # RE-START THE GEOMETRIES (APPLIES TO ALL AGENTS IN THE NEIGHBOURHOOD)
            # On episode 0, the geometry is restarted when the steps are calculated
            if episode != 0:
                # on year 0 we only need to set the geometry to its initial state
                # Including neighs of neighs in coop mode              
                for agent_ID in particip4:
                    # restart agent to 1 cube
                    this_agent = my_neigh.GetAgentbyID(agent_ID)
                    this_agent.Extend(-1)
                    
                    # Extend to the basic module size
                    for init_actn in basic_mod_stps:
                        this_agent.Extend(init_actn)
                
                    # if this year is not the initial, we need to perform additional tasks
                    if year != 0:                        
                        # Add actions selected in previous years
                        sum_acts = []
                        for this_yy in range(year): # visits all past years
                            if this_yy in winact_rec[agent_ID]:
                                if len(winact_rec[agent_ID][this_yy]) > 0:
                                    # add latest winning policy to current list
                                    sum_acts += winact_rec[agent_ID][this_yy]
                        print ("The recovered actions to apply to agent {} are {}".format(agent_ID, sum_acts))
                        
                        if len(sum_acts) > 0:
                            for act in sum_acts:
                                this_agent.Extend(act)        
                                 
            # APPLY THE FOLLOWING ONLY TO THE AGENTS THAT PARTICIPATE THIS YEAR
            # Temporary dict to store policies
            temp_policies = {agent_num:{} for agent_num in particip2}
            
            # Teporary dict to store performances
            temp_perfs = {agent_num:{} for agent_num in particip2}
    
            # Replace traces dicts with clean ones for the new episode
            traces_dicts = {agent_num:{} for agent_num in particip2}
           
            # Set a list of dictionaries to collect individual rewards to discrimiante
            # non-participants from early goal achievers
            # Dict keys will be steps and values the rewards
            i_rewards = {agent_num:{} for agent_num in particip2}
    
            # Inner loop
            for step in range(steps): #AS MANY STEPS AS MAX NEED
                print ("********")
                print("Continuing with step {} of episode {} of year {}".format(step, episode, year))
                print ("********")
    
                # Count the absolute number of iteration
                c_iter = step + (episode * steps)
                
                # GET INDIVIDUAL INITIAL STATES
                states_0 = my_neigh.GetJStatesN(particip2)
                
                # Check if csv recover file exists
                evaluated_before = False
                if recover_file:
                    # Determine if the current iteration has been visited
                    visited_ag_dat = []
                    particip = [] # particip 2 has nothing to do here, because these are from the step, not year
                    only_neighs = []
                    for dct in list_of_dict: # iterate trhough rows
                        # Has the current year_episode_step been visited?                    
                        if dct["Year"] == str(year) and dct["Episode"] == str(episode) and dct["Step"] == str(step):
                            # separate participants from neighbours
                            if dct['Part'] == "Participant":
                                particip.append(dct["Agent_Id"])
                            elif dct['Part'] == "Neighbour":
                                only_neighs.append(dct["Agent_Id"])
                                
                            # Only take fields of interest
                            selected_dct = {key: dct[key] for key in 
                                            dct.keys() & {'Part', 'Agent_Id', 'Action', 
                                                          'Indv_perf', 'Flag', 'study_id',
                                                          'study_project', 'study_owner'}}  
                            visited_ag_dat.append(selected_dct)
                    
                    if len(visited_ag_dat) > 0:
                        part_plus_neigh = particip + only_neighs
                        part_plus_neigh = list(dict.fromkeys(part_plus_neigh))
                        evaluated_before = True
                        if execution == poss_execution[0]: # When executing on the cloud
                            if "study_id" not in visited_ag_dat[0]:
                                print ("Check recover data file, was it made for competitive mode? This is cooperative")
                            study_id = visited_ag_dat[0]["study_id"]
                            study_project = visited_ag_dat[0]["study_project"]
                            study_owner = visited_ag_dat[0]["study_owner"]
    
                # If we have evaluated before, only recover results
                if evaluated_before:
                    print ("We have evaluated this step_episode_year before")
                    print ("Getting data from saved file")
                    
                    # Recover data. Value for non visited is an empty dict
                    actions = {agent_num:None for agent_num in particip3}
                    flags = {agent_num:None for agent_num in particip3}
                    recov_perfs = {agent_num:None for agent_num in particip3}
                    
                    # Iter over all agents because we might be including neighbours
                    for agent_ID in particip3:
                        for row_line in visited_ag_dat:
                            if row_line["Agent_Id"] == agent_ID:
                                recov_perfs[agent_ID] = float(row_line['Indv_perf'])
                                if row_line['Part'] == "Participant":
                                    actions[agent_ID] = int(row_line['Action'])
                                    flags[agent_ID] = row_line['Flag']                            
                                break
                    
                    # Now all None actions become 0s and all None flags become "static"
                    actions = {key:0 if value is None else value for key, value in actions.items()}
                    flags = {key:"Static" if value is None else value for key, value in flags.items()}
                    poss_acts = {agent_num:None for agent_num in particip3}
                    
                    #print (actions)
                    
                    # Get performance from CSV and save it in local dictionary
                    for agent_ID in particip3:
                        this_agent = my_neigh.GetAgentbyID(agent_ID)
                        
                        # Apply actions to agents
                        action = actions[agent_ID]
                        this_agent.Extend(action)
                        
                        # Get possible future actions
                        fut_acts = this_agent.Poss_act
                        poss_acts[agent_ID] = fut_acts
                        
                    # Get states (of agents with data only) after appying actions
                    states_1 = my_neigh.GetJStatesN(part_plus_neigh)
                        
                    # Save performance in the usual local dictionary
                    # NOW KEYS HAVE DOUBLE UNDERSCORE
                    for agent_ID in part_plus_neigh:
                        my_newst = states_1[agent_ID]
                        key_to_fill = str(agent_ID) + "_" + str(my_newst) #NOW TWO _
                        
                        if key_to_fill not in avoid_sim:
                            avoid_sim[key_to_fill] = recov_perfs[agent_ID]
                            
                    kill_flag = False
                        
                # If the files does not exist or the iter has not been visited
                # Generate and upload models as usual
                else:
                    ####
                    # GET ACTIONS, FLAGS, POSSIBLE FUTURE ACTIONS AND GEOMETRIES
                    ####                
                    # Actions and flags are generated for all as they might be required for neighbours
                    actions = {agent_num:None for agent_num in particip3}
                    flags = {agent_num:None for agent_num in particip3}
                    poss_acts = {agent_num:None for agent_num in particip3}
                    geoms = {agent_num:None for agent_num in particip4} # I need the geoms of neighs of neighs
                    non_part = [] # non participating agents IDs
                    
                    #for agent_ID in my_neigh.AgInNeigh:
                    for agent_ID in particip2:
                        this_agent = my_neigh.GetAgentbyID(agent_ID)
                        
                        # On the very first episode, this will be random (epsilon = 1)
                        if episode == 0 and step == 0:
                            action, flag = this_agent.GetActionMulti2(1)
                        else:
                            action, flag = this_agent.GetActionMulti2(EPSILON, qtables[agent_ID],
                                                                      st_ja_tab[agent_ID], states_0[agent_ID])
                        
                        # When the selected action is 0, override (so growers always grow)
                        if action == 0:
                            action, flag = 1, "Override0"
                        
                        # Check step participation (agent might have fullfilled in previous step)
                        if this_agent.NOccupiedPts >= spaces_needed[agent_ID] + act_sizes[agent_ID]:
                            action, flag = 0, "Static"
                            # Impossible, as year participants are selected earlier
                            if step == 0:
                                print ("ERROR: Step participants are not the same as year participants")
                                kill_flag = True
                                break
                            else:
                                # This agent participated in the year but has achieved its goal on a previous step
                                non_part.append(agent_ID)                            
                            
                        # Save action and flag on respective lists
                        actions[agent_ID] = action
                        flags[agent_ID] = flag                    
        
                        # Apply action to current state
                        print ("Agent {} selected action {}".format(agent_ID, action))
                        this_agent.Extend(action)
                        
                    # When on individual mode, do all at once
                    if mode == mode_keyw[1]:
                        for agent_ID in particip3:
                            this_agent = my_neigh.GetAgentbyID(agent_ID)
                            
                            # Get possible future actions
                            fut_acts = this_agent.Poss_act
                            poss_acts[agent_ID] = fut_acts
                            
                            # get geometries
                            my_geometry = this_agent.OutBrep
                            geoms[agent_ID] = my_geometry
                    # When on coop mode, do it in two steps
                    else:
                        # Possible actions are only needed for particip agents and inmediate neighbours
                        for agent_ID in particip3:
                            this_agent = my_neigh.GetAgentbyID(agent_ID)
                            
                            # Get possible future actions
                            fut_acts = this_agent.Poss_act
                            poss_acts[agent_ID] = fut_acts
                            
                        # But geometries are needed for all, neighs and neighs of neighs
                        for agent_ID in particip4:
                            this_agent = my_neigh.GetAgentbyID(agent_ID)
                            
                            # get geometries
                            my_geometry = this_agent.OutBrep
                            geoms[agent_ID] = my_geometry
                        
                    # We need inmediate neighs (because the q table demands neighbours)
                    states_1 = my_neigh.GetJStatesN(particip3)
    
                    ####
                    # GET PERFORMANCE FROM GEOMETRIES
                    ####
                    #if not evaluated_before:
                    particip2.sort() # the base are participating agents this year
                    non_part.sort() # then we take out those that have achieved goal on previous step
                    
                    # When all need has been meet on earlier step, end the learning process
                    if particip2 == non_part:
                        print ("Impossible because number of steps equals max need")
                        break
                    # Agents that participate in this step (as only 1 room per step, i expect particip == particip2)
                    else: 
                        particip = list(set(particip2) - set(non_part))
                        
                    # Warning sign
                    print (".......")
                    print ("Determining agents to be evaluated")
                    print (".......")                      
                    if len(particip) < 1:
                        print ("Warning, no growing dwellings detected, no models generated")
                    else:
                        print ("Number of participating agents: {}".format(len(particip)))
                        # If this is cooperative mode, add to the particip list all their neighbours
                        if mode == mode_keyw[0]:                        
                            # Get a list with lists of neighs for each participating agent
                            all_neighs = [value for key, value in every_n.items() if key in particip]
                            
                            # flatten list of lists
                            all_neighs = [item for slist in all_neighs for item in slist]
                            
                            # delete duplicates
                            all_neighs = list(dict.fromkeys(all_neighs))
                            
                            # Join the neighbours list with the participants list
                            part_plus_neigh = particip + all_neighs
                            
                            # delete duplicated
                            part_plus_neigh = list(dict.fromkeys(part_plus_neigh))
                            
                            print ("Participating agents and neighbours: {}".format(len(part_plus_neigh)))
                        else:
                            part_plus_neigh = particip
                            
                        # check if the participating agents have previously recorded a perf
                        excl_lst = [] # a list containing agent IDs with states previously evaluated             
                        for agent_ID in part_plus_neigh:                                                
                            # Get resulting joint state
                            my_newst = states_1[agent_ID]
                            
                            # Check if agent_num+joint_state key exist in the dict
                            key_to_search = agent_ID + "_" + my_newst
                            if key_to_search in avoid_sim:
                                # if so, add the agent num to the exclusion list
                                excl_lst.append(agent_ID)     
                     
                        # Take out the agents whose perf is recorded
                        if len(excl_lst) > 0:
                            ids_to_send = list(set(part_plus_neigh) - set(excl_lst))
                            # This might result in an empty list!
                            # when all participating agents have been prev evaluated
                        else:
                            ids_to_send = part_plus_neigh
                        
                        print ("Number of evaluated agents: {}".format(len(ids_to_send)))
                            
                    # Delete all the previous files in the upload and download folders
                    # REQUIRES AT LEAST ONE PRE EXISTING FILE IN THE FOLDER
                    if execution == poss_execution[0]:
                        if len(os.listdir(model_fld)) > 0:
                            clear_folder(model_fld)
                        if len(os.listdir(down_folder)) > 0:
                            clear_folder(down_folder)                     
                    
                    # Iterate only on those that are participating
                    # AND do not have a recorded perf for their agent/joint states
                    if len(ids_to_send) > 0:
                        print ("=======")
                        print ("Evaluating models")
                        for agent_ID in ids_to_send:
                                           
                            # current geometry
                            my_geom = [geoms[agent_ID]]
            
                            # Generate context (with all the neighbours of all agents)
                            # context_ = [value for key, value in geoms.items()
                            #             if key != agent_ID]
                            
                            # Generate context only with my neighbours INDIVIDUAL
                            # Because neighs are included on ids to send
                            # in coop mode their are automatically included
                            context_ = [value for key, value in geoms.items()
                                        if key in every_n[agent_ID]]                        
                            
            
                            # Get rooms from solids (EACH DWELLING IS ONE ROOM!)
                            # HERE YOU WOULD NEED TO ITERATED THROUGH ALL THE BREPS IN AN AGENT
                            my_roomname = "room" + agent_ID                
                            my_rooms = RoomSolid(my_geom, my_roomname, my_modset, [my_CSetClim], [myPType], myConditioned,
                                                  my_roofangle)
                        
                            # Solve the adjacency among rooms
                            # solved_rooms = SolveAdjacency(my_rooms, my_intconst_sset, my_radind_mod, my_adiabatic, my_airbound,
                            #                               my_overwrite, solve_now)
                        
                            # Get Apertures by ratio
                            # apert_rooms = ApertByRatio(solved_rooms, my_aper_ratio, my_subdivision, my_win_hgt, my_sill_hgt,
                            #                             my_h_sep, my_v_sep, my_oper_apert)
                            
                            apert_rooms = ApertByRatio(my_rooms, my_aper_ratio, my_subdivision, my_win_hgt, my_sill_hgt,
                                                        my_h_sep, my_v_sep, my_oper_apert)
                        
                            # Get shades
                            my_shdgeo = context_
                            my_shd_name = "Context" + agent_ID
                            my_shds = Shd(my_shdgeo, my_shd_name, context_attach, my_shade_energyconst, my_shd_transm,
                                          my_radshd_mod)
                        
                            # Add shades to model
                            for room in apert_rooms:
                                room.add_outdoor_shades((shd.duplicate() for shd in my_shds))
                        
                            # Get model
                            model_name = "My_model-" + agent_ID
                            my_model = Mdl(apert_rooms, my_faces, my_shades2, my_apertures, my_doors, model_name)
                            
                            if execution == poss_execution[0]:                            
                                # Save model to HBJSON in local path
                                my_model.to_hbjson(name = model_name, folder=model_fld)
                                
                            else: # Local execution
                                print ("Locally")
                                print ("=======")
                                # Additional settings
                                my_measures = [] #HB load measures
                                my_add_str = [] #additional strings to add IDF, only for advanced users
                                write_osm = True
                                run_osm = True
                                
                                # Transform model to OSM
                                print(my_measures)
                                my_results = ModToOSM(my_model, epwpath_str, my_simPars,
                                                      my_measures, my_add_str, 
                                                      model_fld_2, write_osm, run_osm)
                                              
                                # Get EUI (performance)
                                my_EUI = getEUI(my_results[4]) # sql only
                                this_perf = my_EUI[0] * my_EUI[3] # use intensity by floor area
                                
                                # Append to collector
                                my_newst = states_1[agent_ID]
                                key_to_fill = agent_ID + "_" + my_newst
                                avoid_sim[key_to_fill] = this_perf
                            
                        if execution == poss_execution[0]: # Only on cloud mode
                            print ("In the cloud")
                            print ("=======")
                            # Upload models from local path
                            study = upload_models(epw_cloud, ddy_cloud, pars_cloud, model_fld, new_study)
        
                            # wait until the study is finished
                            check_study_status(study=study)
                            
                            # Download the files
                            download_study_results(api_client=api_client, study=study, output_folder=down_folder)
                            
                            # When download files < uploaded files, send again (up to three times)
                            # AND SAVE THE NEW CODE IN THE RECOVER CSV SO WHEN RECOVER WE RUN AS USUAL
                            for i in range(3):
                                if len(os.listdir(down_folder)) != len(os.listdir(model_fld)):
                                    clear_folder(down_folder) # Just in case delete all
                                    study = upload_models(epw_cloud, ddy_cloud, pars_cloud, model_fld, new_study)
                                    check_study_status(study=study)
                                    download_study_results(api_client=api_client, study=study, output_folder=down_folder)
                                    #rerun_ids["study_id"] = study.id
                                else:
                                    break                  
            
                            # If after three attempts, still not working, send warning, stop process
                            if len(os.listdir(down_folder)) != len(os.listdir(model_fld)):
                                print ("LESS DOWN RESULTS THAN UP MODELS!")
                                kill_flag = True
                                break
                            else:
                                kill_flag = False
                                                    
                            # Read the files
                            perfs = read_jsons(down_folder) # By defult the data needed is total energy
                              
                            # save the new perfs in the perfs dictionary
                            for agent_ID in ids_to_send:
                                my_newst = states_1[agent_ID]
                                key_to_fill = agent_ID + "_" + my_newst
                                avoid_sim[key_to_fill] = perfs[agent_ID]
    
                #####
                # Manage performances (downloaded and persistent)
                #####
                
                # All performances, cloud and not, are now in the avoid_sim dict
                # Recover them for all the participants from there!            
                all_ocpts = {agent_num:None for agent_num in particip3}
                all_perfs = {agent_num:None for agent_num in particip3}
                nonmanies = {agent_num:None for agent_num in particip3}            
                fill_spaces = {agent_num:None for agent_num in particip3}
                
                # For cooperative mode, we need to recover the perfs and size of part
                # and Neighs, not only particip
                for agent_ID in part_plus_neigh:
                    this_agent = my_neigh.GetAgentbyID(agent_ID)
                    # Get current individual size
                    oc_pts = this_agent.NOccupiedPts
                    all_ocpts[agent_ID] = oc_pts
                    
                    # Get current joint state
                    my_newst = states_1[agent_ID]               
    
                    # Get search key to recover performance
                    key_to_search = agent_ID + "_" + my_newst
                    
                    # Get performance
                    if key_to_search in avoid_sim:
                        all_perfs[agent_ID] = avoid_sim[key_to_search]
                    else:
                        # If the perf has not been recorded there, something weird is happening
                        print ("Something else is happening with agent {}".format(agent_ID))
                        
                    # In this iter we also need to colect if there are non manies and fill spaces
                    # Reproduce the non-manifold state
                    NM_STR = this_agent.GetNullState()
    
                    # Detect non manifold state
                    if this_agent.C_state == NM_STR:
                        nonmani = True
                    else:
                        nonmani = False
                    nonmanies[agent_ID] = nonmani
    
                    # Filled the need (space)
                    if int(spaces_needed[agent_ID]) + act_sizes[agent_ID] <= int(all_ocpts[agent_ID]):
                        filled_space = True
                    else:
                        filled_space = False
                    fill_spaces[agent_ID] = filled_space
    
                    # Still within budget
                    ext_cost = this_agent.WallAreaExtCost + this_agent.RoofAreaExtCost
                    # agent_balance = budget - ext_cost # BUDGET DOES NOT EXIST IN THIS CSV
                    # balances[agent_num] = agent_balance # BALANCES IS NOT USED IN THIS CSV
    
                ####
                # GET REWARDS
                ####               
                # Record tolerance lines for graphs
                toler_lines = {agent_num:None for agent_num in particip3}
                
                # Save local performances and sizes for coop mode
                local_perf = {}
                local_ptocc = {}
                
                # Get variables for global reward or get individual rewards
                for agent_ID in particip:
                    this_agent = my_neigh.GetAgentbyID(agent_ID)                
    
                    # When on competitive mode assign individual reward
                    if mode != mode_keyw[0]:
                        # Check if we have broken performance record (within tolerance)
                        if all_ocpts[agent_ID] not in my_rdicts[agent_ID]: # The first time we visit this
                            my_rdicts[agent_ID][all_ocpts[agent_ID]] = all_perfs[agent_ID]
                            agent_record = all_perfs[agent_ID]
                        else:
                            # Minimise
                            # if all_perfs[agent_ID] < my_rdicts[agent_ID][all_ocpts[agent_ID]]:
                            #     my_rdicts[agent_ID][all_ocpts[agent_ID]] = all_perfs[agent_ID]
                            #     agent_record = all_perfs[agent_ID]
                            # else:
                            #     agent_record = my_rdicts[agent_ID][all_ocpts[agent_ID]]
                            
                            # Maximise
                            if all_perfs[agent_ID] > my_rdicts[agent_ID][all_ocpts[agent_ID]]:
                                my_rdicts[agent_ID][all_ocpts[agent_ID]] = all_perfs[agent_ID]
                                agent_record = all_perfs[agent_ID]
                            else:
                                agent_record = my_rdicts[agent_ID][all_ocpts[agent_ID]]
    
                        # Minimise
                        # upper_limit = agent_record + (agent_record * tolerance)
                        # toler_lines[agent_ID] = upper_limit
                        
                        # Maximise
                        upper_limit = agent_record - (agent_record * tolerance)
                        toler_lines[agent_ID] = upper_limit
                        
                        # Minimise
                        # if all_perfs[agent_ID] <= upper_limit and not nonmanies[agent_ID]:
                        #     record_broken = True  # Reeplace record on dictionary on the next loop
                        # else:
                        #     record_broken = False
                            
                        # Maximise
                        if all_perfs[agent_ID] >= upper_limit and not nonmanies[agent_ID]:
                            record_broken = True  # Reeplace record on dictionary on the next loop
                        else:
                            record_broken = False
                            
                        # Finally, the conditions
                        if record_broken and fill_spaces[agent_ID]:  # Goal achieved
                            status = GOAL_REWARD                   
    
                            # Tell the programme that on this episode, this agent won
                            # when the win is repeated in several steps, it is replaced
                            # so there is always only one win by episode
                            #count_wins[agent_num][episode] = "win"
                            count_wins[agent_ID][episode] = str(all_ocpts[agent_ID]) + "_" + str(agent_record) 
                            
                            
                        elif not record_broken and fill_spaces[agent_ID]:  # This limits growth to strictly necesary (faster?)
                            status = -GOAL_REWARD # Avoids using unnecesary steps
                            # if this is a further episode, make sure you replace
                            # a possible "win"
                            count_wins[agent_ID][episode] = "lose"
                            #print ("not record_broken and filled_space")
                            
                        ## elif agent_balance < 0 or nonmani:  # Deadly status - Fail
                        ## status = "F" # AGENT BALANCE DOES NOT EXIST IN THIS CSV
                        elif nonmanies[agent_ID]:  # Deadly status - Fail
                            status = -GOAL_REWARD
                            # if this is a further episode, make sure you replace
                            # a possible "win"
                            count_wins[agent_ID][episode] = "NONMANI"
                            #print ("nonmani")
                            
                        else:
                            # If it is the last time step and we have not found a solution
                            if step + 1 == steps:
                                status = -GOAL_REWARD
                                # if this is a further episode, make sure you replace
                                # a possible "win"
                                count_wins[agent_ID][episode] = "lose"
                                #print ("last_step")
                            # If we still have time
                            else:
                                status = -TIME_PENALTY
                        
                        # Append individual reward to collector
                        i_rewards[agent_ID][step] = status
                        
                        # Save actions in case this is a high performing episode
                        if step == 0:
                            # on step 0 replace whatever existed before
                            #winact_rec[agent_num][year] = [actions[agent_num]]
                            part_winact[agent_ID][episode] = [actions[agent_ID]]
                        else:
                            # on further steps, add current action to list
                            #winact_rec[agent_num][year].append(actions[agent_num])
                            part_winact[agent_ID][episode].append(actions[agent_ID])
                    
                    # When on cooperative mode, assign local reward
                    else:                    
                        # Get their neighbour IDs (this is a list)
                        myneighs_ID = every_n[agent_ID]
                        local_nid = copy.deepcopy(myneighs_ID) # create deep copy to protect attribute
                        local_nid.sort()
                        
                        # Add own id to neighs
                        local_nid.append(agent_ID)
                        
                        # Make sure there are no repeated IDs
                        local_nid = list(dict.fromkeys(local_nid))
                        
                        # subset their perfs, sizes and *costs*
                        neigh_perfs = []
                        neigh_sizes = []
                        neigh_nonm = []
                        neigh_fspaces = []
                        #neigh_costs = []
                        
                        # dictionaries include neighs IDS
                        for agent_IDk in local_nid:
                            if all_perfs[agent_IDk] is not None:
                                neigh_perfs.append(all_perfs[agent_IDk])
                            if all_ocpts[agent_IDk] is not None:
                                neigh_sizes.append(all_ocpts[agent_IDk])
                            if nonmanies[agent_IDk] is not None:
                                neigh_nonm.append(nonmanies[agent_IDk])
                            if fill_spaces[agent_IDk] is not None:
                                neigh_fspaces.append(fill_spaces[agent_IDk])
                                
                        # Get local objectives
                        tot_oc_pts = sum(neigh_sizes) # Total space occupied
                        tot_perf = sum(neigh_perfs) # Sum individual perfs
                        nonmani = any(neigh_nonm) # Check if any geometry nonmanifold
                        all_filled = all(neigh_fspaces) # Check that all meet space demand
                        
                        # Save local perfs and sizes
                        local_perf[agent_ID] = tot_perf
                        local_ptocc[agent_ID] = tot_oc_pts
                        
                        # The stopping function needs the common perf and size of each 
                        # coop agent to compare with records
                        
                        # Check if we have broken performance record (within tolerance)
                        if tot_oc_pts not in my_rdicts[agent_ID]: # The first time we visit this
                            my_rdicts[agent_ID][tot_oc_pts] = tot_perf
                            local_record = tot_perf
                        else:
                            # Minimise
                            # if tot_perf < my_rdicts[agent_ID][tot_oc_pts]:
                            #     my_rdicts[agent_ID][tot_oc_pts] = tot_perf
                            #     local_record = tot_perf
                            # else:
                            #     local_record = my_rdicts[agent_ID][tot_oc_pts]
                            
                            # Maximise
                            if tot_perf > my_rdicts[agent_ID][tot_oc_pts]:
                                my_rdicts[agent_ID][tot_oc_pts] = tot_perf
                                local_record = tot_perf
                            else:
                                local_record = my_rdicts[agent_ID][tot_oc_pts]
                        
                        # Minimise
                        # upper_limit = local_record + (local_record * tolerance)
                        # toler_lines[agent_ID] = upper_limit
                        
                        # Maximise
                        upper_limit = local_record - (local_record * tolerance)
                        toler_lines[agent_ID] = upper_limit
                         
                        # Minimise
                        # if tot_perf <= upper_limit and not nonmani:
                        #     record_broken = True
                        # else:
                        #     record_broken = False
                            
                        # Maximise
                        if tot_perf >= upper_limit and not nonmani:
                            record_broken = True
                        else:
                            record_broken = False
                            
                        # Finally, the conditions
                        if record_broken and all_filled:  # Goal achieved
                            status = GOAL_REWARD
                            # Tell the programme that on this episode, this agent won
                            # when the win is repeated in several steps, it is replaced
                            # so there is always only one win by episode
                            #count_wins[agent_num][episode] = "win"
                            count_wins[agent_ID][episode] = str(tot_oc_pts) + "_" + str(local_record) 
                            
                        elif not record_broken and all_filled:  # This limits growth to strictly necesary (faster?)
                            status = -GOAL_REWARD # Avoids using unnecesary steps
                            # if this is a further episode, make sure you replace
                            # a possible "win"
                            count_wins[agent_ID][episode] = "lose"
                            #print ("not record_broken and filled_space")
                            
                        ## elif agent_balance < 0 or nonmani:  # Deadly status - Fail
                        ## status = "F" # AGENT BALANCE DOES NOT EXIST IN THIS CSV
                        elif nonmani:  # Deadly status - Fail
                            status = -GOAL_REWARD
                            # if this is a further episode, make sure you replace
                            # a possible "win"
                            count_wins[agent_ID][episode] = "NONMANI"
                            #print ("nonmani")
                            
                        else:
                            # If it is the last time step and we have not found a solution
                            if step + 1 == steps:                            
                                status = -GOAL_REWARD
                                # if this is a further episode, make sure you replace
                                # a possible "win"
                                count_wins[agent_ID][episode] = "lose"
                                #print("last_step. Record {}. All_filled {}. Non_mani {}".format(record_broken, all_filled, nonmani))
                            # If we still have time
                            else:
                                status = -TIME_PENALTY
    
                            
                        # Save local reward on individual list to discriminate those
                        # that never participated in the episode from those who did on the 
                        # next step of the episode
                        i_rewards[agent_ID][step] = status
                        
                        # Save actions to reintroduce if a high performing episode
                        if step == 0:
                            # on step 0 replace whatever existed before
                            #winact_rec[agent_num][year] = [actions[agent_num]]
                            part_winact[agent_ID][episode] = [actions[agent_ID]]
                        else:
                            # on further steps, add current action to list
                            #winact_rec[agent_num][year].append(actions[agent_num])
                            part_winact[agent_ID][episode].append(actions[agent_ID])
                
                ####
                # UPDATE Q TABLE AND OTHER RECORDS
                ####            
                # CHECK IF NEW STATE AND POSSIBLE ACTIONS EXIST IN CURRENT Q-TABLE. IF NOT, ADD
                qtables, st_ja_tab = my_neigh.CheckQtableN(qtables, st_ja_tab, states_1, poss_acts, particip)
    
                # ASSIGN VALUES TO Q-TABLES AND OTHER DATA RECORDS
                for agent_ID in particip:
                    # Get agent
                    this_agent = my_neigh.GetAgentbyID(agent_ID)
                    
                    # My initial state
                    state0 = states_0[agent_ID]
    
                    # my selected action
                    action = actions[agent_ID]
    
                    # My neighbour's actions (tuple)
                    jactions = []
                    neighbours_ids = every_n[agent_ID]
                    neighbours_ids.sort()
                    
                    for id_n in neighbours_ids:
                        ja = actions[id_n]
                        ja = 0 if ja is None else ja
                        jactions.append(ja)
                    jactions = tuple(jactions)
    
                    # My final state
                    state1 = states_1[agent_ID]
    
                    # Get the current q-value
                    current_q = qtables[agent_ID][state0][jactions][action]                    
    
                    # Get reward
                    reward = i_rewards[agent_ID][step]
                    
                    # Kill action 0
                    qtables[agent_ID][state0][jactions][0] = -GOAL_REWARD * 4
                    
                    # Assign values to q table and so
                    # First when fallen on losing state
                    if reward == -GOAL_REWARD:
                        new_qvalue = reward
                        future_q = None
                        qtables[agent_ID][state0][jactions][action] = new_qvalue
                        
                    # Otherwise
                    else:
                        # When still searching
                        if -GOAL_REWARD < reward < GOAL_REWARD:                        
                            # Get future q (WHEN MAX_REWARD OR -MAX_REWARD, ALL ARE 0S!)
                            future_q = this_agent.GetMaxFutureQ(qtables[agent_ID], st_ja_tab[agent_ID],
                                                                              state1)
    
                            # Calculate new q value
                            new_qvalue = (1 - LEARNING_RATE) * current_q + LEARNING_RATE * (
                                    reward + DISCOUNT * future_q)
    
                            # Replace q value on qtable
                            qtables[agent_ID][state0][jactions][action] = new_qvalue
                            
                            # Save on traces dictionary
                            # Turn tuple to string (joint actions)
                            j_act_str = []
                            for act in jactions:
                                stt = str(act)
                                j_act_str.append(stt)
                            jactstr = '_'.join(j_act_str)
    
                            # Get the identifier for the traces dictionary
                            traces_id = state0 + ':' + jactstr + ':' + str(action)
    
                            # if the identifier does not exist on elegibility dict, create
                            if traces_id not in traces_dicts[agent_ID]:
                                traces_dicts[agent_ID][traces_id] = 0.0
    
                            # If it does exist, add a 1
                            for key, old_value in traces_dicts[agent_ID].items():
                                trace_state, trace_jact, trace_act = key.split(":")
                                trace_jact = tuple(map(int, trace_jact.split('_')))
    
                                # trace_act must go from str to int
                                trace_act = int(trace_act)
    
                                # Update the q-value and traces dictionary for currently visited state:jaction:action
                                if state0 == trace_state and jactions == trace_jact and action == trace_act:
                                    # Update traces dict
                                    traces_dicts[agent_ID][key] = old_value + 1
    
                        # When we have found a solution
                        elif reward >= GOAL_REWARD:
                            # Current q-value is reward
                            new_qvalue = reward
                            qtables[agent_ID][state0][jactions][action] = new_qvalue
    
                            # Because function give 0 on max or min reward, just assign 0
                            future_q = 0
    
                            # Get the value of the new-qs formula that derives from present values
                            from_current_state = (reward + (DISCOUNT * future_q)) - current_q
    
                            # Update previous q_values
                            for key, old_value in traces_dicts[agent_ID].items():
                                trace_state, trace_jact, trace_act = key.split(":")
                                trace_jact = tuple(map(int, trace_jact.split('_')))
                                trace_act = int(trace_act)
    
                                old_qvalues = qtables[agent_ID][trace_state][trace_jact][trace_act]
                                new_qvalues = old_qvalues + LEARNING_RATE * traces_dicts[agent_ID][
                                    key] * from_current_state
                                qtables[agent_ID][trace_state][trace_jact][trace_act] = new_qvalues
                            
                    # Update state-joint action count table
                    st_ja_tab[agent_ID][state0][jactions] += 1                        
                        
                    # Save all relevant data on the correspondent dictionary
                    # DATA MUST BE SAVED FOR ALL AGENTS THAT WERE EVALUATED IN THIS STEP
                    # this includes particip and neighs in coop
                    # But there non_particip include only some data
                    my_dictone = {}
                    
                    my_dictone["Part"] = "Participant" # If participant or neighbour
    
                    my_dictone["Agent_Id"] = agent_ID
                    my_dictone["Countdown"] = c_iter
                    my_dictone["Episode"] = episode
                    my_dictone["Step"] = step
                    my_dictone["State_0"] = state0
                    my_dictone["Action"] = action
                    my_dictone["Joint_act"] = jactions
                    my_dictone["Epsilon"] = EPSILON
                    my_dictone["Flag"] = flags[agent_ID]
                    my_dictone["Old_q"] = current_q
                    my_dictone["State_1"] = state1
                    my_dictone["Reward"] = reward
                    my_dictone["Max_future_q"] = future_q
                    my_dictone["New_q"] = new_qvalue
                    key_to_search = agent_ID + "_" + state1
                    my_dictone["Indv_perf"] = avoid_sim[key_to_search]
                    my_dictone["Indv_mod_occupied"] = all_ocpts[agent_ID]
                    my_dictone["Tolerance_line"] = toler_lines[agent_ID]
                    if mode != mode_keyw[0]: # on indv mode 
                        my_dictone["Eval_perf"] = avoid_sim[key_to_search]
                        my_dictone["Eval_mod_occupied"] = all_ocpts[agent_ID]
                        my_dictone["Record_Perf"] = my_rdicts[agent_ID][all_ocpts[agent_ID]]
                    else: # on coop mode
                        my_dictone["Eval_perf"] = local_perf[agent_ID] # takes in account growing and non-growing
                        my_dictone["Eval_mod_occupied"] = local_ptocc[agent_ID]
                        my_dictone["Record_Perf"] = my_rdicts[agent_ID][local_ptocc[agent_ID]]
                    # my_dictone["Remaining_Budget"] = balances[agent_num] # BALANCES IS NOT USED IN THIS CSV
                    my_dictone["LR"] = LEARNING_RATE
                    my_dictone["Mode"] = mode
                    my_dictone["Location"] = my_location
                    my_dictone["Year"] = year
                    my_dictone["Need"] = spaces_needed[agent_ID]
                    if execution == poss_execution[0]: # Only on cloud mode
                        if evaluated_before or len(ids_to_send) == 0:
                            my_dictone["study_id"] = study_id
                            my_dictone["study_project"] = study_project
                            my_dictone["study_owner"] = study_owner
                        else:
                            my_dictone["study_owner"] = study.owner
                            my_dictone["study_project"] = study.project
                            my_dictone["study_id"] = study.id
                        
                    #relevant_datas.append(my_dictone)
                    
                    # Write current dict as a new line in the out csv file
                    my_filepath = csv_out + "\\" + "rel_dat_" + current_date + ".csv"
                    newfile = not os.path.isfile(my_filepath)
                    
                    with open(my_filepath, 'a', newline='') as f:  # You will need 'wb' mode in Python 2.x
                        w = csv.DictWriter(f, my_dictone.keys())
                        if newfile:
                            w.writeheader()
                        w.writerow(my_dictone)                
    
                    # Save temporary dict to get wining policy
                    temp_policies[agent_ID][step] = action
                    
                    # Save temporary dict to get wining performance
                    temp_perfs[agent_ID][all_ocpts[agent_ID]] = avoid_sim[key_to_search]
                    
                # NOW ADD THE DATA OF EVALAUATED NEIGBOURS to csv file            
                if mode == mode_keyw[0]: # Neighbours only exist if this was a coop scenario
                    if not evaluated_before:
                        only_neighs = [item for item in all_neighs if item not in particip]
                    else:
                        only_neighs = [item for item in only_neighs if item not in particip]
                    for ng in only_neighs:
                        my_dictone = {}
                        
                        my_dictone["Part"] = "Neighbour" # participant or neighbour
                        
                        my_dictone["Agent_Id"] = ng
                        my_dictone["Countdown"] = c_iter
                        my_dictone["Episode"] = episode
                        my_dictone["Step"] = step
                        my_dictone["State_0"] = None
                        my_dictone["Action"] = None
                        my_dictone["Joint_act"] = None
                        my_dictone["Epsilon"] = EPSILON
                        my_dictone["Flag"] = None
                        my_dictone["Old_q"] = None
                        my_dictone["State_1"] = states_1[ng]
                        my_dictone["Reward"] = None
                        my_dictone["Max_future_q"] = None
                        my_dictone["New_q"] = None
                        key_to_search = ng + "_" + states_1[ng]
                        my_dictone["Indv_perf"] = avoid_sim[key_to_search]
                        my_dictone["Indv_mod_occupied"] = all_ocpts[ng]
                        my_dictone["Tolerance_line"] = None
                        
                        my_dictone["Eval_perf"] = None # takes in account growing and non-growing
                        my_dictone["Eval_mod_occupied"] = None
                        my_dictone["Record_Perf"] = None
                        
                        my_dictone["LR"] = LEARNING_RATE
                        my_dictone["Mode"] = mode
                        my_dictone["Location"] = my_location
                        my_dictone["Year"] = year
                        my_dictone["Need"] = None
                        
                        if execution == poss_execution[0]: # Only on cloud mode
                            if evaluated_before or len(ids_to_send) == 0:
                                my_dictone["study_id"] = study_id
                                my_dictone["study_project"] = study_project
                                my_dictone["study_owner"] = study_owner
                            else:
                                my_dictone["study_owner"] = study.owner
                                my_dictone["study_project"] = study.project
                                my_dictone["study_id"] = study.id
                        
                        # Write current dict as a new line in the out csv file
                        my_filepath = csv_out + "\\" + "rel_dat_" + current_date + ".csv"
                        newfile = not os.path.isfile(my_filepath)
                        
                        with open(my_filepath, 'a', newline='') as f:  # You will need 'wb' mode in Python 2.x
                            w = csv.DictWriter(f, my_dictone.keys())
                            if newfile:
                                w.writeheader()
                            w.writerow(my_dictone)                    
                        
                ####
                # FINISH THE EPISODE
                ####        
                # END ALL PROCESS IF MORE UP MODELS THAN DOWN RESULTS
                if kill_flag:
                    print ("Kill_flag")
                    break
                
                # Decay epsilon and learning rate
                EPSILON *= EPS_DECAY
                LEARNING_RATE *= LR_DECAY
                
                # Get the individual rewards for this step for all agents
                # NOW IREWARDS IS A DICT OF DICTS
                values = []                
                for dict_ in i_rewards.values():
                  for key in dict_.keys():
                    if key == step:
                      values.append(dict_[key])
                print ("List of rewards for Year {}, Episode {} and Step {} out of {} Steps: {} ".format(year, episode, step, steps, values))
                
                # When all are Max reward or min reward, finish the episode
                abs_vals = [abs(int(val)) for val in values]
                if len(set(abs_vals)) == 1 and int(set(abs_vals).pop()) == GOAL_REWARD:
                    print ("________________")                    
                    print ("Finished episode {} of year {}".format(episode, year))
                    print ("________________")
                    break
    
                
            ####
            # BREAK THE LEARNING PROCESS
            ####
            # END ALL PROCESS IF MORE UP MODELS THAN DOWN RESULTS
            if kill_flag:
                print ("Kill flag 2")
                break
                
            # Check if we have achieve the success rate
            if episode > n_count_epis:
                # get the number of episode of the latest episodes
                # add 1 because of 0s
                last_episodes = [i for i in range(episode - (n_count_epis + 1), episode + 1)]
    
                counts = {} # this is the prop of won episodes per agent
                #for agent_ID in particip:
                for recent_epi in last_episodes:             
                    count = 0 # Counts how many agents have achieved the goal per episode
                    any_nonmani = []
                    for agent_ID in particip2: # Because we are outside of the step sub selection
                        if recent_epi in count_wins[agent_ID]:
                            # When winning episode, the record_perf + occ_pts at that time is saved
                            # ADD A KEYWORD WHEN THE RESULT IS A NON-MANIFOLD STATE
                            # SO HERE COMES AS AN EXCEPTION
                            if count_wins[agent_ID][recent_epi] != "lose" and\
                            count_wins[agent_ID][recent_epi] != -TIME_PENALTY:
                                if count_wins[agent_ID][recent_epi] == "NONMANI":
                                    # Tell the list that this agent was non manifold at the end of the episode
                                    any_nonmani.append(True)
                                else:
                                    # Tell the list that this was a manifold state
                                    any_nonmani.append(False)                           
                                
                                    # Separate occupied points from record
                                    occpts_perf = count_wins[agent_ID][recent_epi].split("_")
                                    occptsr = int(occpts_perf[0])
                                    perfrec = float(occpts_perf[1])
                                    
                                    # Minimise
                                    #recorded_record = my_rdicts[agent_ID][occptsr]
                                    #upper_limit = recorded_record + (recorded_record * tolerance)
                                    
                                    # Maximise
                                    recorded_record = my_rdicts[agent_ID][occptsr]
                                    upper_limit = recorded_record - (recorded_record * tolerance)
                                    
                                    # Minimise
                                    #if perfrec <= float(upper_limit):
                                        #count += 1
                                    
                                    # Maximise
                                    if perfrec >= float(upper_limit):
                                        count += 1
                                        
                    # When non manifold state is found, the score for this episode is set to 0
                    # In that way, its results will never be chosen
                    if any(any_nonmani):
                        counts[recent_epi] = 0
                    else:
                        #prop_win = count / len(last_episodes) # wins out of the number of latest episodes
                        prop_win = count / len(particip2) # success agents out of the total participating this year
                        counts[recent_epi] = prop_win
                
                # Get the episode when the highest success was achieved!
                episode_id = max(counts, key=counts.get)
                
                # Replace the yearly actions record with the best performing episode            
                if counts[episode_id] > 0:
                    # Save the identity of the latest episode for winning policy
                    winyear = {}
                    winyear["episode"] = episode_id
                    winyear["proportion"] = counts[episode_id]
                    #for agent_ID in particip:
                    for agent_ID in particip2:
                        winact_rec[agent_ID][year] = part_winact[agent_ID][episode_id]
                    
                        
                # If we are on the last episode and no winning selection, something went wrong
                if episode + 1 == episodes and counts[episode_id] <= 0:
                    print("Warning! last episode of the year and no winning epsiode selected/actions recorded")
                    kill_flag = True
                
                # Get an average of success for the last episodes
                tot_prop = sum(counts.values()) / len(counts)
                
                # Set auto-stop conditions
                # If so, time to end the learning
                autostop = False
                # Check if the success rate has been stable for the amount of evaluated years
                unique_success = list(set(list(counts.values()))) # get unique values
                if len(unique_success) == 1 and unique_success[0] > 0: # One repeated value more than 0
                    print ("AUTOSTOP because there is a unique success rate")
                    autostop = True
                # Check if the success average is equal or higher than expected
                if tot_prop >= stop_prop:
                    autostop = True
                    print ("The Max agents win proportion in the evaluated episodes was {} at episode {}".format(counts[episode_id], episode_id))
    
                # stop the process
                if autostop:         
                    break    
    
            # Temporal auto-stop to skip year 0 learning
            #if year == 0:
                #autostop = True
                #break
            
        ####
        # END YEAR ITERATION
        ####    
        # Get this learning process timing
        inner_end = time.time()
        inner_elapsed = inner_end - inner_start
        inner_date = datetime.now().strftime("%d%m%Y_%H%M")    
        
        # Only write a txt file of each succesful learning process when there has been need to expand
        lines_to_write = []  # ADD GLOBAL PERFORMANCE AND TOLERANCE
        lines_to_write.append(inner_date)
        lines_to_write.append("Process of type " + str(mode) + " finished after " +
                              str(inner_elapsed) + " seconds and " + str(episode) + " episodes")
    
        if autostop:
            lines_to_write.append("Auto-stop triggered. Inputs: " + str(n_count_epis) + ", " + str(stop_prop))
        else:
            lines_to_write.append("Ran until max episodes")
    
        for agent_ID in winact_rec.keys():
            lines_to_write.append("For agent ID " + agent_ID + " the wining policy is:")
            for k, v in winact_rec[agent_ID].items(): # therefore v is a list
                lines_to_write.append("Year: " + str(k) + ", actions: " + str(v))
    
        # Write on txt file and print result
        my_writepath = csv_out + "\\" + "summary_" + current_date + ".txt"
        with open(my_writepath, 'a') as f:
            for wline in lines_to_write:
                #print(wline)
                f.write(wline)
                f.write('\n')
          
        ####
        # Write winning actions in csv
        ####
        my_winningpath = csv_out + "\\" + "winning_policy" + current_date + ".csv"
        mew_file = not os.path.isfile(my_winningpath)
        
        # reconvert collector of winning actions to list of dicts
        dict_list = []
        for key, value in winact_rec.items():
            for key2, value2 in value.items():
                if key2 == year: # only write current year
                    as_str = '_'.join(str(i) for i in value2) # actions separated by _
                    new_dict = {"agent_id":key, "year":key2, "actions":as_str,
                                "epsisode": winyear["episode"],
                                "proportion": winyear["proportion"],
                                "mode": mode, "location": my_location}
                    dict_list.append(new_dict)
    
        # Write csv
        with open(my_winningpath, 'a', newline='') as out_file:
            fc = csv.DictWriter(out_file, dict_list[0].keys())
            if mew_file:
                fc.writeheader()
            fc.writerows(dict_list)
                        
                    
        # END ALL PROCESS IF MORE UP MODELS THAN DOWN RESULTS
        if kill_flag:
            print ("KILL FLAG 3")
            break
        
        # PRINT END OF YEAR
        print ("++++++++++")
        print("Finished year {}".format(year))
        print ("++++++++++")
        
    print ("##########")
    print ("Finished Simulation")
    
    # Outer time
    outer_end = time.time()
    elapsed = outer_end - outer_start
    print("time elapsed {}".format(elapsed))
    print ("##########")

######
# TEMP IMPLEMENTATION TO RESCUE DATA FROM OLD RESULTS
# EXPORT A CSV WITH THE LOCATION OF THE LOTS AND NUMBER OF EXTENSIONS
#####
# for agent_ID in my_neigh.AgInNeigh:
#     this_agent = my_neigh.GetAgentbyID(agent_ID)
#     my_coords = this_agent.VertixLots
    
#     myxs = []
#     myys = []
#     for vertxx in my_coords:
#         myxs.append(vertxx.X)
#         myys.append(vertxx.Y)
    
#     maxx = max(myxs)
#     minx = min(myxs)
    
#     maxy = max(myys)
#     miny = min(myys)
    
#     if mainsideXorY: # alter it considering open spaces    
#         minx -= this_agent.Module/2
#         maxx += this_agent.Module
#     else:
#         miny -= this_agent.Module/2
#         maxy += this_agent.Module
        
#     # To get year and if we built I need to recover the original csv export
#     years = []
#     for dctt in list_of_dict:
#         years.append(int(dctt["Year"]))
#     years = list(dict.fromkeys(years))
    
#     for year in years:
#         this_line = {} 
#         for dctt in list_of_dict:
#             if int(dctt["Year"]) == year and dctt["Part"] == "Participant" and dctt["Agent_Id"] == agent_ID:          
#                 this_line["Origin"] = str(minx) + "_" + str(miny)
#                 this_line["Width"] = str(maxx - minx)
#                 this_line["Heigth"] = str(maxy - miny)
#                 this_line["Agent_Id"] = agent_ID
#                 this_line["Socec_Id"] = my_neigh.AgInNeigh.index(agent_ID)
#                 this_line["Year"] = year
#                 this_line["Build"] = int(dctt["Need"])
#                 this_line["Mode"] = mode
#                 this_line["Location"] = my_location
#         # check if after this the dictionary is still empty
#         if not this_line:
#             this_line["Origin"] = str(minx) + "_" + str(miny)
#             this_line["Width"] = str(maxx - minx)
#             this_line["Heigth"] = str(maxy - miny)
#             this_line["Agent_Id"] = agent_ID
#             this_line["Socec_Id"] = my_neigh.AgInNeigh.index(agent_ID)
#             this_line["Year"] = year
#             this_line["Build"] = 0
#             this_line["Mode"] = mode
#             this_line["Location"] = my_location
    
#         # Save the year construction activity in a csv
#         my_coord_csv = csv_out + "\\" + "coords.csv"
#         tew_file = not os.path.isfile(my_coord_csv)
#         with open(my_coord_csv, 'a', newline='') as out_file:
#             fc = csv.DictWriter(out_file, this_line.keys())
#             if tew_file:
#                 fc.writeheader()
#             fc.writerow(this_line)
            

#####
# EXPORT A CSV WITH THE LOCATION OF THE ROOFS
#####

def RoofInfoAgent(agent_as_lot, ag_id, yyyy):            
    # Get face indices of the roofs in the brep
    roof_faceids = agent_as_lot.ClassifyFaces(agent_as_lot.OutBrep)[1]
    
    this_agents_data = []
    
    # For each roof surface, get origin coordinates, hewight width and elevation
    for idx in roof_faceids:
        srf_brp = agent_as_lot.OutBrep.Faces[idx].ToBrep()
        srf_vtx = srf_brp.Vertices
        xs = []
        ys = []
        zs = []
        
        for vtx in srf_vtx:
            xs.append(vtx.Location[0])
            ys.append(vtx.Location[1])
            zs.append(vtx.Location[2])
        
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        z = set(zs).pop() # get unique value
        
        line_to_write = {}
        line_to_write["agent_id"] = ag_id
        line_to_write["socec_id"] = my_neigh.AgInNeigh.index(agent_ID)
        line_to_write["year"] = yyyy
        line_to_write["roof_id"] = idx
        line_to_write["origin"] = str(minx) + "_" + str(miny)
        line_to_write["height"] = str(maxy - miny)
        line_to_write["width"] = str(maxx - minx)
        line_to_write["elevation"] = z
        line_to_write["Mode"] = mode
        line_to_write["Location"] = my_location
        
        this_agents_data.append(line_to_write)
    
    return this_agents_data      
            
####
# WRITE RESULTING NEIGHBOURHOOD PERFORMANCE
####
if "dict_list" not in globals(): # if this file exists, learning process was active
    dict_list = list_of_years
else:
    print ("No file with winning policies found")

# When the learning process is disabled, recover from recover_years.csv
# dict_list = list_of_years if "dict_list" not in globals() else dict_list

# Create all neighs if not already in memory
all_neighs = every_n if "every_n" in locals() else my_neigh.EveryNeigh

# Create avoid_sim dict if sim not in variables
avoid_sim = {} if "avoid_sim" not in locals() else avoid_sim

# Get the participating years from the dictionary
years = []
for csv_line in dict_list:
    years.append(int(csv_line["year"]))
years = list(dict.fromkeys(years))
    
# Apply basic common actions to all agents
geoms = {}
sizes = {}
for agent_ID in my_neigh.AgInNeigh:
    # restart agent to 1 cube
    this_agent = my_neigh.GetAgentbyID(agent_ID)
    this_agent.Extend(-1)
    
    # Extend to the basic module size
    for init_actn in basic_mod_stps:
        this_agent.Extend(init_actn)
        
    # save initial geometries and states
    geoms[agent_ID] = this_agent.OutBrep
    sizes[agent_ID] = this_agent.NOccupiedPts
        
    # record the very first state in the roofs csv
    this_agent_dicts = RoofInfoAgent(this_agent, agent_ID, -1)
    
    my_heights_csv = csv_out + "\\" + "roof_h.csv"
    sew_file = not os.path.isfile(my_heights_csv)
    with open(my_heights_csv, 'a', newline='') as out_file:
        fc = csv.DictWriter(out_file, this_agent_dicts[0].keys())
        if sew_file:
            fc.writeheader()
        fc.writerows(this_agent_dicts)

####
# Evaluate the very first performance of the dwellings
####

# get joint states for all agents
states = my_neigh.GetJStatesN(my_neigh.AgInNeigh)

# Identify those that do not register a state yet
excepmt_ids = []
for agent_ID in my_neigh.AgInNeigh:
    key_to_search = agent_ID + "_" + states[agent_ID]
    if key_to_search in avoid_sim:
        excepmt_ids.append(agent_ID)

sim_ids = list(set(my_neigh.AgInNeigh) - set(excepmt_ids))
    
# Get ready receiving formder for cloud execution
if execution == poss_execution[0]:
    if len(os.listdir(model_fld)) > 0:
        clear_folder(model_fld)
    if len(os.listdir(down_folder)) > 0:
        clear_folder(down_folder)

# Get the performance of each agent    
for agent_ID in sim_ids:
    # current geometry
    my_geom = [geoms[agent_ID]]
    
    # Generate context only with my neighbours
    context_ = [value for key, value in geoms.items()
                if key in all_neighs[agent_ID]]
    
    # Get rooms from solids (EACH DWELLING IS ONE ROOM!)
    my_roomname = "room" + agent_ID                
    my_rooms = RoomSolid(my_geom, my_roomname, my_modset, [my_CSetClim], [myPType], myConditioned,
                          my_roofangle)
    
    apert_rooms = ApertByRatio(my_rooms, my_aper_ratio, my_subdivision, my_win_hgt, my_sill_hgt,
                                my_h_sep, my_v_sep, my_oper_apert)

    # Get shades
    my_shdgeo = context_
    my_shd_name = "Context" + agent_ID
    my_shds = Shd(my_shdgeo, my_shd_name, context_attach, my_shade_energyconst, my_shd_transm,
                  my_radshd_mod)

    # Add shades to model
    for room in apert_rooms:
        room.add_outdoor_shades((shd.duplicate() for shd in my_shds))

    # Get model
    model_name = "My_model-" + agent_ID
    my_model = Mdl(apert_rooms, my_faces, my_shades2, my_apertures, my_doors, model_name)
    
    if execution == poss_execution[0]:                            
        # Save model to HBJSON in local path
        my_model.to_hbjson(name = model_name, folder=model_fld)
        
    else: # Local execution
        print ("Locally")
        print ("=======")
        # Additional settings
        my_measures = [] #HB load measures
        my_add_str = [] #additional strings to add IDF, only for advanced users
        write_osm = True
        run_osm = True
        
        # Transform model to OSM
        my_results = ModToOSM(my_model, epwpath_str, my_simPars,
                              my_measures, my_add_str, 
                              model_fld_2, write_osm, run_osm)
                      
        # Get EUI (performance)
        my_EUI = getEUI(my_results[4]) # sql only
        this_perf = my_EUI[0] * my_EUI[3] # use intensity by floor area
        
        # Append to collector
        my_newst = states[agent_ID]
        key_to_fill = agent_ID + "_" + my_newst
        avoid_sim[key_to_fill] = this_perf
    
if execution == poss_execution[0]: # Only on cloud mode
    print ("In the cloud")
    print ("=======")
    # Upload models from local path
    study = upload_models(epw_cloud, ddy_cloud, pars_cloud, model_fld, new_study)

    # wait until the study is finished
    check_study_status(study=study)
    
    # Download the files
    download_study_results(api_client=api_client, study=study, output_folder=down_folder)
    
    # When download files < uploaded files, send again (up to three times)
    # AND SAVE THE NEW CODE IN THE RECOVER CSV SO WHEN RECOVER WE RUN AS USUAL
    for i in range(3):
        if len(os.listdir(down_folder)) != len(os.listdir(model_fld)):
            clear_folder(down_folder) # Just in case delete all
            study = upload_models(epw_cloud, ddy_cloud, pars_cloud, model_fld, new_study)
            check_study_status(study=study)
            download_study_results(api_client=api_client, study=study, output_folder=down_folder)
            #rerun_ids["study_id"] = study.id
        else:
            break                  

    # If after three attempts, still not working, send warning, stop process
    if len(os.listdir(down_folder)) != len(os.listdir(model_fld)):
        print ("LESS DOWN RESULTS THAN UP MODELS!")
                            
    # Read the files
    perfs = read_jsons(down_folder)
    
    for agent_ID in sim_ids:
        my_newst = states[agent_ID]
        key_to_fill = agent_ID + "_" + my_newst
        avoid_sim[key_to_fill] = perfs[agent_ID]
    
for agent_ID in my_neigh.AgInNeigh:
    # Recover data from collector
    key_to_search = agent_ID + "_" + states[agent_ID]
    perfor = avoid_sim[key_to_search]
    
    # Prepare data for csv
    csv_towrite = {"year":-1, "agent_id": agent_ID, 
                   "performance": perfor, "occ_pts":sizes[agent_ID],
                   "Mode":mode, "Location":my_location}

    # Save the year performance in a csv
    # generate a model for each year
    my_total_perfs = csv_out + "\\" + "total_perfs.csv"
    dew_file = not os.path.isfile(my_total_perfs)
    with open(my_total_perfs, 'a', newline='') as out_file:
        fc = csv.DictWriter(out_file, csv_towrite.keys())
        if dew_file:
            fc.writeheader()
        fc.writerow(csv_towrite)
    
####
# Now do the same but for every year
####
for year in years:  
    print ("#######")
    print ("Evaluating year:{}".format(year))
    print ("#######")  

    geoms = {}
    sizes = {}
    # Search for actions on the csv and apply
    agents_thisy = []
    actions_thisy = []
    for csv_line in dict_list:        
        if int(csv_line["year"]) == year:
            agent_id = agents_thisy.append(csv_line["agent_id"])
            action = actions_thisy.append(int(csv_line["actions"]))
            
    for k in range(len(agents_thisy)):        
        this_agent = my_neigh.GetAgentbyID(agents_thisy[k])
        this_agent.Extend(actions_thisy[k])
        
    # get joint states for all agents
    states = my_neigh.GetJStatesN(my_neigh.AgInNeigh)
    
    # Identify those that do not register a state yet
    excepmt_ids = []
    for agent_ID in my_neigh.AgInNeigh:
        key_to_search = agent_ID + "_" + states[agent_ID]
        if key_to_search in avoid_sim:
            excepmt_ids.append(agent_ID)
    
    sim_ids = list(set(my_neigh.AgInNeigh) - set(excepmt_ids))
            
    # add all geometries to dict (including those that not receive action)
    for agent_ID in my_neigh.AgInNeigh:
        this_agent = my_neigh.GetAgentbyID(agent_ID)
        geoms[agent_ID] = this_agent.OutBrep
        sizes[agent_ID] = this_agent.NOccupiedPts
        
        # record geometric state on the roofs csv
        this_agent_dicts = RoofInfoAgent(this_agent, agent_ID, year)
        
        my_heights_csv = csv_out + "\\" + "roof_h.csv"
        sew_file = not os.path.isfile(my_heights_csv)
        with open(my_heights_csv, 'a', newline='') as out_file:
            fc = csv.DictWriter(out_file, this_agent_dicts[0].keys())
            if sew_file:
                fc.writeheader()
            fc.writerows(this_agent_dicts)

    # Get ready receiving formder for cloud execution
    if execution == poss_execution[0]:
        if len(os.listdir(model_fld)) > 0:
            clear_folder(model_fld)
        if len(os.listdir(down_folder)) > 0:
            clear_folder(down_folder)
    
    # Get the performance of each agent    
    for agent_ID in sim_ids:
        # current geometry
        my_geom = [geoms[agent_ID]]
        
        # Generate context only with my neighbours
        context_ = [value for key, value in geoms.items()
                    if key in all_neighs[agent_ID]]
        
        # Get rooms from solids (EACH DWELLING IS ONE ROOM!)
        my_roomname = "room" + agent_ID                
        my_rooms = RoomSolid(my_geom, my_roomname, my_modset, [my_CSetClim], [myPType], myConditioned,
                              my_roofangle)
        
        apert_rooms = ApertByRatio(my_rooms, my_aper_ratio, my_subdivision, my_win_hgt, my_sill_hgt,
                                    my_h_sep, my_v_sep, my_oper_apert)
    
        # Get shades
        my_shdgeo = context_
        my_shd_name = "Context" + agent_ID
        my_shds = Shd(my_shdgeo, my_shd_name, context_attach, my_shade_energyconst, my_shd_transm,
                      my_radshd_mod)
    
        # Add shades to model
        for room in apert_rooms:
            room.add_outdoor_shades((shd.duplicate() for shd in my_shds))
    
        # Get model
        model_name = "My_model-" + agent_ID
        my_model = Mdl(apert_rooms, my_faces, my_shades2, my_apertures, my_doors, model_name)
        
        if execution == poss_execution[0]:                            
            # Save model to HBJSON in local path
            my_model.to_hbjson(name = model_name, folder=model_fld)
            
        else: # Local execution
            print ("Locally")
            print ("=======")
            # Additional settings
            my_measures = [] #HB load measures
            my_add_str = [] #additional strings to add IDF, only for advanced users
            write_osm = True
            run_osm = True
            
            # Transform model to OSM
            my_results = ModToOSM(my_model, epwpath_str, my_simPars,
                                  my_measures, my_add_str, 
                                  model_fld_2, write_osm, run_osm)
                          
            # Get EUI (performance)
            my_EUI = getEUI(my_results[4]) # sql only
            this_perf = my_EUI[0] * my_EUI[3] # use intensity by floor area
            
            # Append to collector
            my_newst = states[agent_ID]
            key_to_fill = agent_ID + "_" + my_newst
            avoid_sim[key_to_fill] = this_perf
        
    if execution == poss_execution[0]: # Only on cloud mode
        print ("In the cloud")
        print ("=======")
        # Upload models from local path
        study = upload_models(epw_cloud, ddy_cloud, pars_cloud, model_fld, new_study)

        # wait until the study is finished
        check_study_status(study=study)
        
        # Download the files
        download_study_results(api_client=api_client, study=study, output_folder=down_folder)
        
        # When download files < uploaded files, send again (up to three times)
        # AND SAVE THE NEW CODE IN THE RECOVER CSV SO WHEN RECOVER WE RUN AS USUAL
        for i in range(3):
            if len(os.listdir(down_folder)) != len(os.listdir(model_fld)):
                clear_folder(down_folder) # Just in case delete all
                study = upload_models(epw_cloud, ddy_cloud, pars_cloud, model_fld, new_study)
                check_study_status(study=study)
                download_study_results(api_client=api_client, study=study, output_folder=down_folder)
                #rerun_ids["study_id"] = study.id
            else:
                break                  

        # If after three attempts, still not working, send warning, stop process
        if len(os.listdir(down_folder)) != len(os.listdir(model_fld)):
            print ("LESS DOWN RESULTS THAN UP MODELS!")
            kill_flag = True
            break
        else:
            kill_flag = False
                                
        # Read the files
        perfs = read_jsons(down_folder)
        
        for agent_ID in sim_ids:
            my_newst = states[agent_ID]
            key_to_fill = agent_ID + "_" + my_newst
            avoid_sim[key_to_fill] = perfs[agent_ID]
        
    for agent_ID in my_neigh.AgInNeigh:
        # Recover data from collector
        key_to_search = agent_ID + "_" + states[agent_ID]
        perfor = avoid_sim[key_to_search]
        
        # Prepare data for csv
        csv_towrite = {"year":year, "agent_id": agent_ID, 
                       "performance": perfor, "occ_pts":sizes[agent_ID],
                       "Mode":mode, "Location":my_location}
    
        # Save the year performance in a csv
        # generate a model for each year
        my_total_perfs = csv_out + "\\" + "total_perfs.csv"
        dew_file = not os.path.isfile(my_total_perfs)
        with open(my_total_perfs, 'a', newline='') as out_file:
            fc = csv.DictWriter(out_file, csv_towrite.keys())
            if dew_file:
                fc.writeheader()
            fc.writerow(csv_towrite)