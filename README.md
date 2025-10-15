# ⚡ Energy Management System (EMS) Web Application

A web-based simulator for analyzing and optimizing energy management systems with solar PV and battery storage.

## 🚀 Features

- **Interactive Web Interface**: User-friendly Streamlit-based interface
- **Load Data Upload**: Support for CSV file upload with load profiles
- **PV Generation Modeling**: Realistic solar PV generation simulation
- **EMS Optimization**: Smart battery charging/discharging control
- **Financial Analysis**: ROI, payback period, and savings calculations
- **Interactive Charts**: Real-time visualization with Plotly
- **Optimization Recommendations**: AI-powered suggestions for system improvement
- **Data Export**: Download simulation results as CSV

## 📋 Requirements

- Python 3.8 or higher
- Required packages (see `requirements.txt`)

## 🛠️ Installation

### 1. Create Project Folder

```bash
mkdir penang_ems_webapp
cd penang_ems_webapp
```

### 2. Copy Required Files

Copy these files into the folder:
- `app.py` - Main Streamlit application
- `ems_engine.py` - Backend computation engine
- `ems_controller_penang_optimized.py` - EMS controller (from your Penang project)
- `requirements.txt` - Python dependencies

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 🎮 Usage

### Start the Application

```bash
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`

### Input Configuration

1. **Location Information**
   - Country: e.g., Malaysia
   - City: e.g., Penang

2. **Load Data Upload**
   - Upload CSV file with columns:
     - `timestamp`: Date and time (e.g., "2025-01-01 00:00:00")
     - `load`: Power consumption in kW

3. **System Configuration**
   - PV Capacity (kWp): Total solar capacity
   - Battery Capacity (MWh): Energy storage capacity
   - Max Discharge Power (kW): Maximum battery power output

4. **Target Settings**
   - Target Maximum Demand (kW): Desired peak demand limit

5. **Financial Parameters**
   - Total CAPEX (RM): Capital expenditure
   - MD Charge (RM/kW/month): Maximum demand charge rate
   - Peak Energy Rate (RM/kWh): Peak hour energy rate
   - Off-Peak Rate (RM/kWh): Off-peak energy rate

### Run Simulation

Click the **"🚀 Run Simulation"** button to start the analysis.

### View Results

Results are displayed in multiple tabs:

1. **📈 Power Flow**: Load, PV generation, and grid import visualization
2. **🔋 Battery**: Battery operation, state of energy, and health
3. **💰 Financial**: MD breakdown, payback analysis, and savings
4. **💡 Recommendations**: System optimization suggestions

### Export Results

Click **"📊 Download Simulation Data"** to export results as CSV.

## 📊 CSV File Format

Your load data CSV must follow this format:

```csv
timestamp,load
2025-01-01 00:00:00,7500
2025-01-01 00:05:00,7450
2025-01-01 00:10:00,7600
```

**Requirements:**
- Column names: `timestamp` and `load`
- Timestamp format: `YYYY-MM-DD HH:MM:SS`
- Load values in kW
- Recommended interval: 5 minutes

## 🔧 Configuration

Default system parameters (can be modified in the sidebar):

```python
PV_CAPACITY = 9109.1  # kWp
BATTERY_CAPACITY = 7.5  # MWh
MAX_DISCHARGE = 2000  # kW
TARGET_MD = 6500  # kW
SYSTEM_LOSS = 14%  # PV system losses
INITIAL_SOE = 60%  # Starting battery charge
```

Default financial parameters:

```python
MD_CHARGE = 97.0  # RM/kW/month
PEAK_RATE = 0.31  # RM/kWh
OFFPEAK_RATE = 0.27  # RM/kWh
```

## 📁 Project Structure

```
penang_ems_webapp/
├── app.py                                  # Main Streamlit application
├── ems_engine.py                          # Backend computation engine
├── ems_controller_penang_optimized.py     # EMS controller logic
├── requirements.txt                       # Python dependencies
├── README.md                              # This file
└── data/                                  # (Optional) Sample data folder
    └── penang_load_data.csv              # Sample load data
```

## 🎯 Key Metrics Explained

- **MD Reduction**: Decrease in maximum demand (kW)
- **Annual Savings**: Total yearly cost savings (RM)
- **Payback Period**: Time to recover investment (years)
- **ROI**: Return on investment percentage
- **Battery Cycles**: Equivalent full charge/discharge cycles
- **SoH**: State of Health - battery degradation indicator

## 🔍 Troubleshooting

### Application won't start
```bash
# Make sure Streamlit is installed
pip install streamlit

# Run with full path
python -m streamlit run app.py
```

### CSV upload error
- Check file format matches the required structure
- Ensure timestamp column is parseable
- Verify no missing values in critical columns

### Import errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

## 🌐 Deployment

### Streamlit Community Cloud (recommended)

1. Fork or push this project to your own public GitHub repository.
2. Visit [https://share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, select your repository/branch, set `app.py` as the main file, and deploy.
4. Use the app dashboard to configure secrets under `Settings → Secrets` and optionally map a custom domain.

### Render / Heroku

- A `Procfile` is included so Render and Heroku detect the start command automatically:
  ```
  web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
  ```
- For Render, create a new **Web Service**, point to your repo, choose the default Python runtime, and deploy.
- For Heroku: `heroku create <app-name>`, `git push heroku main`.

### Docker / Self-hosting

1. Build the container: `docker build -t ems-webapp .`
2. Run locally: `docker run -p 8501:8501 ems-webapp`
3. Push the image to your registry and deploy on ECS, Cloud Run, or Kubernetes.

The repository already contains `.streamlit/config.toml`, `Procfile`, and `Dockerfile` for smoother deployment across these platforms.

## 📝 Sample Data

Sample load data format (save as `sample_load.csv`):

```csv
timestamp,load
2025-01-01 00:00:00,7500
2025-01-01 00:05:00,7450
2025-01-01 00:10:00,7600
2025-01-01 00:15:00,7550
2025-01-01 00:20:00,7480
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and enhancement requests.

## 📄 License

This project is licensed under the MIT License.

## 📧 Support

For questions or support, please contact your system administrator.

## 🎉 Acknowledgments

Based on the Penang EMS project implementation.

---

**Version:** 1.0.0  
**Last Updated:** January 2025  
**Built with:** Python, Streamlit, Plotly, Pandas, NumPy
