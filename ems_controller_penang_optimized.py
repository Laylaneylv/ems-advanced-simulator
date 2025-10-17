# ems_controller_penang_optimized.py - Penang Project Optimized Controller
"""
Penang Project EMS Control Strategy

Control Objectives:
1. Maximum Peak Shaving Power: 2 MW (2000 kW)
2. Battery Capacity: 10 MWh
3. Core Peak Period: User-defined (default 18:00-22:00 runtime configuration)
4. Strategy: Ensure continuous peak shaving across the configured window, then extend discharge to 15% SoE.

Energy Calculation:
- Continuous 2MW discharge for 4 hours = 8 MWh (exceeds capacity)
- Actual available: 10 MWh / 4 hours = 1.875 MW average power
- Considering efficiency and safety margin, target average discharge = 1.8 MW

Charging Strategy (auto-adjusted to peak window):
- Priority charging concludes a few hours before peak start to hit 88% SoE
- Final constrained charging ends shortly before the peak window begins
"""

from datetime import datetime, timedelta
from collections import deque
import statistics

class AdvancedEMSController:
    """
    Penang Project Optimized EMS Controller
    
    Core Strategy:
    1. Daytime PV priority charging to 88% SoE
    2. Configurable peak window discharge (2MW or lower to extend discharge time)
    3. Intelligent power allocation to ensure energy lasts through the peak window
    4. Post-peak extended discharge to 15% SoE.
    """
    
    def __init__(
        self,
        target_md=6500,
        max_power=2000,
        battery_capacity=10,
        peak_start_hour=18.0,
        peak_end_hour=22.0,
        pre_peak_buffer_hours=1.0,
        priority_charge_duration=8.0,
        constrained_charge_duration=3.0,
    ):
        self.target_md = target_md
        self.max_power = max_power  # 2 MW max peak shaving power
        self.battery_capacity = battery_capacity  # 10 MWh

        if peak_end_hour <= peak_start_hour:
            raise ValueError("Peak shaving end hour must be later than the start hour.")
        
        # Peak configuration
        self.peak_start_hour = peak_start_hour
        self.peak_end_hour = peak_end_hour
        self.pre_peak_buffer_hours = max(0.0, pre_peak_buffer_hours)
        self.priority_charge_duration = max(0.0, priority_charge_duration)
        self.constrained_charge_duration = max(0.0, constrained_charge_duration)
        self.peak_duration_hours = self.peak_end_hour - self.peak_start_hour
        
        # ============ Control Parameters (considering SOH degradation) ============
        
        # SOH related parameters
        self.initial_soh = 100  # Initial health 100%
        self.current_soh = 100  # Current health (degrades over time)
        self.target_lifetime_years = 10  # Target lifetime 10 years
        self.target_lifetime_cycles = 3650  # Target cycles (10 years × 365 days)
        
        # DOD limits considering SOH
        # MODIFIED: Allow deeper discharge (down to 15% for extended use post-peak)
        self.max_dod = 0.75  # Maximum DOD 75% (90% - 15%) 
        
        # Calculate SoE range based on DOD
        self.soe_max = 90  # Upper limit 90% (avoid full charge, extend life)
        self.soe_min = 15  # Lower limit 15% (for extended discharge) <-- MODIFIED
        self.soe_safety_margin = 3  # Safety margin 3%
        
        # Target SoE before Peak (considering actual available range after SOH)
        self.target_soe_before_peak = 88  # 88% (reserve 2% buffer)
        
        # ============ Peak Period Definition ============
        self.charge_end_hour = max(0.0, min(24.0, self.peak_start_hour - self.pre_peak_buffer_hours))
        raw_priority_end = self.charge_end_hour - self.constrained_charge_duration
        raw_priority_end = max(0.0, raw_priority_end)
        self.priority_charge_end_hour = min(self.charge_end_hour, raw_priority_end)
        self.charge_start_hour = max(0.0, self.priority_charge_end_hour - self.priority_charge_duration)
        if self.charge_start_hour > self.priority_charge_end_hour:
            self.charge_start_hour = self.priority_charge_end_hour
        self.peak_start_minutes = self._hour_to_minutes(self.peak_start_hour)
        self.peak_end_minutes = self._hour_to_minutes(self.peak_end_hour)
        self.charge_start_minutes = self._hour_to_minutes(self.charge_start_hour)
        self.priority_charge_end_minutes = self._hour_to_minutes(self.priority_charge_end_hour)
        self.charge_end_minutes = self._hour_to_minutes(self.charge_end_hour)
        
        # Extended discharge target
        self.extended_discharge_target_soe = 15 # Continue discharge until 15% SoE
        
        # ============ Energy Management (considering SOH) ============
        
        # Actual battery capacity (considering SOH degradation)
        self.actual_capacity_mwh = self.battery_capacity * (self.current_soh / 100)
        
        # Calculate available energy for configured Core Peak period
        # We reserve the 15% SoE for the absolute end, so usable range is 88% -> 15%
        self.usable_soe_range = self.target_soe_before_peak - (self.extended_discharge_target_soe + self.soe_safety_margin)
        self.usable_energy_mwh = (self.usable_soe_range / 100) * self.actual_capacity_mwh
        
        # Calculate effective DOD
        self.effective_dod = self.usable_soe_range / 100
        
        # Calculate theoretical average discharge power for the configured peak window
        self.theoretical_avg_discharge = (self.usable_energy_mwh / self.peak_duration_hours) * 1000  # kW
        
        # Actual control target (considering 90% roundtrip efficiency)
        self.target_avg_discharge = self.theoretical_avg_discharge * 0.9
        
        # Cycle life estimation (based on DOD-Cycle relationship)
        if self.effective_dod <= 0.50:
            self.estimated_cycles = 6000
        elif self.effective_dod <= 0.65:
            self.estimated_cycles = 4000
        # MODIFIED: Use a lower estimate for 75% DOD
        elif self.effective_dod <= 0.75: 
            self.estimated_cycles = 3000 # Adjusted for 75% DOD
        elif self.effective_dod <= 0.80:
            self.estimated_cycles = 2500
        else:
            self.estimated_cycles = 1200
        
        self.estimated_lifetime_years = self.estimated_cycles / 365
        
        # ============ Multi-window Data Structures ============
        self.window_30min = deque(maxlen=6)
        self.window_15min = deque(maxlen=3)
        self.power_history = deque(maxlen=48)
        self.pv_history = deque(maxlen=48)
        self.load_history = deque(maxlen=48)
        
        # PV charging parameters
        self.min_pv_for_charge = 50  # Minimum 50kW PV to start charging
        
        # Peak period energy tracking
        self.peak_start_soe = None  # SoE at Peak start
        
        # SOH tracking
        self.total_cycles = 0  # Cumulative cycle count
        self.total_throughput_mwh = 0  # Cumulative throughput
        self.daily_cycles = 0  # Daily cycle count
        
        # ============ Initialization Print ============
        self._print_initialization_info()
    
    @staticmethod
    def _hour_to_minutes(hour_decimal):
        total_minutes = int(round(hour_decimal * 60))
        return total_minutes % (24 * 60)

    @staticmethod
    def _format_hour(hour_decimal):
        total_minutes = AdvancedEMSController._hour_to_minutes(hour_decimal)
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"

    @staticmethod
    def _to_decimal_hour(current_time):
        return current_time.hour + current_time.minute / 60.0

    @staticmethod
    def _minutes_since_midnight(current_time):
        return current_time.hour * 60 + current_time.minute
    
    def _print_initialization_info(self):
        """Print controller initialization information"""
        print("\n" + "=" * 70)
        print("🚀 Penang Project Optimized EMS Controller (with SOH Management & Extended Discharge)")
        print("=" * 70)
        print(f"✅ Max Peak Shaving Power: {self.max_power} kW (2 MW)")
        print(f"✅ Rated Battery Capacity: {self.battery_capacity} MWh")
        print(f"✅ Current SOH: {self.current_soh}%")
        print(f"✅ Actual Available Capacity: {self.actual_capacity_mwh:.2f} MWh")
        print(
            f"✅ Core Peak Period: "
            f"{self._format_hour(self.peak_start_hour)} - {self._format_hour(self.peak_end_hour)} "
            f"({self.peak_duration_hours:.1f} hours)"
        )
        print(
            f"✅ Charging Period: "
            f"{self._format_hour(self.charge_start_hour)} - {self._format_hour(self.charge_end_hour)}"
        )
        if self.priority_charge_end_hour > self.charge_start_hour:
            print(
                f"   - Priority Charge: "
                f"{self._format_hour(self.charge_start_hour)} - {self._format_hour(self.priority_charge_end_hour)}"
            )
        if self.charge_end_hour > self.priority_charge_end_hour:
            print(
                f"   - Constrained Charge: "
                f"{self._format_hour(self.priority_charge_end_hour)} - {self._format_hour(self.charge_end_hour)}"
            )
        print(f"\n🔋 SOH Optimization Strategy:")
        print(f"   SoE Operating Range (Max): {self.extended_discharge_target_soe}% - {self.soe_max}%")
        print(f"   Target SoE Before Peak: {self.target_soe_before_peak}%")
        print(f"   Actual DOD: {self.effective_dod*100:.1f}% (Conservative for Core Peak)")
        print(f"   Expected Cycle Life: {self.estimated_cycles:,} cycles")
        print(f"   Expected Lifetime: {self.estimated_lifetime_years:.1f} years")
        print(f"\n💡 Extended Discharge Plan:")
        print(
            f"   Post-{self._format_hour(self.peak_end_hour)} Discharge Target: "
            f"{self.extended_discharge_target_soe}% SoE"
        )
        print(
            f"\n📊 Core Peak ({self._format_hour(self.peak_start_hour)}-"
            f"{self._format_hour(self.peak_end_hour)}) Energy Allocation:"
        )
        print(f"   Available SoE Range: {self.extended_discharge_target_soe + self.soe_safety_margin}% → {self.target_soe_before_peak}%")
        print(f"   Usable Energy: {self.usable_energy_mwh:.2f} MWh")
        print(
            f"   Target Avg Discharge: {self.target_avg_discharge:.0f} kW "
            f"(for {self.peak_duration_hours:.1f} hours)"
        )
        print("=" * 70)
        
    def update_soh_degradation(self, energy_discharged_mwh):
        """
        Update SOH degradation (simplified model)
        """
        # Calculate equivalent cycles
        equivalent_cycle = energy_discharged_mwh / self.battery_capacity
        
        # Accumulate cycles and throughput
        self.total_cycles += equivalent_cycle
        self.total_throughput_mwh += energy_discharged_mwh
        
        # SOH degradation (simplified linear model: 10% loss after 4000 cycles)
        degradation_per_cycle = 0.0025
        soh_loss = equivalent_cycle * degradation_per_cycle
        
        self.current_soh = max(80, self.current_soh - soh_loss)  # Minimum 80%
        
        # Update actual capacity
        self.actual_capacity_mwh = self.battery_capacity * (self.current_soh / 100)
    
    def get_battery_health_report(self):
        """Get battery health report"""
        remaining_cycles = self.estimated_cycles - self.total_cycles
        remaining_years = remaining_cycles / 365
        
        return {
            'current_soh': self.current_soh,
            'actual_capacity_mwh': self.actual_capacity_mwh,
            'total_cycles': self.total_cycles,
            'total_throughput_mwh': self.total_throughput_mwh,
            'remaining_cycles': max(0, remaining_cycles),
            'remaining_years': max(0, remaining_years),
            'capacity_fade': 100 - self.current_soh
        }
    
    def calculate_md30(self):
        """Calculate 30-minute average demand"""
        if len(self.window_30min) == 0:
            return 0
        return sum(self.window_30min) / len(self.window_30min)
    
    def is_peak_period(self, current_time):
        """Check if within the configured peak period."""
        current_decimal = self._to_decimal_hour(current_time)
        return self.peak_start_hour <= current_decimal < self.peak_end_hour
    
    def is_priority_charge_period(self, current_time):
        """Check if in priority charging period."""
        current_decimal = self._to_decimal_hour(current_time)
        return self.charge_start_hour <= current_decimal < self.priority_charge_end_hour
    
    def is_constrained_charge_period(self, current_time):
        """Check if in constrained charging period."""
        current_decimal = self._to_decimal_hour(current_time)
        return self.priority_charge_end_hour <= current_decimal < self.charge_end_hour
    
    def get_remaining_peak_time(self, current_time):
        """Calculate remaining time in Peak period (hours)"""
        if not self.is_peak_period(current_time):
            return 0
        
        current_decimal = self._to_decimal_hour(current_time)
        remaining = self.peak_end_hour - current_decimal
        
        return max(0, remaining)
    
    def get_elapsed_peak_time(self, current_time):
        """Calculate elapsed time in Peak period (hours)"""
        if not self.is_peak_period(current_time):
            return 0
        
        current_decimal = self._to_decimal_hour(current_time)
        elapsed = current_decimal - self.peak_start_hour
        
        return max(0, elapsed)
    
    def calculate_optimal_discharge_power(self, current_time, soe, net_load):
        """
        Calculate optimal discharge power for Core Peak (18:00-22:00)
        
        Strategy: Dynamically adjust based on remaining time and available energy
        """
        remaining_time = self.get_remaining_peak_time(current_time)
        
        if remaining_time <= 0:
            return 0
        
        # Calculate remaining available energy (down to extended_discharge_target_soe + safety)
        available_soe = soe - (self.extended_discharge_target_soe + self.soe_safety_margin)
        available_energy_mwh = (available_soe / 100) * self.battery_capacity
        
        if available_energy_mwh <= 0:
            print(f"⚠️  {current_time.strftime('%H:%M')} Energy depleted for Core Peak reserve!")
            return 0
        
        # Calculate average power needed for remaining time
        required_avg_power = (available_energy_mwh / remaining_time) * 1000  # kW
        
        # Calculate current power reduction needed
        md30 = self.calculate_md30()
        excess_power = max(0, md30 - self.target_md)
        
        # Decision logic
        if excess_power <= 0:
            # Current load already below target, no discharge needed
            discharge = 0
        else:
            # Need to discharge for peak shaving
            # Discharge power = min(needed reduction, max power, avg power for remaining time * 1.2)
            # Allow acceleration (1.2x) to ensure peak is met early
            discharge = min(
                excess_power,           # Actual reduction needed
                self.max_power,         # Max 2MW limit
                required_avg_power * 1.2  # Allow 20% above average
            )
        
        # Energy tracking and reporting
        elapsed_time = self.get_elapsed_peak_time(current_time)
        progress_pct = (elapsed_time / self.peak_duration_hours) * 100
        
        if discharge > 0 and current_time.minute % 30 == 0:  # Report every 30 minutes
            print(f"⚡ {current_time.strftime('%H:%M')} [Core Peak] | "
                  f"Progress={progress_pct:.0f}% | "
                  f"SoE={soe:.1f}% | "
                  f"Remaining={remaining_time:.1f}h | "
                  f"Available={available_energy_mwh:.2f}MWh | "
                  f"Discharge={discharge:.0f}kW | "
                  f"MD30={md30:.0f}kW")
        
        return discharge
    
    def calculate_charge_power_priority(self, current_time, soe, load, pv_power):
        """Calculate charging power during priority charging window (PV-priority)."""
        # Already reached target SoE
        if soe >= self.target_soe_before_peak:
            return 0
        
        # Insufficient PV, no charging
        if pv_power < self.min_pv_for_charge:
            return 0
        
        # Calculate energy still needed (up to target_soe_before_peak)
        soe_deficit = self.target_soe_before_peak - soe
        required_energy_mwh = (soe_deficit / 100) * self.battery_capacity
        
        # Calculate remaining charging time (until configured cut-off)
        current_decimal = self._to_decimal_hour(current_time)
        remaining_charge_time = self.charge_end_hour - current_decimal
        
        if remaining_charge_time <= 0:
            return 0
        
        # Calculate required average charging power
        required_charge_power = (required_energy_mwh / remaining_charge_time) * 1000  # kW
        
        # Actual charging power (PV priority to BESS)
        charge_power = min(
            pv_power * 0.95,            # 95% of PV (leave small margin)
            self.max_power,              # Max charging power
            required_charge_power * 1.5  # Accelerate charging
        )
        
        # Don't exceed SoE upper limit
        time_interval_h = 5/60
        max_by_soe = ((self.soe_max - soe) / 100) * self.battery_capacity * 1000 / time_interval_h
        charge_power = min(charge_power, max_by_soe)
        
        if charge_power > 100 and current_time.minute % 30 == 0:
            print(f"🔋 {current_time.strftime('%H:%M')} [Priority] | "
                  f"SoE={soe:.1f}% → {self.target_soe_before_peak}% | "
                  f"Charge={charge_power:.0f}kW | "
                  f"PV={pv_power:.0f}kW | "
                  f"Remaining Time={remaining_charge_time:.1f}h")
        
        return charge_power
    
    def calculate_charge_power_constrained(self, current_time, soe, load, pv_power):
        """Calculate charging power during constrained charging window (MD-aware)."""
        # Already reached target SoE
        if soe >= self.target_soe_before_peak:
            return 0
        
        # Insufficient PV, no charging
        if pv_power < self.min_pv_for_charge:
            return 0
        
        # Calculate current MD
        md30 = self.calculate_md30()
        
        # Calculate maximum allowable charging power (considering MD constraint)
        md_headroom = max(0, self.target_md - md30)
        
        # If MD already at or above target, no charging
        if md_headroom <= 100:
            return 0
        
        # Calculate energy still needed (up to target_soe_before_peak)
        soe_deficit = self.target_soe_before_peak - soe
        required_energy_mwh = (soe_deficit / 100) * self.battery_capacity
        
        # Calculate remaining charging time
        current_decimal = self._to_decimal_hour(current_time)
        remaining_charge_time = self.charge_end_hour - current_decimal
        
        if remaining_charge_time <= 0:
            return 0
        
        # Calculate required average charging power
        required_charge_power = (required_energy_mwh / remaining_charge_time) * 1000  # kW
        
        # Actual charging power (consider MD constraint)
        charge_power = min(
            pv_power * 0.9,              # 90% of PV (more conservative)
            self.max_power,              # Max charging power
            required_charge_power * 1.3, # Moderate acceleration
            md_headroom * 0.8            # Don't exceed MD (80% of headroom for safety)
        )
        
        # Don't exceed SoE upper limit
        time_interval_h = 5/60
        max_by_soe = ((self.soe_max - soe) / 100) * self.battery_capacity * 1000 / time_interval_h
        charge_power = min(charge_power, max_by_soe)
        
        if charge_power > 100 and current_time.minute % 30 == 0:
            print(f"🔋 {current_time.strftime('%H:%M')} [Constrained] | "
                  f"SoE={soe:.1f}% | "
                  f"Charge={charge_power:.0f}kW | "
                  f"PV={pv_power:.0f}kW | "
                  f"MD30={md30:.0f}kW | "
                  f"MD Headroom={md_headroom:.0f}kW")
        
        return charge_power
    
    def control_decision(self, soe, net_load, current_time, load=None, pv_power=None):
        """
        Main control decision
        
        Returns: Discharge power (kW), positive=discharge, negative=charge
        """
        # Update windows
        self.window_30min.append(net_load)
        self.window_15min.append(net_load)
        self.power_history.append(net_load)
        
        if load is not None:
            self.load_history.append(load)
        if pv_power is not None:
            self.pv_history.append(pv_power)
        
        current_decimal = self._to_decimal_hour(current_time)
        current_minutes = self._minutes_since_midnight(current_time)
        minute = current_time.minute
        
        # ============ Phase 1: Priority Charging Period (PV-priority) ============
        if self.is_priority_charge_period(current_time):
            if load is not None and pv_power is not None:
                charge_power = self.calculate_charge_power_priority(current_time, soe, load, pv_power)
                if charge_power > 0:
                    return -charge_power  # Negative = charging
            return 0
        
        # ============ Phase 2: Constrained Charging Period (MD-aware) ============
        elif self.is_constrained_charge_period(current_time):
            # Pre-Peak check at 17:00
            if current_minutes == self.charge_end_minutes:
                if soe < self.target_soe_before_peak:
                    shortage = self.target_soe_before_peak - soe
                    print(f"⚠️  {current_time.strftime('%H:%M')} Pre-Peak Check: SoE={soe:.1f}% (Short by {shortage:.1f}%)")
                else:
                    print(f"✅ {current_time.strftime('%H:%M')} Pre-Peak Check: SoE={soe:.1f}% - Ready!")
            
            if load is not None and pv_power is not None:
                charge_power = self.calculate_charge_power_constrained(current_time, soe, load, pv_power)
                if charge_power > 0:
                    return -charge_power  # Negative = charging
            return 0
        
        # ============ Phase 3: Pre-Peak Standby (buffer before peak) ============
        elif self.charge_end_hour <= current_decimal < self.peak_start_hour:
            # No charging or discharging, wait for Core Peak period
            return 0
        
        # ============ Phase 4: Core Peak Shaving Period ============
        elif self.is_peak_period(current_time):
            # Record SoE at Peak start
            if self.peak_start_soe is None or current_minutes == self.peak_start_minutes:
                self.peak_start_soe = soe
                print(f"\n{'='*70}")
                print(
                    f"🔥 Core Peak Shaving Starts "
                    f"({self._format_hour(self.peak_start_hour)}-{self._format_hour(self.peak_end_hour)}) "
                    f"| Starting SoE: {soe:.1f}%"
                )
                print(f"{'='*70}")
            
            # SoE safety check: Use energy down to the extended discharge target + safety
            if soe <= self.extended_discharge_target_soe + self.soe_safety_margin:
                print(f"❌ {current_time.strftime('%H:%M')} SoE={soe:.1f}% reached Core Peak minimum reserve, stop discharge for shaving.")
                return 0
            
            # Calculate optimal discharge power
            discharge = self.calculate_optimal_discharge_power(current_time, soe, net_load)
            
            return discharge
        
        # ============ Phase 5: Extended Discharge Period ============
        # Goal: Continue discharge until 15% SoE is hit or charging window resumes
        elif current_decimal >= self.peak_end_hour or current_decimal < self.charge_start_hour:
            
            # Peak end report and reset (22:00:00)
            if current_minutes == self.peak_end_minutes and self.peak_start_soe is not None:
                # Calculate energy used during Core Peak
                total_discharged = (self.peak_start_soe - soe) / 100 * self.battery_capacity
                print(f"\n{'='*70}")
                print(f"🏁 Core Peak Shaving Complete")
                print(f"   Ending SoE: {soe:.1f}% | Energy Discharged: {total_discharged:.2f} MWh")
                print(f"   -> Entering Extended Discharge Mode (Target 15% SoE)...")
                print(f"{'='*70}\n")
                self.peak_start_soe = None # Reset Peak tracking
            
            # SoE safety check (15% target)
            if soe <= self.extended_discharge_target_soe:
                return 0 # Stop discharge at 15%
            
            # Calculate discharge power
            discharge = self.max_power
            
            # Calculate max discharge power based on remaining SoE (to avoid overshoot)
            time_interval_h = 5/60
            max_by_soe = ((soe - self.extended_discharge_target_soe) / 100) * self.battery_capacity * 1000 / time_interval_h * 0.9 # Include efficiency
            
            discharge = min(discharge, max_by_soe)
            
            if discharge > 100 and current_time.minute % 30 == 0:
                print(f"⚡ {current_time.strftime('%H:%M')} [Extended Discharge] | "
                      f"SoE={soe:.1f}% | "
                      f"Discharge={discharge:.0f}kW")
                      
            return discharge
        
        # ============ Phase 6: Default/Error ============
        else:
            return 0


if __name__ == "__main__":
    print("✅ Penang Project Optimized EMS Controller Loaded")
    
    # Test
    controller = AdvancedEMSController(
        target_md=6500,
        max_power=2000,
        battery_capacity=10
    )
    
    print("\n" + "=" * 70)
    print(
        f"🧪 Controller Test "
        f"({controller._format_hour(controller.peak_start_hour)}-"
        f"{controller._format_hour(controller.peak_end_hour)} Core Peak, then Extended)"
    )
    print("=" * 70)
    
    # Simulate Peak period
    test_time = datetime(2025, 1, 1, 17, 55)
    soe = 85
    net_load = 7500
    
    print(f"\nStarting SoE={soe}%...")
    
    # Simulate 17:55 to 23:30 (Core Peak + Extended Discharge)
    for i in range(110):  # 110 × 5-minute intervals = 9 hours 10 mins
        
        # Simulate load drop after 22:00
        if test_time.hour >= 22:
             net_load = 500
        
        discharge = controller.control_decision(soe, net_load, test_time)
        
        # Simulate SoE decrease (use 90% RTE for discharge, 1/0.9 for charge)
        if discharge > 0:
            energy_discharged = discharge * 5/60 / 1000  # MWh
            soe -= (energy_discharged / 10) * 100 / 0.9
        
        test_time += timedelta(minutes=5)
    
    print(f"\nFinal SoE: {soe:.1f}%")
    print(f"Target SoE: {controller.extended_discharge_target_soe}%")
