"""Module for representation and analysis of EC-MS measurements"""
import numpy as np
import warnings
from scipy.optimize import minimize
from numpy.fft import fft, ifft, ifftshift, fftfreq  # noqa
from ..constants import FARADAY_CONSTANT
from .ec import ECMeasurement, ECCalibration
from .ms import MSMeasurement, MSCalResult, MSCalibration, _with_siq_quantifier
from .cv import CyclicVoltammogram
from .deconvolution import ECMSImpulseResponse
from ..exceptions import QuantificationError
from ..exporters.ecms_exporter import ECMSExporter
from ..plotters.ecms_plotter import ECMSPlotter
from ..plotters.ms_plotter import STANDARD_COLORS
from ..config import plugins


class ECMSMeasurement(ECMeasurement, MSMeasurement):
    """Class for raw EC-MS functionality. Parents: ECMeasurement and MSMeasurement"""

    extra_column_attrs = {
        "ecms_meaurements": {"ec_technique", "tspan_bg"},
    }
    # FIXME: It would be much more elegant if this carried over automatically from
    #  *both* parents, by appending the table columns...
    #  We'll see how the problem changes with the metaprogramming work.

    default_plotter = ECMSPlotter
    default_exporter = ECMSExporter

    def __init__(self, **kwargs):
        """FIXME: Passing the right key-word arguments on is a mess"""
        ec_kwargs = {
            k: v for k, v in kwargs.items() if k in ECMeasurement.get_all_column_attrs()
        }
        ms_kwargs = {
            k: v for k, v in kwargs.items() if k in MSMeasurement.get_all_column_attrs()
        }
        # ms_kwargs["ms_calibration"] = self.ms_calibration  # FIXME: This is a mess.
        # FIXME: I think the lines below could be avoided with a PlaceHolderObject that
        #  works together with MemoryBackend
        if "series_list" in kwargs:
            ec_kwargs.update(series_list=kwargs["series_list"])
            ms_kwargs.update(series_list=kwargs["series_list"])
        if "component_measurements" in kwargs:
            ec_kwargs.update(component_measurements=kwargs["component_measurements"])
            ms_kwargs.update(component_measurements=kwargs["component_measurements"])
        if "calibration_list" in kwargs:
            ec_kwargs.update(calibration_list=kwargs["calibration_list"])
            ms_kwargs.update(calibration_list=kwargs["calibration_list"])
        ECMeasurement.__init__(self, **ec_kwargs)
        MSMeasurement.__init__(self, **ms_kwargs)
        self._ec_plotter = None
        self._ms_plotter = None

    @property
    def ec_plotter(self):
        """A plotter for just plotting the ec data"""
        return self.plotter.ec_plotter  # the ECPlotter of the measurement's ECMSPlotter

    @property
    def ms_plotter(self):
        """A plotter for just plotting the ms data"""
        return self.plotter.ms_plotter  # the MSPlotter of the measurement's ECMSPlotter

    @classmethod
    def from_dict(cls, obj_as_dict):
        """Initiate an ECMSMeasurement from a dictionary representation.

        This unpacks the ECMSCalibration from its own nested dictionary
        TODO: Figure out a way for that to happen automatically.
        """

        if "calibration" in obj_as_dict:
            if isinstance(obj_as_dict["calibration"], dict):
                # FIXME: This is a mess
                obj_as_dict["calibration"] = ECMSCalibration.from_dict(
                    obj_as_dict["calibration"]
                )
        obj = super(ECMSMeasurement, cls).from_dict(obj_as_dict)
        return obj

    @property
    def tspan(self):
        """The tspan of an MS measurement is the tspan of its potential data"""
        return [self.t[0], self.t[-1]]

    @_with_siq_quantifier
    def as_cv(self):
        self_as_dict = self.as_dict()

        # FIXME: The following lines are only necessary because
        #  PlaceHolderObject.get_object isn't able to find things in the MemoryBackend
        del self_as_dict["s_ids"]
        self_as_dict["series_list"] = self.series_list

        ecms_cv = ECMSCyclicVoltammogram.from_dict(self_as_dict)

        return ecms_cv

    def ecms_calibration(self, mol, mass, n_el, tspan, tspan_bg=None):
        """Calibrate for mol and mass based on one period of steady electrolysis

        Args:
            mol (str): Name of the molecule to calibrate
            mass (str): Name of the mass at which to calibrate
            n_el (str): Number of electrons passed per molecule produced (remember the
                sign! e.g. +4 for O2 by OER and -2 for H2 by HER)
            tspan (tspan): The timespan of steady electrolysis
            tspan_bg (tspan): The time to use as a background

        Return MSCalResult: The result of the ecms_calibration
        """
        if plugins.use_siq:
            warnings.warn(
                "spectro_inlets_quantification is active but you are using the native "
                "ixdat version of `ECMSMeasurement.ecms_calibration`"
            )
        Y = self.integrate_signal(mass, tspan=tspan, tspan_bg=tspan_bg)
        Q = self.integrate("raw_current", tspan=tspan) * 1e-3
        n = Q / (n_el * FARADAY_CONSTANT)
        F = Y / n
        cal = MSCalResult(
            name=f"{mol}@{mass}",
            mol=mol,
            mass=mass,
            cal_type="ecms_calibration",
            F=F,
        )
        return cal

    def ecms_calibration_curve(
        self,
        mol,
        mass,
        n_el,
        tspan_list=None,
        selector_name=None,
        selector_list=None,
        t_steady_pulse=None,
        tspan_bg=None,
        force_through_zero=False,
        ax="new",
        axes_measurement=None,
        axes_measurement_J_name="raw_current",
        return_ax=False,
    ):
        """Fit mol's sensitivity at mass based on steady periods of EC production.

        Args:
            mol (str): Name of the molecule to calibrate
            mass (str): Name of the mass at which to calibrate
            n_el (str): Number of electrons passed per molecule produced (remember the
                sign! e.g. +4 for O2 by OER and -2 for H2 by HER)
            tspan_list (list of tspan): The timespans of steady electrolysis
            selector_name (str): Name of selector which identifies the periods
                of steady electrolysis for automatic selection of timespans of steady
                electrolysis. E.g. "selector" or "Ns" for biologic EC data
            selector_list (list): List of values for selector_name for automatic
                selection of timespans of steady electrolysis
            t_steady_pulse (float): Length of steady electrolysis for each segment
                given by selector_list. Defaults to None = entire length of segment
            tspan_bg (tspan): The time to use as a background
            force_through_zero (boolean): Whether to force the calibration curve through
                zero. This can be done when confident in the background subtraction.
            ax (Axis): The axis on which to plot the ms_calibration curve result.
                Defaults to a new axis.
            axes_measurement (list of Axes): The EC-MS plot axes to highlight the
                ms_calibration on. Defaults to None. These axes are not returned.
            axes_measurement_J_name (str): The J_name used in the axis passed
                to axes_measurement. Must be passed manually as the axis does not "know"
                its J_name. Defaults to "raw_current". IMPORTANT: the method still uses
                "raw_current" to calculate the sensitivity factor, this J_name is only
                used for plotting.
            return_ax (bool): Whether to return the axis on which the calibration curve
                is plotted together with the MSCalResult. Defaults to False.

        Return MSCalResult(, Axis): The result of the ms_calibration (and calibration
            curve axis if requested) based on integration of selected time periods.
        """
        if plugins.use_siq:
            warnings.warn(
                "spectro_inlets_quantification is active but you are using the native "
                "ixdat version of `ECMSMeasurement.ecms_calibration_curve`"
            )
        return self._ecms_calibration_curve(
            mol=mol,
            mass=mass,
            n_el=n_el,
            tspan_list=tspan_list,
            selector_name=selector_name,
            selector_list=selector_list,
            t_steady_pulse=t_steady_pulse,
            tspan_bg=tspan_bg,
            force_through_zero=force_through_zero,
            ax=ax,
            axes_measurement=axes_measurement,
            axes_measurement_J_name=axes_measurement_J_name,
            return_ax=return_ax,
        )

    def _ecms_calibration_curve(
        self,
        mol,
        mass,
        n_el,
        tspan_list=None,
        selector_name=None,
        selector_list=None,
        t_steady_pulse=None,
        tspan_bg=None,
        force_through_zero=False,
        ax="new",
        axes_measurement=None,
        axes_measurement_J_name="raw_current",
        return_ax=False,
    ):
        """Helper function. See ecms_calibration_curve for argument descriptions."""

        axis_ms = axes_measurement[0] if axes_measurement else None
        axis_current = axes_measurement[3] if axes_measurement else None
        Y_list = []
        n_list = []
        if not tspan_list:
            tspan_list = self._get_tspan_list(
                selector_list, selector_name, t_steady_pulse
            )
        for tspan in tspan_list:
            Y = self.integrate_signal(mass, tspan=tspan, tspan_bg=tspan_bg, ax=axis_ms)
            # FIXME: plotting current by giving integrate() an axis doesn't work great.
            if (
                axes_measurement
            ):  # FIXME: need to run twice, once to plot, once to calculate Q
                self.integrate(axes_measurement_J_name, tspan=tspan, ax=axis_current)
            Q = self.integrate("raw_current", tspan=tspan)
            Q *= 1e-3  # mC --> [C]
            n = Q / (n_el * FARADAY_CONSTANT)
            Y_list.append(Y)
            n_list.append(n)
        n_vec = np.array(n_list)
        Y_vec = np.array(Y_list)
        n_fit = np.array([0, max(n_vec)])
        if force_through_zero:

            def rms_error(F_guess):
                return np.mean((Y_vec - F_guess * n_vec) ** 2)

            F_guess_0 = np.sum(Y_vec) / np.sum(n_vec)
            res = minimize(rms_error, F_guess_0)
            F = res.x[0]
            Y_fit = n_fit * F
        else:
            pfit = np.polyfit(n_vec, Y_vec, deg=1)
            F = pfit[0]
            Y_fit = n_fit * pfit[0] + pfit[1]

        if ax:
            color = STANDARD_COLORS[mass]
            if ax == "new":
                ax = self.plotter.new_ax()
                ax.set_xlabel("amount produced / [nmol]")
                ax.set_ylabel("integrated signal / [nC]")
            ax.plot(n_vec * 1e9, Y_vec * 1e9, "o", color=color)
            ax.plot(n_fit * 1e9, Y_fit * 1e9, "--", color=color)

        cal = MSCalResult(
            name=f"{mol}@{mass}",
            mol=mol,
            mass=mass,
            cal_type="ecms_calibration_curve",
            F=F,
        )

        if return_ax:
            return cal, ax
        return cal

    def _get_tspan_list(
        self,
        selector_list,
        selector_name=None,
        t_steady_pulse=None,
    ):
        """
        Generate a t_span list from input of selectors.

        Args:
            selector_list (list of selector): selector numbers that define the
                                            tspans over which data should be integrated
            selector_name (str): name of selector that will be used to determine sections
                                of data. Will refer to data['selector'] by default.
                                selector_name cannot contain a space character due to
                                limitations of self.select_values().
            t_steady_pulse (float): length of steady state pulse period to integrate
                                    (will choose the last x seconds of the period).
                                    Defaults to None: uses entire steady state pulse

        Returns tspan_list(list of tspan)
        """
        selector_name = selector_name or "selector"
        t_idx = -1
        if not t_steady_pulse:
            t_idx = 0
            t_steady_pulse = 0
        tspan_list = [
            [
                self.select_values(**{selector_name: selector_value}).grab("t")[0][t_idx]
                - t_steady_pulse,
                self.select_values(**{selector_name: selector_value}).grab("t")[0][-1],
            ]
            for selector_value in selector_list
        ]
        print("Following tspans were selected for calibration: " + str(tspan_list))
        return tspan_list

    def siq_ecms_calibration(self, mol, mass, n_el, tspan, tspan_bg=None):
        """Calibrate for mol and mass based on one period of steady electrolysis

        Use `spectro_inlets_quantification` package.
        Args:
            mol (str): Name of the molecule to calibrate
            mass (str): Name of the mass at which to calibrate
            n_el (str): Number of electrons passed per molecule produced (remember the
                sign! e.g. +4 for O2 by OER and -2 for H2 by HER)
            tspan (tspan): The timespan of steady electrolysis
            tspan_bg (tspan): The time to use as a background

        Return siq.CalPoint: The result of the ecms_calibration
        """
        if not plugins.use_siq:
            raise QuantificationError(
                "`ECMSMeasurement.siq_ecms_calibration` only works when using "
                "`spectro_inlets_quantification`"
                "(`ixdat.options.activate_siq()`). "
                "For native ixdat MS quantification, use `ecms_calibration`"
                "instead."
            )
        Y = self.integrate_signal(mass, tspan=tspan, tspan_bg=tspan_bg)
        Q = self.integrate("raw_current", tspan=tspan) * 1e-3
        n = Q / (n_el * FARADAY_CONSTANT)
        F = Y / n
        cal = plugins.siq.CalPoint(
            name=f"{mol}@{mass}",
            mol=mol,
            mass=mass,
            F_type="ecms_calibration",
            F=F,
        )
        return cal

    def siq_ecms_calibration_curve(
        self,
        mol,
        mass,
        n_el,
        tspan_list=None,
        selector_name=None,
        selector_list=None,
        t_steady_pulse=None,
        tspan_bg=None,
        force_through_zero=False,
        ax="new",
        axes_measurement=None,
        axes_measurement_J_name="raw_current",
        return_ax=False,
    ):
        """Fit mol's sensitivity at mass based on steady periods of EC production.

        Use `spectro_inlets_quantification`.

        Args:
            mol (str): Name of the molecule to calibrate
            mass (str): Name of the mass at which to calibrate
            n_el (str): Number of electrons passed per molecule produced (remember the
                sign! e.g. +4 for O2 by OER and -2 for H2 by HER)
            tspan_list (list of tspan): The timespans of steady electrolysis
            selector_name (str): Name of selector which identifies the periods
                of steady electrolysis for automatic selection of timespans of steady
                electrolysis. E.g. "selector" or "Ns" for biologic EC data
            selector_list (list): List of values for selector_name for automatic
                selection of timespans of steady electrolysis
            t_steady_pulse (float): Length of steady electrolysis for each segment
                given by selector_list. Defaults to None = entire length of segment
            tspan_bg (tspan): The time to use as a background
            force_through_zero (boolean): Whether to force the calibration curve through
                zero. This can be done when confident in the background subtraction.
            ax (Axis): The axis on which to plot the ms_calibration curve result.
                Defaults to a new axis.
            axes_measurement (list of Axes): The EC-MS plot axes to highlight the
                ms_calibration on. Defaults to None. These axes are not returned.
            axes_measurement_J_name (str): The J_name used in the axis passed
                to axes_measurement. Must be passed manually as the axis does not "know"
                its J_name. Defaults to "raw_current". IMPORTANT: the method still uses
                "raw_current" to calculate the sensitivity factor, this J_name is only
                used for plotting.
            return_ax (bool): Whether to return the axis on which the calibration curve
                is plotted together with the MSCalResult. Defaults to False.

        Return MSCalResult(, Axis): The result of the ms_calibration (and calibration
            curve axis if requested) based on integration of selected time periods.
        """
        if not plugins.use_siq:
            raise QuantificationError(
                "`ECMSMeasurement.siq_ecms_calibration_curve` only works when using "
                "`spectro_inlets_quantification`"
                "(`ixdat.options.activate_siq()`). "
                "For native ixdat MS quantification, use `ecms_calibration_curve`"
                "instead."
            )
        ms_cal_result, ax = self._ecms_calibration_curve(
            mol=mol,
            mass=mass,
            n_el=n_el,
            tspan_list=tspan_list,
            selector_name=selector_name,
            selector_list=selector_list,
            t_steady_pulse=t_steady_pulse,
            tspan_bg=tspan_bg,
            force_through_zero=force_through_zero,
            ax=ax,
            axes_measurement=axes_measurement,
            axes_measurement_J_name=axes_measurement_J_name,
            return_ax=True,
        )
        cal = ms_cal_result.to_siq()
        if return_ax:
            return cal, ax
        else:
            return cal
        
    # DECONVOLUTION METHODS BELOW
    def grab_deconvoluted_current(
        self, mol, impulse_response, tspan=None, tspan_bg=None, snr=10
        ):
        """Return the deconvoluted partial current for a given signal using the
        algorithm developed by Krempl et al. https://pubs.acs.org/doi/abs/10.1021/acs.analchem.1c00110
        
        Note, this actually doesnt need the EC data - it is calculated
        from calibrated MS data. It is only meaningful for ECMS measurements 
        at the moment, justifying placement here.

        Args:
            mol (str): Name of molecule for which deconvolution is to
                be carried out.
            impulse_response (ECMSImpulseResponse): Kernel object which contains the mass transport
                parameters
            tspan (list): Timespan for which the partial current is returned.
            tspan_bg (list): Timespan that corresponds to the background signal.
            snr (int): signal-to-noise ratio used for Wiener deconvolution.
        """
        # TODO: comments in this method so someone can tell what's going on!
        
        # grab the calibrated data
        t_sig, v_sig = self.grab_flux(mol, tspan=tspan, tspan_bg=tspan_bg)        
        # calculate the impulse response
        signal_response = impulse_response.model_impulse_response_from_params(
        dt=t_sig[1] - t_sig[0], duration=t_sig[-1] - t_sig[0]
        )
        # this seems quite inefficient, to re-calculate the impulse response every time?
        # TODO: store this somehow?
        kernel = np.hstack((signal_response[1], np.zeros(len(v_sig) - len(signal_response[1])))) # adds an series of zeros to the array
        H = fft(kernel)
        # TODO: store this as well.
        partial_current = np.real(
            ifft(fft(v_sig) * np.conj(H) / (H * np.conj(H) + (1 / snr) ** 2))
        )
        partial_current = partial_current * sum(kernel) # what does this do????
        return t_sig, partial_current

    def extract_impulse_response(self, mol, tspan=None, tspan_bg=None):
        """Extracts an ECMSImpulseResponse object from a measurement using the
        algorithm developed by Krempl et al. https://pubs.acs.org/doi/abs/10.1021/acs.analchem.1c00110
        
        # TODO: add some option of plotting the impulse response together with the data
        # TODO: re-add a possibility to choose cut-off potentials rather
        than having to specify the tspan to make the existance of this method more meaningful, right now it
        just returns an array of the calibrated signal of mol normalized to the peak area
        Args:
            mol (str): Molecule from which the impulse response is to be extracted.
            tspan(list): Timespan over which which the impulse response is
                extracted.
            tspan_bg (list): Timespan that corresponds to the background signal.
        """
        # grab the calibrated data
        impulse_response = ECMSImpulseResponse(mol=mol, data=self).calc_impulse_response_from_data(tspan=tspan, tspan_bg=tspan_bg)
        return impulse_response


class ECMSCyclicVoltammogram(CyclicVoltammogram, ECMSMeasurement):
    """Class for raw EC-MS functionality. Parents: CyclicVoltammogram, ECMSMeasurement"""


class ECMSCalibration(ECCalibration, MSCalibration):
    """Class for calibrations useful for ECMSMeasurements"""

    extra_column_attrs = {
        "ecms_calibrations": {"date", "setup", "RE_vs_RHE", "A_el", "L"}
    }
    # FIXME: The above should be covered by the parent classes. Needs metaprogramming!
    # NOTE: technique, name, and tstamp in column_attrs are inherited from Calibration
    # NOTE: ms_results_ids in extra_linkers is inherited from MSCalibration.
    # NOTE: signal_bgs is left out

    def __init__(
        self,
        name=None,
        date=None,
        tstamp=None,
        setup=None,
        ms_cal_results=None,
        signal_bgs=None,
        RE_vs_RHE=None,
        A_el=None,
        R_Ohm=None,
        L=None,
        technique="EC-MS",
    ):
        """
        Args:
            name (str): Name of the ms_calibration
            date (str): Date of the ms_calibration
            setup (str): Name of the setup where the ms_calibration is made
            ms_cal_results (list of MSCalResult): The mass spec calibrations
            RE_vs_RHE (float): the RE potential in [V]
            A_el (float): The geometric electrode area in [cm^2]
            R_Ohm (float): The Ohmic drop in [Ohm]
            L (float): The working distance in [m]
        """
        ECCalibration.__init__(
            self,
            A_el=A_el,
            RE_vs_RHE=RE_vs_RHE,
            R_Ohm=R_Ohm,
        )
        MSCalibration.__init__(
            self,
            name=name,
            date=date,
            tstamp=tstamp,
            setup=setup,
            ms_cal_results=ms_cal_results,
            signal_bgs=signal_bgs,
        )
        self.technique = technique
        self.L = L

    def calibrate_series(self, key, measurement=None):
        measurement = measurement or self.measurement
        try_1 = ECCalibration.calibrate_series(self, key, measurement)
        if try_1:
            return try_1
        try_2 = MSCalibration.calibrate_series(self, key, measurement)
        if try_2:
            return try_2
