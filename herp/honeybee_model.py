'''THIS MODULE CONTAINS THE FUNCTIONS TO GET A HBJSON FROM HONEYBEE GEOMETRIES.
IT IS TAKEN FROM GRASSHOPPER COMPONENTS FREED FROM THEIR GRASSHOPPER DEPENDENCIES'''

from honeybee_energy.simulation.output import SimulationOutput
from honeybee_energy.simulation.runperiod import RunPeriod
from honeybee_energy.simulation.daylightsaving import DaylightSavingTime
from honeybee_energy.simulation.parameter import SimulationParameter
from honeybee_energy.simulation.shadowcalculation import ShadowCalculation

from ladybug.dt import Date, DateTime

from ladybug_rhino.togeometry import to_vector2d

#####
# SIM OUTPUT COMPONENT
#####
def SimOut(zone_energy_use_, hvac_energy_use_, gains_and_losses_, comfort_metrics_, surface_temperature_,
           surface_energy_flow_, load_type_, _report_frequency_):
    # set default reporting frequency.
    _report_frequency_ = _report_frequency_.title() \
        if _report_frequency_ is not None else 'Hourly'

    # set the default load_type
    load_type_ = load_type_.title() if load_type_ is not None else 'All'

    # create the starting simulation output object.
    sim_output = SimulationOutput(reporting_frequency=_report_frequency_)

    # set each of the requested outputs
    if zone_energy_use_:
        sim_output.add_zone_energy_use(load_type_)
    if hvac_energy_use_:
        sim_output.add_hvac_energy_use()
    if gains_and_losses_:
        load_type = load_type_ if load_type_ != 'All' else 'Total'
        sim_output.add_gains_and_losses(load_type)
    if comfort_metrics_:
        sim_output.add_comfort_metrics()
    if surface_temperature_:
        sim_output.add_surface_temperature()
    if surface_energy_flow_:
        sim_output.add_surface_energy_flow()

    return sim_output

#####
# SIMULATION PARAMETERS COMPONENT
#####
# Create a shadow calc object to input in the sim pars object creation
def ShadCalc(_solar_dist_, _calc_method_, _update_method_, _frequency_, _max_figures_): 
    # dictionary to convert to acceptable solar distributions
    SOLAR_DISTRIBUTIONS = {
        '0': 'MinimalShadowing',
        '1': 'FullExterior',
        '2': 'FullInteriorAndExterior',
        '3': 'FullExteriorWithReflections',
        '4': 'FullInteriorAndExteriorWithReflections',
        'MinimalShadowing': 'MinimalShadowing',
        'FullExterior': 'FullExterior',
        'FullInteriorAndExterior': 'FullInteriorAndExterior',
        'FullExteriorWithReflections': 'FullExteriorWithReflections',
        'FullInteriorAndExteriorWithReflections': 'FullInteriorAndExteriorWithReflections'
        }
    
    
    # process the solar distribution
    try:
        _solar_dist_ = SOLAR_DISTRIBUTIONS[_solar_dist_] if _solar_dist_ is not None \
            else 'FullExteriorWithReflections'
    except KeyError:
        raise ValueError(' Input _solar_dist_ "{}" is not valid.\nChoose from the '
            'following:\n{}'.format(_solar_dist_, SOLAR_DISTRIBUTIONS.keys()))
    
    # set other default values
    _calc_method_ = _calc_method_ if _calc_method_ is not None else 'PolygonClipping'
    _update_method_ = _update_method_ if _update_method_ is not None else 'Periodic'
    _frequency_ = _frequency_ if _frequency_ is not None else 30
    _max_figures_ = _max_figures_ if _max_figures_ is not None else 15000
    
    # create the object
    shadow_calc = ShadowCalculation(
        _solar_dist_, _calc_method_, _update_method_, _frequency_, _max_figures_)
    
    return shadow_calc


def SimPars(_north_, _output_, _run_period_, daylight_saving_, holidays_, _start_dow_,
            _timestep_, _terrain_, _sim_control_, _shadow_calc_, _sizing_):
    # set default simulation outputs
    if _output_ is None:
        _output_ = SimulationOutput()
        _output_.add_zone_energy_use()
        _output_.add_hvac_energy_use()

    # set default simulation run period
    _run_period_ = RunPeriod.from_analysis_period(_run_period_) \
        if _run_period_ is not None else RunPeriod()

    # set the daylight savings if it is input
    if daylight_saving_ is not None:
        daylight_saving = DaylightSavingTime.from_analysis_period(daylight_saving_)
        _run_period_.daylight_saving_time = daylight_saving

    # set the holidays if requested.
    if len(holidays_) != 0:
        try:
            dates = tuple(Date.from_date_string(date) for date in holidays_)
        except ValueError:
            dates = tuple(DateTime.from_date_time_string(date).date for date in holidays_)
        _run_period_.holidays = dates

    # set the start day of the week if it is input
    if _start_dow_ is not None:
        _run_period_.start_day_of_week = _start_dow_.title()

    # set the default timestep
    _timestep_ = _timestep_ if _timestep_ is not None else 6

    # set the default timestep
    _terrain_ = _terrain_.title() if _terrain_ is not None else 'City'

    # return final simulation parameters
    sim_par = SimulationParameter(output=_output_,
                                  run_period=_run_period_,
                                  timestep=_timestep_,
                                  simulation_control=_sim_control_,
                                  shadow_calculation=_shadow_calc_,
                                  sizing_parameter=_sizing_,
                                  terrain_type=_terrain_)

    # set the north if it is not defaulted
    if _north_ is not None:
        try:
            sim_par.north_vector = to_vector2d(_north_)
        except AttributeError:  # north angle instead of vector
            sim_par.north_angle = float(_north_)

    return sim_par