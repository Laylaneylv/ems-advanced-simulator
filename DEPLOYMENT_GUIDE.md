# 🚀 EMS Web App - Complete Deployment Guide

## 📦 Project Structure

Create the following folder structure:

```
penang_ems_webapp/
├── app.py                                  # Main Streamlit application
├── ems_engine.py                          # Backend computation engine
├── ems_controller_penang_optimized.py     # EMS controller (copy from Penang project)
├── requirements.txt                       # Python dependencies
├── README.md                              # User documentation
├── DEPLOYMENT_GUIDE.md                    # This file
└── data/                                  # (Optional) Sample data
    └── sample_load.csv                    # Sample load data
```

---

## 📋 Step-by-Step Setup

### Step 1: Create Project Folder

```bash
# Create main directory
mkdir penang_ems_webapp
cd penang_ems_webapp

# Create subdirectories
mkdir data
```

### Step 2: Copy Files from Artifacts

Copy the following files from the artifacts:

1. **app.py** - Main Streamlit application
2. **ems_engine.py** - Backend computation engine
3. **requirements.txt** - Python dependencies
4. **README.md** - User documentation

### Step 3: Copy Controller from Penang Project

**IMPORTANT:** Copy the EMS controller from your latest Penang project:

```bash
# From your Penang project folder
cp /path/to/penang_project/ems_controller_penang_optimized.py ./
```

### Step 4: Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Test the Application

```bash
streamlit run app.py
```

The app should open automatically in your browser at `http://localhost:8501`

---

## 🔧 Configuration

### Default System Parameters

Edit in `app.py` sidebar defaults:

```python
pv_capacity = 9109.1  # kWp
battery_capacity = 7.5  # MWh (updated from 10 MWh)
max_discharge = 2000  # kW
target_md = 5500  # kW (updated from 6500 kW)
```

### Default Financial Parameters

```python
capex = 4861625  # RM
md_charge = 97.0  # RM/kW/month
peak_rate = 0.31  # RM/kWh (14:00-22:00, Mon-Fri)
offpeak_rate = 0.27  # RM/kWh
```

---

## 📊 Key Features Update

### Updated Financial Analysis

The app now uses the **improved energy savings calculation** from your latest Penang project:

**Savings Components:**

1. **MD Savings** (Monthly)
   - Formula: `MD_reduction × RM 97/kW/month`

2. **BESS Peak Discharge Savings** (Monthly)
   - Based on actual BESS discharge during 14:00-22:00 (Mon-Fri)
   - Formula: `Peak_discharge_kWh × RM 0.31/kWh`

3. **BESS Off-Peak Discharge Savings** (Monthly)
   - Based on BESS discharge outside peak hours
   - Formula: `OffPeak_discharge_kWh × RM 0.27/kWh`

4. **PV Self-Consumption** (Monthly, for reference only)
   - NOT included in ROI calculations
   - Shown separately in the UI

**ROI Calculation:**
- Uses: MD Savings + BESS Peak + BESS Off-Peak
- Excludes: PV self-consumption (shown separately)

**New Energy Metrics:**
- **Core Peak Shaving Energy**: Total BESS discharge during 18:00-22:00 (MWh)
- **Annual Discharge Energy**: Projected yearly BESS discharge
- **PV Self-Consumption**: Direct PV-to-load energy

---

## 🌐 Deployment Options

### Option 1: Local Deployment (Development)

```bash
streamlit run app.py
```

Access at: `http://localhost:8501`

### Option 2: Streamlit Cloud (Free, Recommended)

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/your-username/ems-webapp.git
   git push -u origin main
   ```

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Set main file: `app.py`
   - Click "Deploy"

3. **Your app will be live at:**
   `https://your-username-ems-webapp-app-xyz123.streamlit.app`

### Option 3: Heroku Deployment

1. **Create Procfile:**
   ```
   web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
   ```

2. **Deploy:**
   ```bash
   heroku create your-ems-app
   git push heroku main
   ```

### Option 4: Docker Deployment

1. **Create Dockerfile:**
   ```dockerfile
   FROM python:3.9-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   EXPOSE 8501
   CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
   ```

2. **Build and run:**
   ```bash
   docker build -t ems-webapp .
   docker run -p 8501:8501 ems-webapp
   ```

---

## 📝 Creating Sample Data

Create `data/sample_load.csv` with this format:

```csv
timestamp,load
2025-01-01 00:00:00,7500
2025-01-01 00:05:00,7450
2025-01-01 00:10:00,7600
2025-01-01 00:15:00,7550
2025-01-01 00:20:00,7480
...
```

You can generate sample data:

```python
import pandas as pd
import numpy as np

# Generate 2 days of data at 5-minute intervals
dates = pd.date_range('2025-01-01', periods=576, freq='5min')
# Add some realistic variation
base_load = 7500
load = base_load + np.random.normal(0, 200, len(dates))

df = pd.DataFrame({'timestamp': dates, 'load': load})
df.to_csv('data/sample_load.csv', index=False)
```

---

## 🔍 Troubleshooting

### Issue 1: Module Import Errors

```bash
# Error: No module named 'streamlit'
pip install -r requirements.txt

# Error: No module named 'ems_controller_penang_optimized'
# Make sure you copied the controller file to the same directory
```

### Issue 2: CSV Upload Fails

**Check:**
- File has 'timestamp' and 'load' columns
- Timestamp format is parseable (YYYY-MM-DD HH:MM:SS)
- No missing values in critical columns
- File size < 200MB (Streamlit limit)

### Issue 3: Simulation Error

**Common causes:**
- Invalid battery capacity (too small)
- Target MD too low (system can't achieve it)
- Insufficient load data (need at least 1 day)

---

## 📊 Performance Optimization

### For Large Datasets (>10,000 points):

1. **Add caching in ems_engine.py:**
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=128)
   def _calculate_pv_cached(self, timestamp_tuple):
       # Cache PV calculations
       pass
   ```

2. **Reduce plot resolution in app.py:**
   ```python
   # Downsample for display
   display_df = results_df.iloc[::10]  # Show every 10th point
   ```

---

## 🔐 Security Considerations

### For Production Deployment:

1. **Add authentication:**
   ```python
   import streamlit_authenticator as stauth
   # Add user login
   ```

2. **Limit file uploads:**
   ```python
   MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
   if uploaded_file.size > MAX_FILE_SIZE:
       st.error("File too large")
   ```

3. **Sanitize inputs:**
   ```python
   # Validate numeric inputs
   if capex < 0:
       st.error("CAPEX must be positive")
   ```

---

## 📈 Feature Roadmap

### Planned Enhancements:

- [ ] PDF report generation
- [ ] Multi-scenario comparison
- [ ] Real-time data integration
- [ ] Advanced optimization algorithms
- [ ] Multi-language support
- [ ] Database integration for history
- [ ] API endpoint for programmatic access

---

## 🤝 Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📞 Support

For issues or questions:

1. Check the troubleshooting section above
2. Review the README.md
3. Contact your system administrator

---

## 📜 License

This project is licensed under the MIT License.

---

## ✅ Pre-Deployment Checklist

Before deploying to production:

- [ ] Test with sample data
- [ ] Test with actual customer data
- [ ] Verify all charts display correctly
- [ ] Check financial calculations accuracy
- [ ] Test CSV download functionality
- [ ] Verify responsive design on mobile
- [ ] Review security settings
- [ ] Set up error logging
- [ ] Prepare user documentation
- [ ] Train end users

---

**Version:** 2.0.0 (Updated with new energy savings calculation)  
**Last Updated:** January 2025  
**Compatible with:** Penang Project v2.0 (with BESS discharge-based savings)