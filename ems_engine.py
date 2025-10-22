"""
EMS Engine - Backend computation engine for EMS simulation
Based on the Penang project implementation with PV Inverter capacity limit
"""

import pandas as pd
import numpy as np
from datetime import datetime
from ems_controller_penang_optimized import AdvancedEMSController


class TimeOfUseController:
    """Schedule-based Time-of-Use controller for BESS operations."""

    def __init__(
        self,
        *,
        max_power: float,
        battery_capacity: float,
        charge_window: dict,
        discharge_window: dict,
        min_soe: float = 15.0,
        max_soe: float = 90.0,
        roundtrip_efficiency: float = 0.90,
    ):
        self.max_power = max(0.0, float(max_power))
        self.battery_capacity = max(0.0, float(battery_capacity))
        self.charge_window = self._normalize_window(charge_window)
        self.discharge_window = self._normalize_window(discharge_window)
        self.soe_min = max(0.0, min(float(min_soe), 100.0))
        self.soe_max = max(self.soe_min, min(float(max_soe), 100.0))
        self.roundtrip_efficiency = max(0.10, min(roundtrip_efficiency, 1.0))
        self.interval_hours = 5 / 60  # Simulation granularity (5 minutes)

        # Battery health tracking (simplified)
        self.current_soh = 100.0
        self.actual_capacity_mwh = self.battery_capacity
        self.total_cycles = 0.0
        self.total_throughput_mwh = 0.0
        self.estimated_cycles = 4000.0

    @staticmethod
    def _normalize_window(window: dict) -> dict:
        start = float(window.get('start_hour', 0.0) or 0.0) % 24
        end = float(window.get('end_hour', 0.0) or 0.0) % 24
        return {'start_hour': start, 'end_hour': end}

    @staticmethod
    def _to_decimal_hour(current_time) -> float:
        return current_time.hour + current_time.minute / 60.0 + current_time.second / 3600.0

    def _in_window(self, current_time, window: dict) -> bool:
        current_hour = self._to_decimal_hour(current_time)
        start = window['start_hour']
        end = window['end_hour']
        if abs(start - end) < 1e-6:
            return False  # Empty window
        if start <= end:
            return start <= current_hour < end
        return current_hour >= start or current_hour < end

    def is_priority_charge_period(self, current_time) -> bool:
        return self._in_window(current_time, self.charge_window)

    def is_constrained_charge_period(self, current_time) -> bool:
        return False

    def is_discharge_period(self, current_time) -> bool:
        return self._in_window(current_time, self.discharge_window)

    def control_decision(self, soe, net_load, current_time, load=None, pv_power=None) -> float:
        """
        Returns discharge power in kW (positive means discharge, negative means charge).
        """
        if self.battery_capacity <= 0 or self.max_power <= 0:
            return 0.0

        # Discharge takes precedence over charging when both windows overlap
        if self.is_discharge_period(current_time) and soe > self.soe_min:
            available_delta = max(0.0, soe - self.soe_min)
            max_by_soe = (
                available_delta / 100
                * self.battery_capacity
                * 1000
                * self.roundtrip_efficiency
                / self.interval_hours
            )
            discharge_power = min(self.max_power, max_by_soe)
            if discharge_power <= 0:
                return 0.0
            return discharge_power

        if self.is_priority_charge_period(current_time) and soe < self.soe_max:
            missing_delta = max(0.0, self.soe_max - soe)
            max_by_soe = (
                missing_delta / 100
                * self.battery_capacity
                * 1000
                / (self.interval_hours * self.roundtrip_efficiency)
            )
            charge_power = min(self.max_power, max_by_soe)
            if charge_power <= 0:
                return 0.0
            return -charge_power

        return 0.0

    def update_soh_degradation(self, energy_discharged_mwh: float):
        if energy_discharged_mwh <= 0 or self.battery_capacity <= 0:
            return
        equivalent_cycle = energy_discharged_mwh / self.battery_capacity
        self.total_cycles += equivalent_cycle
        self.total_throughput_mwh += energy_discharged_mwh
        degradation_per_cycle = 0.0025
        soh_loss = equivalent_cycle * degradation_per_cycle
        self.current_soh = max(80.0, self.current_soh - soh_loss)
        self.actual_capacity_mwh = self.battery_capacity * (self.current_soh / 100)

    def get_battery_health_report(self):
        remaining_cycles = max(0.0, self.estimated_cycles - self.total_cycles)
        remaining_years = remaining_cycles / 365 if remaining_cycles > 0 else 0.0
        return {
            'current_soh': self.current_soh,
            'actual_capacity_mwh': self.actual_capacity_mwh,
            'total_cycles': self.total_cycles,
            'total_throughput_mwh': self.total_throughput_mwh,
            'remaining_cycles': remaining_cycles,
            'remaining_years': remaining_years,
            'capacity_fade': 100 - self.current_soh
        }

class EMSEngine:
    """
    Energy Management System simulation engine
    """
    
    def __init__(self, config):
        """
        Initialize EMS engine with configuration
        
        Args:
            config (dict): Configuration dictionary containing:
                - location: {name, city, country}
                - pv_system: {total_capacity_kwp, system_loss, inverter_capacity_kw}
                - ems_config: {target_md, max_discharge_power, battery_capacity, initial_soe}
                - financial: {capex, md_charge, peak_energy_rate, offpeak_energy_rate, include_pv_savings}
        """
        self.config = config
        self.controller = None
        self.results_df = None
        self.analysis = None
    
    def run_simulation(self, load_df):
        """
        Run complete EMS simulation
        
        Args:
            load_df (DataFrame): Load data with 'timestamp' and 'load' columns
            
        Returns:
            dict: Results containing data, analysis, and recommendations
        """
        # Clean and prepare data
        load_df = self._prepare_load_data(load_df)
        
        # Generate PV data
        load_df = self._generate_pv_data(load_df)
        
        # Run EMS simulation
        results_df = self._run_ems_simulation(load_df)
        
        # Analyze results
        analysis = self._analyze_results(results_df)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(analysis)
        
        return {
            'data': results_df,
            'analysis': analysis,
            'recommendations': recommendations
        }
    
    def _prepare_load_data(self, load_df):
        """Clean and prepare load data"""
        df = load_df.copy()
        
        # 统一列名为小写并去除空格
        df.columns = df.columns.str.lower().str.strip()
        
        # 检查必需的列
        required_cols = ['timestamp', 'load']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"CSV must have columns: {required_cols}. Missing: {missing_cols}")
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Remove duplicates
        df = df.drop_duplicates(subset='timestamp', keep='first')
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        return df
    
    def _generate_pv_data(self, load_df):
        """Generate PV data aligned with load timestamps with inverter capacity limit"""
        df = load_df.copy()
        timestamps = df['timestamp']
        
        # Time calculations
        hours = timestamps.dt.hour + timestamps.dt.minute / 60.0
        days_of_year = timestamps.dt.dayofyear + hours / 24.0
        
        # Solar parameters
        sunrise = 6.5
        sunset = 19.0
        day_length = sunset - sunrise
        
        # Initialize PV
        pv_power = np.zeros(len(timestamps))
        daytime_mask = (hours >= sunrise) & (hours < sunset)
        
        # Calculate PV for daytime
        if daytime_mask.any():
            hours_daytime = hours[daytime_mask]
            days_daytime = days_of_year[daytime_mask]
            
            # Solar elevation
            solar_fraction = (hours_daytime - sunrise) / day_length
            solar_angle = solar_fraction * np.pi
            elevation = np.sin(solar_angle)
            
            # Seasonal variation
            seasonal = 1.0 + 0.15 * np.cos(2 * np.pi * (days_daytime - 172) / 365)
            
            # Calculate PV power
            nameplate_kw = self.config['pv_system']['total_capacity_kwp']
            system_loss = self.config['pv_system']['system_loss']
            inverter_capacity_kw = self.config['pv_system'].get('inverter_capacity_kw', nameplate_kw)
            
            pv_power[daytime_mask] = nameplate_kw * elevation * seasonal * (1 - system_loss)
            
            # Apply inverter capacity limit (CLIPPING)
            pv_power[daytime_mask] = np.minimum(pv_power[daytime_mask], inverter_capacity_kw)
            
            # Ensure non-negative
            pv_power[daytime_mask] = np.maximum(0, pv_power[daytime_mask])
        
        df['pv_power'] = pv_power
        df['net_load'] = df['load'] - df['pv_power']
        
        return df

    @staticmethod
    def _parse_decimal_hour(time_str):
        """Convert HH:MM string to decimal hour."""
        if not time_str:
            return None
        try:
            dt = datetime.strptime(time_str, "%H:%M")
        except ValueError:
            return None
        return dt.hour + dt.minute / 60
    
    def _run_ems_simulation(self, data_df):
        """Run EMS control simulation"""
        ems_config = self.config['ems_config']
        control_mode = ems_config.get('control_mode', 'time_of_control')
        tou_config = ems_config.get('time_of_use', {}) or {}
        peak_config = ems_config.get('peak_shaving_period', {}) or {}

        self.control_mode = control_mode
        self.tou_charge_window = None
        self.tou_discharge_window = None
        self.tou_min_soe = tou_config.get('min_soe')
        self.tou_max_soe = tou_config.get('max_soe')
        peak_start_hour = peak_config.get('start_hour')
        peak_end_hour = peak_config.get('end_hour')

        if peak_start_hour is None:
            peak_start_hour = self._parse_decimal_hour(
                peak_config.get('start_time') or peak_config.get('start')
            )
        if peak_end_hour is None:
            peak_end_hour = self._parse_decimal_hour(
                peak_config.get('end_time') or peak_config.get('end')
            )

        peak_start_hour = peak_start_hour if peak_start_hour is not None else 18.0
        peak_end_hour = peak_end_hour if peak_end_hour is not None else 22.0

        if peak_end_hour <= peak_start_hour:
            raise ValueError("Peak shaving end time must be later than the start time.")
        
        self.peak_start_hour = peak_start_hour
        self.peak_end_hour = peak_end_hour

        if control_mode == 'time_of_use':
            def _resolve_window(window_cfg, default_start, default_end):
                start_val = window_cfg.get('start_hour')
                end_val = window_cfg.get('end_hour')
                if start_val is None:
                    start_val = self._parse_decimal_hour(window_cfg.get('start_time'))
                if end_val is None:
                    end_val = self._parse_decimal_hour(window_cfg.get('end_time'))
                if start_val is None:
                    start_val = default_start
                if end_val is None:
                    end_val = default_end
                return {
                    'start_hour': float(start_val) % 24,
                    'end_hour': float(end_val) % 24
                }

            self.tou_charge_window = _resolve_window(tou_config.get('charge_window', {}), 0.0, 6.0)
            self.tou_discharge_window = _resolve_window(tou_config.get('discharge_window', {}), 18.0, 22.0)

            self.controller = TimeOfUseController(
                max_power=ems_config['max_discharge_power'],
                battery_capacity=ems_config['battery_capacity'],
                charge_window=self.tou_charge_window,
                discharge_window=self.tou_discharge_window,
                min_soe=tou_config.get('min_soe', 15.0),
                max_soe=tou_config.get('max_soe', 90.0),
                roundtrip_efficiency=0.90
            )
        else:
            # Initialize controller for Time-of-Control mode
            self.controller = AdvancedEMSController(
                target_md=ems_config['target_md'],
                max_power=ems_config['max_discharge_power'],
                battery_capacity=ems_config['battery_capacity'],
                peak_start_hour=peak_start_hour,
                peak_end_hour=peak_end_hour
            )
        
        # Initialize results storage
        results = {
            'timestamp': [], 'load': [], 'pv_power': [], 'net_load': [],
            'discharge': [], 'soe': [],
            'md30_no_pv_no_ems': [], 'md30_with_pv_no_ems': [], 'md30_with_pv_with_ems': [],
            'grid_import': [], 'pv_to_load': [], 'pv_to_battery': [], 'pv_curtailment': [],
            'current_soh': []
        }
        
        soe = ems_config['initial_soe']
        rte = 0.90
        interval_hours = 5 / 60
        track_tou = control_mode == 'time_of_use'
        was_in_discharge_window = False
        tou_leftover_events = []
        time_of_control_extension = None

        def process_interval(ts, load, pv, net_load):
            nonlocal soe, was_in_discharge_window
            prev_soe = soe
            in_discharge_window = self.controller.is_discharge_period(ts) if track_tou else False

            discharge = self.controller.control_decision(
                soe=soe, net_load=net_load,
                current_time=ts, load=load, pv_power=pv
            )

            if discharge < 0:  # Charging
                charge_power = abs(discharge)
                if self.controller.is_priority_charge_period(ts) or \
                   self.controller.is_constrained_charge_period(ts):
                    pv_to_battery = min(charge_power, pv)
                    pv_to_load = max(0, pv - pv_to_battery)
                    grid_import = max(0, load - pv_to_load) + max(0, charge_power - pv_to_battery)
                    pv_curtailment = 0
                else:
                    pv_to_battery, pv_to_load = 0, min(pv, load)
                    grid_import = max(0, load - pv_to_load)
                    pv_curtailment = max(0, pv - pv_to_load)

                soe += (charge_power * interval_hours / 1000 / ems_config['battery_capacity']) * 100 * rte

            elif discharge > 0:  # Discharging
                pv_to_battery = 0
                pv_to_load = min(pv, load)
                grid_import = max(0, load - pv_to_load - discharge)
                pv_curtailment = max(0, pv - pv_to_load)

                soe -= (discharge * interval_hours / 1000 / ems_config['battery_capacity']) * 100 / rte
                self.controller.update_soh_degradation(discharge * interval_hours / 1000)

            else:  # Standby
                pv_to_battery = 0
                pv_to_load = min(pv, load)
                grid_import = max(0, load - pv_to_load)
                pv_curtailment = max(0, pv - pv_to_load)

            soe = max(self.controller.soe_min, min(self.controller.soe_max, soe))

            for k, v in zip(
                ['timestamp', 'load', 'pv_power', 'net_load', 'discharge', 'soe',
                 'grid_import', 'pv_to_load', 'pv_to_battery', 'pv_curtailment', 'current_soh'],
                [ts, load, pv, net_load, discharge, soe,
                 grid_import, pv_to_load, pv_to_battery, pv_curtailment, self.controller.current_soh]
            ):
                results[k].append(v)

            window_size = min(6, len(results['load']))
            results['md30_no_pv_no_ems'].append(sum(results['load'][-window_size:]) / window_size)
            results['md30_with_pv_no_ems'].append(
                sum([max(0, results['load'][i] - results['pv_power'][i])
                     for i in range(len(results['load']) - window_size, len(results['load']))]) / window_size
            )
            results['md30_with_pv_with_ems'].append(sum(results['grid_import'][-window_size:]) / window_size)

            if track_tou:
                if was_in_discharge_window and not in_discharge_window:
                    leftover_soe = max(0.0, prev_soe - self.controller.soe_min)
                    leftover_energy_kwh = (leftover_soe / 100) * ems_config['battery_capacity'] * 1000
                    tou_leftover_events.append({
                        'timestamp': ts,
                        'remaining_soe': soe,
                        'excess_above_min_pct': leftover_soe,
                        'excess_energy_kwh': leftover_energy_kwh
                    })
                was_in_discharge_window = in_discharge_window

            return discharge, prev_soe, soe

        # Primary simulation loop
        for _, row in data_df.iterrows():
            process_interval(row['timestamp'], row['load'], row['pv_power'], row['net_load'])

        # Capture leftover for Time-of-Use mode
        if track_tou and was_in_discharge_window:
            leftover_soe = max(0.0, soe - self.controller.soe_min)
            leftover_energy_kwh = (leftover_soe / 100) * ems_config['battery_capacity'] * 1000
            tou_leftover_events.append({
                'timestamp': data_df.iloc[-1]['timestamp'],
                'remaining_soe': soe,
                'excess_above_min_pct': leftover_soe,
                'excess_energy_kwh': leftover_energy_kwh,
                'note': 'simulation ended within discharge window'
            })

        # Time-of-Control extension: continue into next day until minimum SoE
        if control_mode == 'time_of_control' and soe > self.controller.soe_min + 1e-6:
            pre_extension_soe = soe
            extension_energy_kwh = 0.0
            extension_intervals = 0

            charge_start_hour = getattr(self.controller, 'charge_start_hour', 0.0)
            extension_candidates = data_df[
                (data_df['timestamp'].dt.hour + data_df['timestamp'].dt.minute / 60.0) < charge_start_hour
            ]
            if extension_candidates.empty:
                extension_candidates = data_df.copy()

            max_cycles = 3
            cycle = 0
            while soe > self.controller.soe_min + 1e-6 and cycle < max_cycles and not extension_candidates.empty:
                day_offset = cycle + 1
                for _, ext_row in extension_candidates.iterrows():
                    if soe <= self.controller.soe_min + 1e-6:
                        break
                    extended_ts = ext_row['timestamp'] + pd.Timedelta(days=day_offset)
                    discharge, prev_soe, new_soe = process_interval(
                        extended_ts, ext_row['load'], ext_row['pv_power'], ext_row['net_load']
                    )
                    delta_pct = max(0.0, prev_soe - new_soe)
                    extension_energy_kwh += (delta_pct / 100) * ems_config['battery_capacity'] * 1000
                    extension_intervals += 1
                cycle += 1

            time_of_control_extension = {
                'initial_excess_pct': max(0.0, pre_extension_soe - self.controller.soe_min),
                'final_soe_pct': soe,
                'extension_intervals': extension_intervals,
                'extension_energy_kwh': extension_energy_kwh,
                'completed': soe <= self.controller.soe_min + 1e-6
            }

        self.tou_leftover_events = tou_leftover_events
        self.tou_final_soe = soe
        self.time_of_control_extension = time_of_control_extension
        return pd.DataFrame(results)
    
    def _analyze_results(self, results_df):
        """Analyze simulation results with updated energy savings calculation and inverter clipping"""
        financial = self.config['financial']
        ems_config = self.config['ems_config']
        
        # Get PV savings inclusion option (default to True if not specified)
        include_pv_savings = financial.get('include_pv_savings', True)
        
        # Calculate MD values (weekdays 2pm-10pm)
        billing_mask = results_df['timestamp'].apply(
            lambda x: 14 <= x.hour < 22 and x.weekday() < 5
        )
        
        if billing_mask.any():
            md_no_pv = results_df.loc[billing_mask, 'md30_no_pv_no_ems'].max()
            md_with_pv = results_df.loc[billing_mask, 'md30_with_pv_no_ems'].max()
            md_final = results_df.loc[billing_mask, 'md30_with_pv_with_ems'].max()
        else:
            md_no_pv = results_df['md30_no_pv_no_ems'].max()
            md_with_pv = results_df['md30_with_pv_no_ems'].max()
            md_final = results_df['md30_with_pv_with_ems'].max()
        
        pv_contribution = md_no_pv - md_with_pv
        ems_contribution = md_with_pv - md_final
        total_reduction = md_no_pv - md_final
        
        # MD Savings
        monthly_md_savings = total_reduction * financial['md_charge']
        
        # BESS Discharge-Based Energy Savings
        peak_rate_mask = results_df['timestamp'].apply(
            lambda x: 14 <= x.hour < 22 and x.weekday() < 5
        )
        peak_start = getattr(self, 'peak_start_hour', 18.0)
        peak_end = getattr(self, 'peak_end_hour', 22.0)
        core_peak_shaving_mask = results_df['timestamp'].apply(
            lambda x: (
                peak_start <= x.hour + x.minute / 60.0 < peak_end
                and x.weekday() < 5
            )
        )
        
        INTERVAL_H = 5/60
        
        discharge_mask = results_df['discharge'] > 0
        
        E_peak_rate_discharge_kwh = results_df.loc[
            peak_rate_mask & discharge_mask, 'discharge'
        ].sum() * INTERVAL_H
        
        E_total_discharge_kwh = results_df.loc[
            discharge_mask, 'discharge'
        ].sum() * INTERVAL_H
        
        E_offpeak_extra_kwh = E_total_discharge_kwh - E_peak_rate_discharge_kwh
        
        E_core_peak_discharge_kwh = results_df.loc[
            core_peak_shaving_mask & discharge_mask, 'discharge'
        ].sum() * INTERVAL_H
        E_core_peak_discharge_mwh = E_core_peak_discharge_kwh / 1000
        
        E_pv_self_consumption_kwh = results_df['pv_to_load'].sum() * INTERVAL_H
        
        simulation_days = (results_df['timestamp'].max() - results_df['timestamp'].min()).days + 1
        
        daily_peak_discharge_savings = (E_peak_rate_discharge_kwh / simulation_days) * financial['peak_energy_rate']
        daily_offpeak_discharge_savings = (E_offpeak_extra_kwh / simulation_days) * financial['offpeak_energy_rate']
        daily_pv_self_consumption_savings = (E_pv_self_consumption_kwh / simulation_days) * financial['peak_energy_rate']
        
        monthly_peak_discharge_savings = daily_peak_discharge_savings * 30
        monthly_offpeak_discharge_savings = daily_offpeak_discharge_savings * 30
        monthly_pv_savings = daily_pv_self_consumption_savings * 30
        
        # Calculate savings based on PV inclusion option
        if include_pv_savings:
            # Include PV savings in ROI calculations
            monthly_savings_for_roi = (
                monthly_md_savings + 
                monthly_peak_discharge_savings + 
                monthly_offpeak_discharge_savings +
                monthly_pv_savings  # Include PV savings
            )
            annual_savings_for_roi = monthly_savings_for_roi * 12
            monthly_total_savings = monthly_savings_for_roi
        else:
            # Exclude PV savings from ROI calculations (BESS-only analysis)
            monthly_savings_for_roi = (
                monthly_md_savings + 
                monthly_peak_discharge_savings + 
                monthly_offpeak_discharge_savings
                # PV savings excluded
            )
            annual_savings_for_roi = monthly_savings_for_roi * 12
            monthly_total_savings = monthly_savings_for_roi + monthly_pv_savings
        
        annual_total_savings = monthly_total_savings * 12
        
        # Inverter Clipping Analysis
        inverter_capacity = self.config['pv_system'].get('inverter_capacity_kw', float('inf'))
        nameplate_capacity = self.config['pv_system']['total_capacity_kwp']
        system_loss = self.config['pv_system']['system_loss']
        
        # Calculate theoretical PV without inverter limit
        timestamps = results_df['timestamp']
        hours = timestamps.dt.hour + timestamps.dt.minute / 60.0
        days_of_year = timestamps.dt.dayofyear + hours / 24.0
        sunrise, sunset = 6.5, 19.0
        day_length = sunset - sunrise
        
        pv_theoretical = np.zeros(len(timestamps))
        daytime_mask = (hours >= sunrise) & (hours < sunset)
        
        if daytime_mask.any():
            hours_daytime = hours[daytime_mask]
            days_daytime = days_of_year[daytime_mask]
            solar_fraction = (hours_daytime - sunrise) / day_length
            solar_angle = solar_fraction * np.pi
            elevation = np.sin(solar_angle)
            seasonal = 1.0 + 0.15 * np.cos(2 * np.pi * (days_daytime - 172) / 365)
            pv_theoretical[daytime_mask] = nameplate_capacity * elevation * seasonal * (1 - system_loss)
        
        # Calculate clipping
        pv_clipped_mask = (pv_theoretical >= inverter_capacity * 0.99) & (pv_theoretical > results_df['pv_power'])
        clipping_hours = pv_clipped_mask.sum() * 5 / 60
        clipping_percentage = (pv_clipped_mask.sum() / len(results_df)) * 100 if len(results_df) > 0 else 0
        energy_lost_kwh = (pv_theoretical[pv_clipped_mask] - results_df.loc[pv_clipped_mask, 'pv_power']).sum() * INTERVAL_H
        
        # ROI calculations
        capex = financial['capex']
        payback = capex / annual_savings_for_roi if annual_savings_for_roi > 0 else float('inf')
        roi_5yr = (annual_savings_for_roi * 5 - capex) / capex * 100 if annual_savings_for_roi > 0 else float('-inf')
        roi_10yr = (annual_savings_for_roi * 10 - capex) / capex * 100 if annual_savings_for_roi > 0 else float('-inf')
        
        health = self.controller.get_battery_health_report()
        time_of_use_report = None
        if self.control_mode == 'time_of_use':
            events = getattr(self, 'tou_leftover_events', [])
            battery_capacity_mwh = ems_config['battery_capacity']
            simplified_events = []
            for ev in events:
                simplified_events.append({
                    'timestamp': ev['timestamp'].isoformat() if hasattr(ev['timestamp'], 'isoformat') else str(ev['timestamp']),
                    'remaining_soe': ev['remaining_soe'],
                    'excess_above_min_pct': ev['excess_above_min_pct'],
                    'excess_energy_kwh': ev['excess_energy_kwh'],
                    'note': ev.get('note')
                })

            max_excess_pct = max((ev['excess_above_min_pct'] for ev in events), default=0.0) if events else 0.0
            avg_excess_pct = float(np.mean([ev['excess_above_min_pct'] for ev in events])) if events else 0.0
            last_event = events[-1] if events else None
            last_summary = None
            if last_event:
                last_summary = {
                    'timestamp': last_event['timestamp'].isoformat() if hasattr(last_event['timestamp'], 'isoformat') else str(last_event['timestamp']),
                    'remaining_soe': last_event['remaining_soe'],
                    'excess_above_min_pct': last_event['excess_above_min_pct'],
                    'excess_energy_kwh': last_event['excess_energy_kwh'],
                    'note': last_event.get('note')
                }

            final_excess_pct = max(0.0, getattr(self, 'tou_final_soe', results_df['soe'].iloc[-1]) - self.controller.soe_min)
            final_excess_energy = (final_excess_pct / 100) * battery_capacity_mwh * 1000

            time_of_use_report = {
                'charge_window': self.tou_charge_window,
                'discharge_window': self.tou_discharge_window,
                'min_soe_target': self.controller.soe_min,
                'max_soe_limit': self.controller.soe_max,
                'leftover_events': simplified_events,
                'last_leftover': last_summary,
                'max_excess_pct': max_excess_pct,
                'avg_excess_pct': avg_excess_pct,
                'final_excess_pct': final_excess_pct,
                'final_excess_energy_kwh': final_excess_energy,
                'battery_capacity_mwh': battery_capacity_mwh
            }
        time_of_control_extension = getattr(self, 'time_of_control_extension', None)
        
        return {
            'md_no_pv_no_ems': md_no_pv,
            'md_with_pv_no_ems': md_with_pv,
            'md_with_pv_with_ems': md_final,
            'pv_contribution': pv_contribution,
            'ems_contribution': ems_contribution,
            'total_reduction': total_reduction,
            'monthly_savings': monthly_savings_for_roi,
            'annual_savings': annual_savings_for_roi,
            'monthly_total_savings': monthly_total_savings,
            'annual_total_savings': annual_total_savings,
            'capex': capex,
            'payback_years': payback,
            'roi_5yr': roi_5yr,
            'roi_10yr': roi_10yr,
            'equivalent_cycles': health['total_cycles'],
            'final_soh': health['current_soh'],
            'savings_breakdown': {
                'md_savings': monthly_md_savings,
                'peak_discharge_savings': monthly_peak_discharge_savings,
                'offpeak_discharge_savings': monthly_offpeak_discharge_savings,
                'pv_self_consumption_savings': monthly_pv_savings
            },
            'energy_metrics': {
                'core_peak_discharge_mwh': E_core_peak_discharge_mwh,
                'total_discharge_kwh': E_total_discharge_kwh,
                'pv_self_consumption_kwh': E_pv_self_consumption_kwh,
                'simulation_days': simulation_days
            },
            'inverter_clipping': {
                'hours': clipping_hours,
                'percentage': clipping_percentage,
                'capacity_kw': inverter_capacity,
                'energy_lost_kwh': energy_lost_kwh
            },
            'include_pv_savings': include_pv_savings,  # Add this flag to results
            'control_mode': self.control_mode,
            'time_of_use_report': time_of_use_report,
            'time_of_control_extension': time_of_control_extension
        }
    
    def _generate_recommendations(self, analysis):
        """Generate optimization recommendations"""
        ems_config = self.config['ems_config']
        financial = self.config['financial']
        
        max_capability = ems_config['max_discharge_power']
        actual_used = analysis['ems_contribution']
        remaining = max_capability - actual_used
        
        utilization_rate = (remaining / max_capability * 100) if max_capability > 0 else 0
        
        recommendations = {
            'remaining_capacity': remaining,
            'utilization_rate': utilization_rate,
            'has_opportunity': False,
            'utilization_level': 'optimal'
        }
        
        if remaining > 200:
            potential_reduction = remaining * 0.8
            suggested_target = analysis['md_with_pv_with_ems'] - potential_reduction
            extra_monthly = potential_reduction * financial['md_charge']
            extra_annual = extra_monthly * 12
            new_annual = analysis['annual_savings'] + extra_annual
            new_payback = financial['capex'] / new_annual if new_annual > 0 else float('inf')
            
            recommendations.update({
                'has_opportunity': True,
                'utilization_level': 'low',
                'suggested_target': suggested_target,
                'additional_reduction': potential_reduction,
                'extra_monthly_savings': extra_monthly,
                'extra_annual_savings': extra_annual,
                'new_annual_savings': new_annual,
                'new_payback': new_payback,
                'savings_increase': (extra_annual / analysis['annual_savings'] * 100) if analysis['annual_savings'] > 0 else 0
            })
            
        elif remaining > 50:
            recommendations.update({
                'utilization_level': 'good',
                'suggested_target': analysis['md_with_pv_with_ems'] - remaining * 0.5
            })
        else:
            recommendations.update({
                'utilization_level': 'high'
            })
        
        return recommendations
