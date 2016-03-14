from openmdao.api import Component, Group, Problem, IndepVarComp
from akima import Akima, akima_interp
from utilities import smooth_min, hermite_spline

import numpy as np
from scipy import interp


def add_gen_params_IdepVarComps(openmdao_group, datasize):
    openmdao_group.add('gp0', IndepVarComp('gen_params:pP', 3.0, pass_by_obj=True), promotes=['*'])
    openmdao_group.add('gp1', IndepVarComp('gen_params:windSpeedToCPCT_wind_speed', np.zeros(datasize), units='m/s',
                                  desc='range of wind speeds', pass_by_obj=True), promotes=['*'])
    openmdao_group.add('gp2', IndepVarComp('gen_params:windSpeedToCPCT_CP', np.zeros(datasize),
                                  desc='power coefficients', pass_by_obj=True), promotes=['*'])
    openmdao_group.add('gp3', IndepVarComp('gen_params:windSpeedToCPCT_CT', np.zeros(datasize),
                                  desc='thrust coefficients', pass_by_obj=True), promotes=['*'])


class WindFrame(Component):
    """ Calculates the locations of each turbine in the wind direction reference frame """

    def __init__(self, nTurbines, resolution=0, differentiable=True):

        # print 'entering windframe __init__ - analytic'

        super(WindFrame, self).__init__()

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-5
        self.fd_options['step_type'] = 'relative'

        if not differentiable:
            self.fd_options['force_fd'] = True
            self.fd_options['form'] = 'forward'

        self.nTurbines = nTurbines

        # flow property variables
        self.add_param('wind_speed', val=8.0, units='m/s', desc='free stream wind velocity')
        self.add_param('wind_direction', val=270.0, units='deg',
                       desc='wind direction using direction from, in deg. cw from north as in meteorological data')

        # Explicitly size input arrays
        self.add_param('turbineX', val=np.zeros(nTurbines), units='m', desc='x positions of turbines in original ref. frame')
        self.add_param('turbineY', val=np.zeros(nTurbines), units='m', desc='y positions of turbines in original ref. frame')

        # variables for testing wind speed at various locations
        self.add_param('ws_position', val=np.zeros(resolution * resolution), units='m',
                       desc='position of desired measurements in original ref. frame')

        # Explicitly size output arrays
        self.add_param('wsw_position', val=np.zeros(resolution * resolution), units='m',
                       desc='position of desired measurements in wind ref. frame')

        # add output
        self.add_output('turbineXw', val=np.zeros(nTurbines), units='m', desc='downwind coordinates of turbines')
        self.add_output('turbineYw', val=np.zeros(nTurbines), units='m', desc='crosswind coordinates of turbines')

    def solve_nonlinear(self, params, unknowns, resids):

        windDirectionDeg = params['wind_direction']

        # get turbine positions and velocity sampling positions
        turbineX = params['turbineX']
        turbineY = params['turbineY']

        # print "in windframe", turbineX, turbineY

        # if self.ws_position.any():
        #     velX = self.ws_position[:, 0]
        #     velY = self.ws_position[:, 1]
        # else:
        #     velX = np.zeros([0, 0])
        #     velY = np.zeros([0, 0])

        # convert to downwind(x)-crosswind(y) coordinates
        windDirectionDeg = 270. - windDirectionDeg
        if windDirectionDeg < 0.:
            windDirectionDeg += 360.
        windDirectionRad = np.pi*windDirectionDeg/180.0             # inflow wind direction in radians
        # rotationMatrix = np.array([(np.cos(-windDirectionRad), -np.sin(-windDirectionRad)),
        #                            (np.sin(-windDirectionRad), np.cos(-windDirectionRad))])
        turbineXw = turbineX*np.cos(-windDirectionRad)-turbineY*np.sin(-windDirectionRad)
        turbineYw = turbineX*np.sin(-windDirectionRad)+turbineY*np.cos(-windDirectionRad)

        unknowns['turbineXw'] = turbineXw
        unknowns['turbineYw'] = turbineYw

    def linearize(self, params, unknowns, resids):

        # print 'entering windframe - provideJ'

        nTurbines = self.nTurbines

        windDirectionDeg = params['wind_direction']

        windDirectionDeg = 270. - windDirectionDeg
        if windDirectionDeg < 0.:
            windDirectionDeg += 360.

        windDirectionRad = np.pi*windDirectionDeg/180.0             # inflow wind direction in radians

        dturbineXw_dturbineX = np.eye(nTurbines, nTurbines)*np.cos(-windDirectionRad)
        dturbineXw_dturbineY = np.eye(nTurbines, nTurbines)*(-np.sin(-windDirectionRad))
        dturbineYw_dturbineX = np.eye(nTurbines, nTurbines)*np.sin(-windDirectionRad)
        dturbineYw_dturbineY = np.eye(nTurbines, nTurbines)*np.cos(-windDirectionRad)

        # print dturbineXw_dturbineY.shape
        J = {}

        J[('turbineXw', 'turbineX')] = dturbineXw_dturbineX
        J[('turbineXw', 'turbineY')] = dturbineXw_dturbineY
        J[('turbineYw', 'turbineX')] = dturbineYw_dturbineX
        J[('turbineYw', 'turbineY')] = dturbineYw_dturbineY


        # print 'end windframe jacobian'

        return J


class AdjustCtCpYaw(Component):
    """ Adjust Cp and Ct to yaw if they are not already adjusted """

    def __init__(self, nTurbines, direction_id=0, differentiable=True):

        # print 'entering adjustCtCp __init__ - analytic'
        super(AdjustCtCpYaw, self).__init__()

        self. direction_id = direction_id

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-5
        self.fd_options['step_type'] = 'relative'

        if not differentiable:
            self.fd_options['force_fd'] = True
            self.fd_options['form'] = 'forward'

        # Explicitly size input arrays
        self.add_param('Ct_in', val=np.zeros(nTurbines), desc='Thrust coefficient for all turbines')
        self.add_param('Cp_in', val=np.zeros(nTurbines), desc='power coefficient for all turbines')
        self.add_param('yaw%i' % direction_id, val=np.zeros(nTurbines), units='deg', desc='yaw of each turbine')

        # Explicitly size output arrays
        self.add_output('Ct_out', val=np.zeros(nTurbines), desc='Thrust coefficient for all turbines')
        self.add_output('Cp_out', val=np.zeros(nTurbines), desc='power coefficient for all turbines')

        # parameters since var trees are not supports
        self.add_param('gen_params:pP', 1.88, pass_by_obj=True)
        self.add_param('gen_params:CTcorrected', False,
                       desc='CT factor already corrected by CCBlade calculation (approximately factor cos(yaw)^2)', pass_by_obj=True)
        self.add_param('gen_params:CPcorrected', False,
                       desc='CP factor already corrected by CCBlade calculation (assumed with approximately factor cos(yaw)^3)', pass_by_obj=True)
        self.add_param('floris_params:FLORISoriginal', True,
                       desc='override all parameters and use FLORIS as original in first Wind Energy paper', pass_by_obj=True)

    def solve_nonlinear(self, params, unknowns, resids):

        direction_id = self.direction_id

        # print 'entering adjustCtCP - analytic'

        # collect inputs
        Ct = params['Ct_in']
        Cp = params['Cp_in']
        yaw = params['yaw%i' % direction_id] * np.pi / 180.
        # print 'in Ct correction, Ct_in: ', Ct
        # determine floris_parameter values
        if params['floris_params:FLORISoriginal']:
            pP = 1.88
        else:
            pP = params['gen_params:pP']

        CTcorrected = params['gen_params:CTcorrected']
        CPcorrected = params['gen_params:CPcorrected']

        # calculate new CT values, if desired
        if not CTcorrected:
            # print "ct not corrected"
            unknowns['Ct_out'] = np.cos(yaw)*np.cos(yaw)*Ct
            # print 'in ct correction Ct_out: ', unknowns['Ct_out']
        else:
            unknowns['Ct_out'] = Ct

        # calculate new CP values, if desired
        if not CPcorrected:
            unknowns['Cp_out'] = Cp * np.cos(yaw) ** pP
        else:
            unknowns['Cp_out'] = Cp

    def linearize(self, params, unknowns, resids):
        #TODO check derivatives
        direction_id = self.direction_id

        # print 'entering CtCp linearize'
        # collect inputs
        Ct = params['Ct_in']
        Cp = params['Cp_in']
        nTurbines = np.size(Ct)
        yaw = params['yaw%i' % direction_id] * np.pi / 180.

        # determine floris_parameter values
        if params['floris_params:FLORISoriginal']:
            pP = 1.88
        else:
            pP = params['gen_params:pP']

        CTcorrected = params['gen_params:CTcorrected']
        CPcorrected = params['gen_params:CPcorrected']

        # calculate gradients
        J = {}

        if not CTcorrected:
            J[('Ct_out', 'Ct_in')] = np.eye(nTurbines) * np.cos(yaw) * np.cos(yaw)
            J[('Ct_out', 'Cp_in')] = np.zeros((nTurbines, nTurbines))
            J[('Ct_out', 'yaw%i' % direction_id)] = np.eye(nTurbines) * Ct * (-2. * np.sin(yaw) * np.cos(yaw)) * np.pi / 180.
        else:
            J[('Ct_out', 'Ct_in')] = np.eye(nTurbines, nTurbines)
            J[('Ct_out', 'Cp_in')] = np.zeros((nTurbines, nTurbines))
            J[('Ct_out', 'yaw%i' % direction_id)] = np.zeros((nTurbines, nTurbines))

        if not CPcorrected:
            J[('Cp_out', 'Cp_in')] = np.eye(nTurbines, nTurbines) * np.cos(yaw) ** pP
            J[('Cp_out', 'Ct_in')] = np.zeros((nTurbines, nTurbines))
            J[('Cp_out', 'yaw%i' % direction_id)] = np.eye(nTurbines, nTurbines) * (
                -Cp * pP * np.sin(yaw) * np.cos(yaw) ** (pP - 1.0)) * np.pi / 180.
        else:
            J[('Cp_out', 'Cp_in')] = np.eye(nTurbines, nTurbines)
            J[('Cp_out', 'Ct_in')] = np.zeros((nTurbines, nTurbines))
            J[('Cp_out', 'yaw%i' % direction_id)] = np.zeros((nTurbines, nTurbines))

        return J


class WindFarmAEP(Component):
    """ Estimate the AEP based on power production for each direction and weighted by wind direction frequency  """

    def __init__(self, nDirections):

        super(WindFarmAEP, self).__init__()

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-5
        self.fd_options['step_type'] = 'relative'

        # define inputs
        self.add_param('power_directions', np.zeros(nDirections), units='kW',
                       desc='vector containing the power production at each wind direction ccw from north')
        self.add_param('windrose_frequencies', np.zeros(nDirections),
                       desc='vector containing the weighted frequency of wind at each direction ccw from east using '
                            'direction too')

        # define output
        self.add_output('AEP', val=0.0, units='kWh', desc='total annual energy output of wind farm')

    def solve_nonlinear(self, params, unknowns, resids):

        # # print 'in AEP'

        # locally name input values
        power_directions = params['power_directions']
        windrose_frequencies = params['windrose_frequencies']

        # number of hours in a year
        hours = 8760.0

        # calculate approximate AEP
        AEP = sum(power_directions*windrose_frequencies)*hours

        # promote AEP result to class attribute
        unknowns['AEP'] = AEP

        print 'In AEP, AEP %s' % unknowns['AEP']

    def linearize(self, params, unknowns, resids):

        # # print 'entering AEP - provideJ'

        # assign params to local variables
        windrose_frequencies = params['windrose_frequencies']
        power_directions = params['power_directions']
        ndirs = np.size(windrose_frequencies)

        # number of hours in a year
        hours = 8760.0

        # calculate the derivative of outputs w.r.t. each wind direction
        dAEP_dpower = np.ones(ndirs)*windrose_frequencies*hours
        dAEP_dwindrose_frequencies = np.ones(ndirs)*power_directions*hours

        # print 'dAEP = ', dAEP_dpower
        J = {}

        J['AEP', 'power_directions'] = np.array([dAEP_dpower])
        J['AEP', 'windrose_frequencies'] = np.array([dAEP_dwindrose_frequencies])

        return J


class SpacingComp(Component):
    """
    Calculates inter-turbine spacing for all turbine pairs
    """

    def __init__(self, nTurbines):

        # print 'entering dist_const __init__

        super(SpacingComp, self).__init__()

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-5
        self.fd_options['step_type'] = 'relative'

        # Explicitly size input arrays
        self.add_param('turbineX', val=np.zeros(nTurbines),
                       desc='x coordinates of turbines in wind dir. ref. frame')
        self.add_param('turbineY', val=np.zeros(nTurbines),
                       desc='y coordinates of turbines in wind dir. ref. frame')

        # Explicitly size output array
        self.add_output('separation_squared', val=np.zeros((nTurbines-1.)*nTurbines/2.),
                        desc='spacing of all turbines in the wind farm')

    def solve_nonlinear(self, params, unknowns, resids):
        # print 'in dist const'

        turbineX = params['turbineX']
        turbineY = params['turbineY']
        nTurbines = turbineX.size
        separation_squared = np.zeros((nTurbines-1.)*nTurbines/2.)

        k = 0
        for i in range(0, nTurbines):
            for j in range(i+1, nTurbines):
                separation_squared[k] = (turbineX[j]-turbineX[i])**2+(turbineY[j]-turbineY[i])**2
                k += 1
        unknowns['separation_squared'] = separation_squared

    def linearize(self, params, unknowns, resids):
        # print 'entering dist const - linearize'
        turbineX = params['turbineX']
        turbineY = params['turbineY']
        # print turbineX
        # print turbineY
        nTurbines = turbineX.size
        dS = np.zeros(((nTurbines-1.)*nTurbines/2., 2*nTurbines))
        k = 0
        # print 'in dist_const, turbineX = ', turbineX
        # print 'in dist_const, turbineY = ', turbineY

        for i in range(0, nTurbines):
            for j in range(i+1, nTurbines):
                # separation wrt Xj
                dS[k, j] = 2*(turbineX[j]-turbineX[i])
                # separation wrt Xi
                dS[k, i] = -2*(turbineX[j]-turbineX[i])
                # separation wrt Yj
                dS[k, j+nTurbines] = 2*(turbineY[j]-turbineY[i])
                # separation wrt Yi
                dS[k, i+nTurbines] = -2*(turbineY[j]-turbineY[i])
                k += 1

        J = {}

        J['separation_squared', 'turbineX'] = dS[:, :nTurbines]
        J['separation_squared', 'turbineY'] = dS[:, nTurbines:]
        # print J
        return J


class MUX(Component):
    """ Connect input elements into a single array  """

    def __init__(self, nElements, units=None):

        super(MUX, self).__init__()

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-5
        self.fd_options['step_type'] = 'relative'

        # define inputs
        if units == None:
            for i in range(0, nElements):
                self.add_param('input%i' % i, val=0.0, desc='scalar input')
        else:
            for i in range(0, nElements):
                self.add_param('input%i' % i, val=0.0, units=units, desc='scalar input')

        # define output
        if units == None:
            self.add_output('Array', np.zeros(nElements), desc='ndArray of all the scalar inputs')
        else:
            self.add_output('Array', np.zeros(nElements), units=units, desc='ndArray of all the scalar inputs')

        self.nElements = nElements

    def solve_nonlinear(self, params, unknowns, resids):

        # print 'in MUX'

        # assign input values to the output array
        for i in range(0, self.nElements):
            exec("unknowns['Array'][%i] = params['input%i']" % (i, i))

        # print unknowns['Array']

    def linearize(self, params, unknowns, resids):

        dArray_dInput = np.zeros(self.nElements)

        J = {}

        for i in range(0, self.nElements):
            dArray_dInput[i] = 1.0
            J['Array', 'input%i' % i] = np.array(dArray_dInput)
            dArray_dInput[i] = 0.0

        return J


class DeMUX(Component):
    """ split a given array into separate elements """

    def __init__(self, nElements, units=None):

        super(DeMUX, self).__init__()

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-5
        self.fd_options['step_type'] = 'relative'

        # define input
        if units == None:
            self.add_param('Array', np.zeros(nElements), desc='ndArray of scalars')
        else:
            self.add_param('Array', np.zeros(nElements), units=units, desc='ndArray of scalars')

        # define outputs
        if units == None:
            for i in range(0, nElements):
                self.add_output('output%i' % i, val=0.0, desc='scalar output')
        else:
            for i in range(0, nElements):
                self.add_output('output%i' % i, val=0.0, units=units, desc='scalar output')
        # print 'demux elements: ', nElements
        self.nElements = nElements

    def solve_nonlinear(self, params, unknowns, resids):

        # print 'in MUX'

        # assign input values to the output array
        for i in range(0, self.nElements):
            exec("unknowns['output%i'] = params['Array'][%i]" % (i, i))

        # print unknowns['Array']

    def linearize(self, params, unknowns, resids):

        doutput_dArray = np.eye(self.nElements)

        J = {}

        for i in range(0, self.nElements):
            # print doutput_dArray
            J['output%i' % i, 'Array'] = np.reshape(doutput_dArray[i, :], (1, self.nElements))

        return J


class DeMUX2D(Component):
    """ split a given 2D array into individual rows """
    # TODO FINISH THIS COMPONENT
    def __init__(self, ArrayShape):

        super(DeMUX2D, self).__init__()

        # define input
        self.add_param('Array', np.zeros(ArrayShape), desc='ndArray of scalars')

        # define outputs
        for i in range(0, ArrayShape[0]):
            self.add_output('output%i' % i, np.zeros(ArrayShape[1]), desc='scalar output')
        # print 'demux rows: ', ArrayShape[0]
        self.ArrayShape = ArrayShape

    def solve_nonlinear(self, params, unknowns, resids):

        # print 'in MUX'

        # assign input values to the output array
        for i in range(0, self.ArrayShape[0]):
            exec("unknowns['output%i[:]'] = params['Array'][%i, :]" % (i, i))

        # print unknowns['Array']

    def linearize(self, params, unknowns, resids):

        doutput_dArray = np.eye(self.ArrayShape)

        J = {}

        for i in range(0, self.ArrayShape[0]):
            # print doutput_dArray
            J['output%i' % i, 'Array'] = np.reshape(doutput_dArray[i, :], (1, 2))

        return J


# ---- if you know wind speed to power and thrust, you can use these tools ----------------
class CPCT_Interpolate_Gradients(Component):

    def __init__(self, nTurbines, direction_id=0, datasize=0):

        super(CPCT_Interpolate_Gradients, self).__init__()

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-5
        self.fd_options['step_type'] = 'relative'

        self.nTurbines = nTurbines
        self.direction_id = direction_id
        self.datasize = datasize

        # add inputs and outputs
        self.add_param('yaw%i' % direction_id, np.zeros(nTurbines), desc='yaw error', units='deg')
        self.add_param('velocitiesTurbines%i' % direction_id, np.zeros(nTurbines), units='m/s', desc='hub height wind speed') # Uhub
        self.add_output('Cp_out', np.zeros(nTurbines))
        self.add_output('Ct_out', np.zeros(nTurbines))

        # add variable trees
        self.add_param('gen_params:pP', 3.0, pass_by_obj=True)
        self.add_param('gen_params:windSpeedToCPCT_wind_speed', np.zeros(datasize), units='m/s',
                       desc='range of wind speeds', pass_by_obj=True)
        self.add_param('gen_params:windSpeedToCPCT_CP', np.zeros(datasize), iotype='out',
                       desc='power coefficients', pass_by_obj=True)
        self.add_param('gen_params:windSpeedToCPCT_CT', np.zeros(datasize), iotype='out',
                       desc='thrust coefficients', pass_by_obj=True)

    def solve_nonlinear(self, params, unknowns, resids):
        direction_id = self.direction_id
        pP = self.params['gen_params:pP']
        # print "turbine 2 inflow velocity: %s" % params['velocitiesTurbines%i' % direction_id]
        # print "pP: %f" % pP
        wind_speed_ax = np.cos(self.params['yaw%i' % direction_id]*np.pi/180.0)**(pP/3.0)*self.params['velocitiesTurbines%i' % direction_id]
        # use interpolation on precalculated CP-CT curve
        wind_speed_ax = np.maximum(wind_speed_ax, self.params['gen_params:windSpeedToCPCT_wind_speed'][0])
        wind_speed_ax = np.minimum(wind_speed_ax, self.params['gen_params:windSpeedToCPCT_wind_speed'][-1])
        self.unknowns['Cp_out'] = interp(wind_speed_ax, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CP'])
        self.unknowns['Ct_out'] = interp(wind_speed_ax, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CT'])

        # for i in range(0, len(self.unknowns['Ct_out'])):
        #     self.unknowns['Ct_out'] = max(max(self.unknowns['Ct_out']), self.unknowns['Ct_out'][i])
        # normalize on incoming wind speed to correct coefficients for yaw
        self.unknowns['Cp_out'] = self.unknowns['Cp_out'] * np.cos(self.params['yaw%i' % direction_id]*np.pi/180.0)**pP
        self.unknowns['Ct_out'] = self.unknowns['Ct_out'] * np.cos(self.params['yaw%i' % direction_id]*np.pi/180.0)**2
        # print 'in CPCT interp, wind_speed_hub = ', self.params['velocitiesTurbines%i' % direction_id]
        # print 'in CPCT: ', params['velocitiesTurbines0']

    def linearize(self, params, unknowns, resids):  # standard central differencing
        # set step size for finite differencing
        h = 1e-6
        direction_id = self.direction_id

        # calculate upper and lower function values
        wind_speed_ax_high_yaw = np.cos((self.params['yaw%i' % direction_id]+h)*np.pi/180.0)**(self.params['gen_params:pP']/3.0)*self.params['velocitiesTurbines%i' % direction_id]
        wind_speed_ax_low_yaw = np.cos((self.params['yaw%i' % direction_id]-h)*np.pi/180.0)**(self.params['gen_params:pP']/3.0)*self.params['velocitiesTurbines%i' % direction_id]
        wind_speed_ax_high_wind = np.cos(self.params['yaw%i' % direction_id]*np.pi/180.0)**(self.params['gen_params:pP']/3.0)*(self.params['velocitiesTurbines%i' % direction_id]+h)
        wind_speed_ax_low_wind = np.cos(self.params['yaw%i' % direction_id]*np.pi/180.0)**(self.params['gen_params:pP']/3.0)*(self.params['velocitiesTurbines%i' % direction_id]-h)

        # use interpolation on precalculated CP-CT curve
        wind_speed_ax_high_yaw = np.maximum(wind_speed_ax_high_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'][0])
        wind_speed_ax_low_yaw = np.maximum(wind_speed_ax_low_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'][0])
        wind_speed_ax_high_wind = np.maximum(wind_speed_ax_high_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'][0])
        wind_speed_ax_low_wind = np.maximum(wind_speed_ax_low_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'][0])

        wind_speed_ax_high_yaw = np.minimum(wind_speed_ax_high_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'][-1])
        wind_speed_ax_low_yaw = np.minimum(wind_speed_ax_low_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'][-1])
        wind_speed_ax_high_wind = np.minimum(wind_speed_ax_high_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'][-1])
        wind_speed_ax_low_wind = np.minimum(wind_speed_ax_low_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'][-1])

        CP_high_yaw = interp(wind_speed_ax_high_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CP'])
        CP_low_yaw = interp(wind_speed_ax_low_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CP'])
        CP_high_wind = interp(wind_speed_ax_high_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CP'])
        CP_low_wind = interp(wind_speed_ax_low_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CP'])

        CT_high_yaw = interp(wind_speed_ax_high_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CT'])
        CT_low_yaw = interp(wind_speed_ax_low_yaw, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CT'])
        CT_high_wind = interp(wind_speed_ax_high_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CT'])
        CT_low_wind = interp(wind_speed_ax_low_wind, self.params['gen_params:windSpeedToCPCT_wind_speed'], self.params['gen_params:windSpeedToCPCT_CT'])

        # normalize on incoming wind speed to correct coefficients for yaw
        CP_high_yaw = CP_high_yaw * np.cos((self.params['yaw%i' % direction_id]+h)*np.pi/180.0)**self.params['gen_params:pP']
        CP_low_yaw = CP_low_yaw * np.cos((self.params['yaw%i' % direction_id]-h)*np.pi/180.0)**self.params['gen_params:pP']
        CP_high_wind = CP_high_wind * np.cos((self.params['yaw%i' % direction_id])*np.pi/180.0)**self.params['gen_params:pP']
        CP_low_wind = CP_low_wind * np.cos((self.params['yaw%i' % direction_id])*np.pi/180.0)**self.params['gen_params:pP']

        CT_high_yaw = CT_high_yaw * np.cos((self.params['yaw%i' % direction_id]+h)*np.pi/180.0)**2
        CT_low_yaw = CT_low_yaw * np.cos((self.params['yaw%i' % direction_id]-h)*np.pi/180.0)**2
        CT_high_wind = CT_high_wind * np.cos((self.params['yaw%i' % direction_id])*np.pi/180.0)**2
        CT_low_wind = CT_low_wind * np.cos((self.params['yaw%i' % direction_id])*np.pi/180.0)**2

        # compute derivative via central differencing and arrange in sub-matrices of the Jacobian
        dCP_dyaw = np.eye(self.nTurbines)*(CP_high_yaw-CP_low_yaw)/(2.0*h)
        dCP_dwind = np.eye(self.nTurbines)*(CP_high_wind-CP_low_wind)/(2.0*h)
        dCT_dyaw = np.eye(self.nTurbines)*(CT_high_yaw-CT_low_yaw)/(2.0*h)
        dCT_dwind = np.eye(self.nTurbines)*(CT_high_wind-CT_low_wind)/(2.0*h)

        # compile Jacobian dict from sub-matrices
        J = {}
        J['Cp_out', 'yaw%i' % direction_id] = dCP_dyaw
        J['Cp_out', 'velocitiesTurbines%i' % direction_id] = dCP_dwind
        J['Ct_out', 'yaw%i' % direction_id] = dCT_dyaw
        J['Ct_out', 'velocitiesTurbines%i' % direction_id] = dCT_dwind

        return J


class CPCT_Interpolate_Gradients_Smooth(Component):

    def __init__(self, nTurbines, direction_id=0, datasize=0):

        super(CPCT_Interpolate_Gradients_Smooth, self).__init__()

        # set finite difference options (fd used for testing only)
        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-6
        self.fd_options['step_type'] = 'relative'

        self.nTurbines = nTurbines
        self.direction_id = direction_id
        self.datasize = datasize

        # add inputs and outputs
        self.add_param('yaw%i' % direction_id, np.zeros(nTurbines), desc='yaw error', units='deg')
        self.add_param('velocitiesTurbines%i' % direction_id, np.zeros(nTurbines), units='m/s', desc='hub height wind speed') # Uhub
        self.add_output('Cp_out', np.zeros(nTurbines))
        self.add_output('Ct_out', np.zeros(nTurbines))

        # add variable trees
        self.add_param('gen_params:pP', 3.0, pass_by_obj=True)
        self.add_param('gen_params:windSpeedToCPCT_wind_speed', np.zeros(datasize), units='m/s',
                       desc='range of wind speeds', pass_by_obj=True)
        self.add_param('gen_params:windSpeedToCPCT_CP', np.zeros(datasize),
                       desc='power coefficients', pass_by_obj=True)
        self.add_param('gen_params:windSpeedToCPCT_CT', np.zeros(datasize),
                       desc='thrust coefficients', pass_by_obj=True)

    def solve_nonlinear(self, params, unknowns, resids):
        direction_id = self.direction_id
        pP = self.params['gen_params:pP']
        yaw = self.params['yaw%i' % direction_id]
        start = 5
        skip = 8
        # Cp = params['gen_params:windSpeedToCPCT_CP'][start::skip]
        Cp = params['gen_params:windSpeedToCPCT_CP']
        # Ct = params['gen_params:windSpeedToCPCT_CT'][start::skip]
        Ct = params['gen_params:windSpeedToCPCT_CT']
        # windspeeds = params['gen_params:windSpeedToCPCT_wind_speed'][start::skip]
        windspeeds = params['gen_params:windSpeedToCPCT_wind_speed']
        #
        # Cp = np.insert(Cp, 0, Cp[0]/2.0)
        # Cp = np.insert(Cp, 0, 0.0)
        # Ct = np.insert(Ct, 0, np.max(params['gen_params:windSpeedToCPCT_CP'])*0.99)
        # Ct = np.insert(Ct, 0, np.max(params['gen_params:windSpeedToCPCT_CT']))
        # windspeeds = np.insert(windspeeds, 0, 2.5)
        # windspeeds = np.insert(windspeeds, 0, 0.0)
        #
        # Cp = np.append(Cp, 0.0)
        # Ct = np.append(Ct, 0.0)
        # windspeeds = np.append(windspeeds, 30.0)

        CPspline = Akima(windspeeds, Cp)
        CTspline = Akima(windspeeds, Ct)

        # n = 500
        # x = np.linspace(0.0, 30., n)
        CP, dCPdvel, _, _ = CPspline.interp(params['velocitiesTurbines%i' % direction_id])
        CT, dCTdvel, _, _ = CTspline.interp(params['velocitiesTurbines%i' % direction_id])

        # print 'in solve_nonlinear', dCPdvel, dCTdvel
        # pP = 3.0
        # print "in rotor, pP = ", pP
        Cp_out = CP*np.cos(yaw*np.pi/180.)**pP
        Ct_out = CT*np.cos(yaw*np.pi/180.)**2.

        print "in rotor, Cp = [%f. %f], Ct = [%f, %f]" % (Cp_out[0], Cp_out[1], Ct_out[0], Ct_out[1])

        self.dCp_out_dyaw = (-np.sin(yaw*np.pi/180.))*(np.pi/180.)*pP*CP*np.cos(yaw*np.pi/180.)**(pP-1.)
        self.dCp_out_dvel = dCPdvel*np.cos(yaw*np.pi/180.)**pP

        # print 'in solve_nonlinear', self.dCp_out_dyaw, self.dCp_out_dvel

        self.dCt_out_dyaw = (-np.sin(yaw*np.pi/180.))*(np.pi/180.)*2.*CT*np.cos(yaw*np.pi/180.)
        self.dCt_out_dvel = dCTdvel*np.cos(yaw*np.pi/180.)**2.

        # normalize on incoming wind speed to correct coefficients for yaw
        self.unknowns['Cp_out'] = Cp_out
        self.unknowns['Ct_out'] = Ct_out

    def linearize(self, params, unknowns, resids):  # standard central differencing

        direction_id = self.direction_id

        # print 'in linearize', self.dCp_out_dyaw, self.dCp_out_dvel

        # compile Jacobian dict
        J = {}
        J['Cp_out', 'yaw%i' % direction_id] = np.eye(self.nTurbines)*self.dCp_out_dyaw
        J['Cp_out', 'velocitiesTurbines%i' % direction_id] = np.eye(self.nTurbines)*self.dCp_out_dvel
        J['Ct_out', 'yaw%i' % direction_id] = np.eye(self.nTurbines)*self.dCt_out_dyaw
        J['Ct_out', 'velocitiesTurbines%i' % direction_id] = np.eye(self.nTurbines)*self.dCt_out_dvel

        return J


class WindDirectionPower(Component):

    def __init__(self, nTurbines, direction_id=0, differentiable=True, use_rotor_components=False):

        super(WindDirectionPower, self).__init__()

        self.differentiable = differentiable
        self.nTurbines = nTurbines
        self.direction_id = direction_id
        self.use_rotor_components = use_rotor_components

        self.fd_options['form'] = 'central'
        self.fd_options['step_size'] = 1.0e-6
        self.fd_options['step_type'] = 'relative'

        if not differentiable:
            self.fd_options['force_fd'] = True
            self.fd_options['form'] = 'forward'

        self.add_param('air_density', 1.1716, units='kg/(m*m*m)', desc='air density in free stream')
        self.add_param('rotorDiameter', np.zeros(nTurbines), units='m', desc='rotor diameters of all turbine')
        self.add_param('Cp', np.zeros(nTurbines)+0.7737/0.944 * 4.0 * 1.0/3.0 * np.power((1 - 1.0/3.0), 2), desc='power coefficient for all turbines')
        self.add_param('generator_efficiency', np.zeros(nTurbines)+0.944, desc='generator efficiency of all turbines')
        self.add_param('velocitiesTurbines%i' % direction_id, np.zeros(nTurbines), units='m/s',
                       desc='effective hub velocity for each turbine')

        self.add_param('rated_power', np.ones(nTurbines)*5000., units='kW',
                       desc='rated power for each turbine', pass_by_obj=True)

        # outputs
        self.add_output('wt_power%i' % direction_id, np.zeros(nTurbines), units='kW', desc='power output of each turbine')
        # output
        self.add_output('power%i' % direction_id, 0.0, units='kW', desc='total power output of the wind farm')

    def solve_nonlinear(self, params, unknowns, resids):
        use_rotor_components = self.use_rotor_components
        direction_id = self.direction_id
        nTurbines = self.nTurbines
        velocitiesTurbines = self.params['velocitiesTurbines%i' % direction_id]
        rated_power = params['rated_power']
        air_density = params['air_density']
        rotorArea = 0.25*np.pi*np.power(params['rotorDiameter'], 2)
        Cp = params['Cp']
        generator_efficiency = params['generator_efficiency']

        wt_power = generator_efficiency*(0.5*air_density*rotorArea*Cp*np.power(velocitiesTurbines, 3))

        wt_power /= 1000.0

        # rated_velocity = np.power(1000.*rated_power/(generator_efficiency*(0.5*air_density*rotorArea*Cp)), 1./3.)
        #
        # dwt_power_dvelocitiesTurbines = np.eye(nTurbines)*generator_efficiency*(1.5*air_density*rotorArea*Cp *
        #                                                                         np.power(velocitiesTurbines, 2))
        # dwt_power_dvelocitiesTurbines /= 1000.

        if not use_rotor_components and np.any(wt_power) >= np.any(rated_power):
            for i in range(0, nTurbines):
                if wt_power[i] >= rated_power[i]:
                    wt_power[i] = rated_power[i]


        # if np.any(rated_velocity+1.) >= np.any(velocitiesTurbines) >= np.any(rated_velocity-1.) and not \
        #         use_rotor_components:
        #     for i in range(0, nTurbines):
        #         if velocitiesTurbines[i] >= rated_velocity[i]+1.:
        #             spline_start_power = generator_efficiency[i]*(0.5*air_density*rotorArea[i]*Cp[i]*np.power(rated_velocity[i]-1., 3))
        #             deriv_spline_start_power = 3.*generator_efficiency[i]*(0.5*air_density*rotorArea[i]*Cp[i]*np.power(rated_velocity[i]-1., 2))
        #             spline_end_power = generator_efficiency[i]*(0.5*air_density*rotorArea[i]*Cp[i]*np.power(rated_velocity[i]+1., 3))
        #             wt_power[i], deriv = hermite_spline(velocitiesTurbines[i], rated_velocity[i]-1.,
        #                                                                      rated_velocity[i]+1., spline_start_power,
        #                                                                      deriv_spline_start_power, spline_end_power, 0.0)
        #             dwt_power_dvelocitiesTurbines[i][i] = deriv/1000.
        #
        # if np.any(velocitiesTurbines) >= np.any(rated_velocity+1.) and not use_rotor_components:
        #     for i in range(0, nTurbines):
        #         if velocitiesTurbines[i] >= rated_velocity[i]+1.:
        #             wt_power = rated_power
        #             dwt_power_dvelocitiesTurbines[i][i] = 0.0



        # self.dwt_power_dvelocitiesTurbines = dwt_power_dvelocitiesTurbines

        power = np.sum(wt_power)

        unknowns['wt_power%i' % direction_id] = wt_power
        unknowns['power%i' % direction_id] = power

    def linearize(self, params, unknowns, resids):

        direction_id = self.direction_id
        use_rotor_components = self.use_rotor_components
        nTurbines = self.nTurbines
        velocitiesTurbines = self.params['velocitiesTurbines%i' % direction_id]
        air_density = params['air_density']
        rotorDiameter = params['rotorDiameter']
        rotorArea = 0.25*np.pi*np.power(rotorDiameter, 2)
        Cp = params['Cp']
        generator_efficiency = params['generator_efficiency']

        dwt_power_dvelocitiesTurbines = np.eye(nTurbines)*generator_efficiency*(1.5*air_density*rotorArea*Cp *
                                                                                np.power(velocitiesTurbines, 2))
        dwt_power_dCp = np.eye(nTurbines)*generator_efficiency*(0.5*air_density*rotorArea*np.power(velocitiesTurbines, 3))
        dwt_power_drotorDiameter = np.eye(nTurbines)*generator_efficiency*(0.5*air_density*(0.5*np.pi*rotorDiameter)*Cp *
                                                                           np.power(velocitiesTurbines, 3))
        # dwt_power_dvelocitiesTurbines = self.dwt_power_dvelocitiesTurbines
        dwt_power_dvelocitiesTurbines /= 1000.
        dwt_power_dCp /= 1000.
        dwt_power_drotorDiameter /= 1000.

        rated_power = params['rated_power']
        wt_power = unknowns['wt_power%i' % direction_id]
        # rated_velocity = np.power(1000.*rated_power/(generator_efficiency*(0.5*air_density*rotorArea*Cp)), 1./3.)

        # if np.any(rated_velocity+1.) >= np.any(velocitiesTurbines) >= np.any(rated_velocity-1.) and not \
        #         use_rotor_components:
        #
        #     spline_start_power = generator_efficiency*(0.5*air_density*rotorArea*Cp*np.power(rated_velocity-1., 3))
        #     deriv_spline_start_power = 3.*generator_efficiency*(0.5*air_density*rotorArea*Cp*np.power(rated_velocity-1., 2))
        #     spline_end_power = generator_efficiency*(0.5*air_density*rotorArea*Cp*np.power(rated_velocity+1., 3))
        #     wt_power, dwt_power_dvelocitiesTurbines = hermite_spline(velocitiesTurbines, rated_velocity-1.,
        #                                                              rated_velocity+1., spline_start_power,
        #                                                              deriv_spline_start_power, spline_end_power, 0.0)

        if np.any(wt_power) >= np.any(rated_power) and not use_rotor_components:
            for i in range(0, nTurbines):
                if wt_power[i] >= rated_power[i]:
                    dwt_power_dvelocitiesTurbines[i][i] = 0.0
                    dwt_power_dCp[i][i] = 0.0
                    dwt_power_drotorDiameter[i][i] = 0.0

        dpower_dvelocitiesTurbines = np.array([np.sum(dwt_power_dvelocitiesTurbines, 0)])
        dpower_dCp = np.array([np.sum(dwt_power_dCp, 0)])
        dpower_drotorDiameter = np.array([np.sum(dwt_power_drotorDiameter, 0)])

        J = {}

        J['wt_power%i' % direction_id, 'velocitiesTurbines%i' % direction_id] = dwt_power_dvelocitiesTurbines
        J['wt_power%i' % direction_id, 'Cp'] = dwt_power_dCp
        J['wt_power%i' % direction_id, 'rotorDiameter'] = dwt_power_drotorDiameter

        J['power%i' % direction_id, 'velocitiesTurbines%i' % direction_id] = dpower_dvelocitiesTurbines
        J['power%i' % direction_id, 'Cp'] = dpower_dCp
        J['power%i' % direction_id, 'rotorDiameter'] = dpower_drotorDiameter

        return J


if __name__ == "__main__":

    # top = Problem()
    #
    # root = top.root = Group()
    #
    # root.add('p1', IndepVarComp('x', np.array([1.0, 1.0])))
    # root.add('p2', IndepVarComp('y', np.array([0.75, 0.25])))
    # root.add('p', WindFarmAEP(nDirections=2))
    #
    # root.connect('p1.x', 'p.power_directions')
    # root.connect('p2.y', 'p.windrose_frequencies')
    #
    # top.setup()
    # top.run()
    #
    # # should return 8760.0
    # print(root.p.unknowns['AEP'])
    # top.check_partial_derivatives()

    # top = Problem()
    #
    # root = top.root = Group()
    #
    # root.add('p1', IndepVarComp('x', 1.0))
    # root.add('p2', IndepVarComp('y', 2.0))
    # root.add('p', MUX(nElements=2))
    #
    # root.connect('p1.x', 'p.input0')
    # root.connect('p2.y', 'p.input1')
    #
    # top.setup()
    # top.run()
    #
    # # should return 8760.0
    # print(root.p.unknowns['Array'])
    # top.check_partial_derivatives()

    # top = Problem()
    #
    # root = top.root = Group()
    #
    # root.add('p1', IndepVarComp('x', np.zeros(2)))
    # root.add('p', DeMUX(nElements=2))
    #
    # root.connect('p1.x', 'p.Array')
    #
    # top.setup()
    # top.run()
    #
    # # should return 8760.0
    # print(root.p.unknowns['output0'])
    # print(root.p.unknowns['output1'])
    # top.check_partial_derivatives()

    top = Problem()

    root = top.root = Group()

    root.add('p1', IndepVarComp('x', np.array([0, 3])))
    root.add('p2', IndepVarComp('y', np.array([1, 0])))
    root.add('p', SpacingComp(nTurbines=2))

    root.connect('p1.x', 'p.turbineX')
    root.connect('p2.y', 'p.turbineY')

    top.setup()
    top.run()

    # print(root.p.unknowns['output0'])
    # print(root.p.unknowns['output1'])
    top.check_partial_derivatives()
