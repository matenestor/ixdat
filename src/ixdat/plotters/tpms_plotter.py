from .base_mpl_plotter import MPLPlotter
from .ms_plotter import MSPlotter
from .plotting_tools import color_axis
import numpy as np


class TPMSPlotter(MPLPlotter):
    """A matplotlib plotter for TP-MS measurements."""

    def __init__(self, measurement=None):
        """Initiate the TPMSPlotter with its default Measurement to plot"""
        super().__init__()
        self.measurement = measurement
        self.ms_plotter = MSPlotter(measurement=measurement)

    def plot_measurement(
        self,
        *,
        measurement=None,
        axes=None,
        mass_list=None,
        mass_lists=None,
        mol_list=None,
        mol_lists=None,
        tspan=None,
        tspan_bg=None,
        remove_background=None,
        unit=None,
        x_unit=None,
        T_name=None,
        P_name=None,
        T_color=None,
        P_color=None,
        logplot=None,
        legend=True,
        emphasis="top",
        **kwargs,
    ):
        """Make a TP-MS plot vs time and return the axis handles.

        Allocates some tasks to MSPlotter.plot_measurement()

        Args:
            measurement (TPMSMeasurement): Defaults to the measurement to which the
                plotter is bound (self.measurement)
            axes (list of three matplotlib axes): axes[0] plots the MID data,
                axes[1] the variable given by T_str (temperature), and axes[3] the
                variable given by P_str (reactor pressure). By default three axes are
                made with axes[0] a top panel with 3/5 the area, and axes[1] and axes[3]
                are the left and right y-axes of the lower panel with 2/5 the area.
            mass_list (list of str): The names of the m/z values, eg. ["M2", ...] to
                plot. Defaults to all of them (measurement.mass_list)
            mass_lists (list of list of str): Alternately, two lists can be given for
                masses in which case one list is plotted on the left y-axis and the other
                on the right y-axis of the top panel.
            mol_list (list of str): The names of the molecules, eg. ["H2", ...] to
                plot. Defaults to all of them (measurement.mass_list)
            mol_lists (list of list of str): Alternately, two lists can be given for
                molecules in which case one list is plotted on the left y-axis and the
                other on the right y-axis of the top panel.
            tspan (iter of float): The time interval to plot, wrt measurement.tstamp
            tspan_bg (timespan): A timespan for which to assume the signal is at its
                background. The average signals during this timespan are subtracted.
                If `mass_lists` are given rather than a single `mass_list`, `tspan_bg`
                must also be two timespans - one for each axis. Default is `None` for no
                background subtraction.
            remove_background (bool): Whether otherwise to subtract pre-determined
                background signals if available. Defaults to (not logplot)
            unit (str): the unit for the MS data. Defaults to "A" for Ampere
            T_name (str): The name of the value to plot on the lower left y-axis.
                Defaults to the name of the series `measurement.temperature`
            P_name (str): The name of the value to plot on the lower right y-axis.
                Defaults to the name of the series `measurement.pressure`
            T_color (str): The color to plot the variable given by 'T_str'
            P_color (str): The color to plot the variable given by 'P_str'
            logplot (bool): Whether to plot the MS data on a log scale (default True
                unless mass_lists are given)
            legend (bool): Whether to use a legend for the MS data (default True)
            emphasis (str or None): "top" for bigger top panel, "bottom" for bigger
                bottom panel, None for equal-sized panels
            kwargs (dict): Additional kwargs go to all calls of matplotlib's plot()

        Returns:
            list of Axes: (top_left, bottom_left, top_right, bottom_right) where:
                axes[0] is top_left is MS data;
                axes[1] is bottom_left is temperature;
                axes[2] is top_right is additional MS data if left and right mass_lists
                    or mol_lists were plotted (otherwise axes[2] is None); and
                axes[3] is bottom_right is pressure.
        """

        measurement = measurement or self.measurement

        T_name = T_name or measurement.T_name
        P_name = P_name or measurement.P_name

        TP_lists = [[T_name], [P_name]]
        TP_list = None

        if logplot is None:
            logplot = not mol_lists and not mass_lists

        if not axes:
            if emphasis == "single plot":
                ax = self.new_ax()
                ax2 = ax.twinx()
                axes = [ax, ax2]
                TP_list = [T_name]
                TP_lists = None
            else:
                axes = self.new_two_panel_axes(
                    n_bottom=2,
                    n_top=(2 if (mass_lists or mol_lists) else 1),
                    emphasis=emphasis,
                )

                TP_lists = [[T_name], [P_name]]
                TP_list = None

        if (
            mass_list
            or mass_lists
            or mol_list
            or mol_lists
            or hasattr(measurement, "mass_list")
        ):
            # then we have MS data!
            self.ms_plotter.plot_measurement(
                measurement=measurement,
                axes=[axes[0], axes[2]] if (mass_lists or mol_lists) else [axes[0]],
                tspan=tspan,
                tspan_bg=tspan_bg,
                remove_background=remove_background,
                mass_list=mass_list,
                mass_lists=mass_lists,
                mol_list=mol_list,
                mol_lists=mol_lists,
                unit=unit,
                x_unit=x_unit,
                logplot=logplot,
                legend=legend,
                **kwargs,
            )

        # Then we have meta data plottet using MSPlotter
        self.ms_plotter.plot_measurement(
            measurement=measurement,
            axes=[axes[1], axes[3]] if TP_lists else [axes[1]],
            tspan=tspan,
            mass_list=TP_list,
            mass_lists=TP_lists,
            unit=None,
            x_unit=x_unit,
            logplot=False,
        )

        # Overwrite colours if colours is manually set
        axes[1].set_ylabel(T_name)
        if not T_color:
            T_color = axes[1].get_lines()[0].get_color()
        else:
            axes[1].get_lines()[0].set_color(T_color)
        color_axis(axes[1], T_color)

        if TP_lists:
            axes[3].set_ylabel(P_name)
            if not P_color:
                P_color = axes[3].get_lines()[0].get_color()
            else:
                axes[3].get_lines()[0].set_color(P_color)
            color_axis(axes[3], P_color)

        return axes

    def plot_arrhenius(
        self,
        *,
        T_name,
        measurement=None,
        ax=None,
        axes=None,
        mass_list=None,
        mass_lists=None,
        mol_list=None,
        mol_lists=None,
        tspan=None,
        tspan_bg=None,
        remove_background=None,
        unit=None,
        arrh_color="r",
        logplot=None,
        legend=True,
        **kwargs,
    ):
        if logplot is None:
            logplot = not mol_lists and not mass_lists

        measurement = measurement or self.measurement

        if (
            mass_list
            or mass_lists
            or mol_list
            or mol_lists
            or hasattr(measurement, "mass_list")
        ):
            # then we have MS data!

            axs = self.ms_plotter.plot_vs(
                measurement=measurement,
                ax=ax,
                axes=axes,
                mass_list=mass_list,
                mass_lists=mass_lists,
                mol_list=mol_list,
                mol_lists=mol_lists,
                tspan=tspan,
                tspan_bg=tspan_bg,
                remove_background=remove_background,
                unit=unit,
                x_name=T_name,
                logplot=logplot,
                legend=legend,
                x_inverse=True,
                **kwargs,
            )

        return axs

    def plot_single(
        self,
        *,
        measurement=None,
        ax=None,
        axes=None,
        mass_list=None,
        mass_lists=None,
        mol_list=None,
        mol_lists=None,
        tspan=None,
        tspan_bg=None,
        remove_background=None,
        unit=None,
        x_unit=None,
        T_name=None,
        T_color=None,
        logplot=None,
        legend=True,
        emphasis="single plot",
        **kwargs,
    ):

        axes = self.ms_plotter.plot_measurement(
            measurement=measurement,
            axes=axes,
            mass_list=mass_list,
            mass_lists=mass_lists,
            mol_list=mol_list,
            mol_lists=mol_lists,
            tspan=tspan,
            tspan_bg=tspan_bg,
            remove_background=remove_background,
            unit=unit,
            x_unit=x_unit,
            T_name=T_name,
            T_color=T_color,
            logplot=logplot,
            legend=legend,
            emphasis=emphasis,
            **kwargs,
        )

        return axes


class SpectroTPMSPlotter(MPLPlotter):
    def __init__(self, measurement=None):
        """Initiate the Spectro-TPMSPlotter with its default Measurement to plot"""
        super().__init__()
        self.measurement = measurement
        self.tpms_plotter = TPMSPlotter(measurement=measurement)

    def plot_measurement(
        self,
        *,
        measurement=None,
        axes=None,
        mass_list=None,
        mass_lists=None,
        mol_list=None,
        mol_lists=None,
        tspan=None,
        tspan_bg=None,
        remove_background=None,
        unit=None,
        T_name=None,
        P_name=None,
        T_color="k",
        P_color="r",
        logplot=None,
        legend=True,
        xspan=None,
        cmap_name="inferno",
        make_colorbar=False,
        aspect=1.25,
        max_threshold=None,
        min_threshold=None,
        scanning_mask=None,
        _sort_indicies=None,
        vmin=None,
        vmax=None,
        emphasis="middle",
        **kwargs,
    ):
        """Make a spectro TP-MS plot vs time and return the axis handles.

        Allocates some tasks to TPMSPlotter.plot_measurement()

        Args:
            measurement (SpectroReactorMeasurement): Defaults to the measurement to which
                the plotter is bound (self.measurement)
            axes (list of four matplotlib axes): axes[0] plots the spectral, axes[1] MS,
                axes[2] the variable given by T_str (temperature), and axes[4] the
                variable given by P_str (reactor pressure). By default four axes are made
                with axes[0] a top panel, axes[1] a middle panel, axes[2] and axes[4]
                the left and right yaxes of the bottom panel
            mass_list (list of str): The names of the m/z values, eg. ["M2", ...] to
                plot. Defaults to all of them (measurement.mass_list)
            mass_lists (list of list of str): Alternately, two lists can be given for
                masses in which case one list is plotted on the left y-axis and the other
                on the right y-axis of the top panel.
            mol_list (list of str): The names of the molecules, eg. ["H2", ...] to
                plot. Defaults to all of them (measurement.mass_list)
            mol_lists (list of list of str): Alternately, two lists can be given for
                molecules in which case one list is plotted on the left y-axis and the
                other on the right y-axis of the top panel.
            tspan (iter of float): The time interval to plot, wrt measurement.tstamp
            tspan_bg (timespan): A timespan for which to assume the signal is at its
                background. The average signals during this timespan are subtracted.
                If `mass_lists` are given rather than a single `mass_list`, `tspan_bg`
                must also be two timespans - one for each axis. Default is `None` for no
                background subtraction.
            remove_background (bool): Whether otherwise to subtract pre-determined
                background signals if available. Defaults to (not logplot)
            unit (str): the unit for the MS data. Defaults to "A" for Ampere
            T_name (str): The name of the value to plot on the lower left y-axis.
                Defaults to the name of the series `measurement.temperature`
            P_name (str): The name of the value to plot on the lower right y-axis.
                Defaults to the name of the series `measurement.pressure`
            T_color (str): The color to plot the variable given by 'T_str'
            P_color (str): The color to plot the variable given by 'P_str'
            logplot (bool): Whether to plot the MS data on a log scale (default True
                unless mass_lists are given)
            legend (bool): Whether to use a legend for the MID data (default True)
            xspan (iterable): The span of the spectral data to plot
            cmap_name (str): The name of the colormap to use. Defaults to "inferno", see
                https://matplotlib.org/3.5.0/tutorials/colors/colormaps.html#sequential
            make_colorbar (bool): Whether to make a colorbar.
                FIXME: colorbar at present mis-alignes axes
            aspect (float): aspect ratio. Defaults to 1.25 times taller than wide.
            max_threshold (float): Set maximum value in scanning data and set to zero if
                data is above.
            min_threshold (float): Set minimum value in scanning data and set to zero if
                data is below.
            scanning_mask (boolean list): List of booleans to include/ exclude specfic
                data in scanning plot (specific masses that are monitored otherwise)
            _sort_indicies (list): list of floats to sort data. Defaults low to high.
            vmin (float): Value used to shift colours in the colorbar to lower values
            vmax (float): Value to shift colours in the colorbar to higher values
            kwargs (dict): Additional kwargs go to all calls of matplotlib's plot()

        Returns:
            list of Axes: (top, mid_left, bottom_left, mid_right, bottom_right) where:
                axes[0] is top is MS spectral data
                axes[1] is mid_left is Mass ID data;
                axes[2] is bottom_left is temperature;
                axes[3] is mid_right is additional MS data if left and right mass_lists
                    or mol_lists were plotted (otherwise axes[3] is None); and
                axes[4] is bottom_right is pressure.
        """
        measurement = measurement or self.measurement

        if not axes:
            axes = self.new_three_panel_axes(
                n_top=1, n_middle=(2 if (mass_lists or mol_lists) else 1), n_bottom=2
            )

        measurement.spectrum_series.heat_plot(
            ax=axes[0],
            tspan=tspan,
            xspan=xspan,
            cmap_name=cmap_name,
            make_colorbar=make_colorbar,
            max_threshold=max_threshold,
            min_threshold=min_threshold,
            scanning_mask=scanning_mask,
            _sort_indicies=_sort_indicies,
            vmin=vmin,
            vmax=vmax,
        )

        self.tpms_plotter.plot_measurement(
            measurement=measurement,
            axes=[axes[1], axes[2], axes[4], axes[5]],
            tspan=tspan,
            tspan_bg=tspan_bg,
            remove_background=remove_background,
            mass_list=mass_list,
            mass_lists=mass_lists,
            mol_list=mol_list,
            mol_lists=mol_lists,
            unit=unit,
            logplot=logplot,
            legend=legend,
            T_name=T_name,
            P_name=P_name,
            T_color=T_color,
            P_color=P_color,
            **kwargs,
        )

        axes[0].set_xlim(axes[1].get_xlim())

        fig = axes[0].get_figure()
        fig.set_figheight(fig.get_figwidth() * aspect)

        return axes

    def plot_measurement_vs(
        self,
        *,
        x_name,
        measurement=None,
        axes=None,
        mass_list=None,
        mass_lists=None,
        mol_list=None,
        mol_lists=None,
        tspan=None,
        tspan_bg=None,
        remove_background=None,
        unit=None,
        logplot=True,
        legend=True,
        xspan=None,
        cmap_name="inferno",
        make_colorbar=False,
        emphasis="top",
        ms_data="top",
        max_threshold=None,
        min_threshold=None,
        scanning_mask=None,
        _sort_indicies=None,
        **kwargs,
    ):

        if logplot is None:
            logplot = not mol_lists and not mass_lists

        if not axes:
            if ms_data == "top":
                n_bottom = 1
                n_top = 2 if (mass_lists or mol_lists) else 1
                ms_axes = 0
                ms_spec_axes = 1
            else:
                n_top = 1
                n_bottom = 2 if (mass_lists or mol_lists) else 1
                ms_axes = 1
                ms_spec_axes = 0

            axes = self.new_two_panel_axes(
                n_bottom=n_bottom,
                n_top=n_top,
                emphasis=emphasis,
            )

        measurement = measurement or self.measurement

        if (
            mass_list
            or mass_lists
            or mol_list
            or mol_lists
            or hasattr(measurement, "mass_list")
        ):
            # then we have MS data!
            self.tpms_plotter.ms_plotter.plot_vs(
                x_name=x_name,
                measurement=measurement,
                axes=[axes[ms_axes], axes[2]]
                if (mass_lists or mol_lists)
                else [axes[ms_axes]],
                tspan=tspan,
                tspan_bg=tspan_bg,
                remove_background=remove_background,
                mass_list=mass_list,
                mass_lists=mass_lists,
                mol_list=mol_list,
                mol_lists=mol_lists,
                unit=unit,
                logplot=logplot,
                legend=legend,
                **kwargs,
            )

        _tseries = measurement.spectrum_series.field.axes_series[0]
        _v = measurement.grab_for_t(item=x_name, t=_tseries.t)
        if not _sort_indicies:
            _sort_indicies = np.argsort(_v)

        measurement.spectrum_series.heat_plot(
            ax=axes[ms_spec_axes],
            t=_v[_sort_indicies],
            tspan=tspan,
            xspan=xspan,
            t_name=x_name,
            cmap_name=cmap_name,
            make_colorbar=make_colorbar,
            max_threshold=max_threshold,
            min_threshold=min_threshold,
            scanning_mask=scanning_mask,
            _sort_indicies=_sort_indicies,
            **kwargs,
        )

        return axes
