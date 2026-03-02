# 📊 MAARGDARSHAN - Complete Data Collection Guide

## Overview

This guide will help you collect ALL the data needed for the rural infrastructure planning system. Follow each section step-by-step.

**Target Region:** Uttarkashi District, Uttarakhand, India

**Total Time Required:** 2-3 hours

---

## 🗺️ **DATASET 1: Digital Elevation Model (DEM)**

### **What:** Terrain elevation data (height above sea level)
### **Format:** GeoTIFF (.tif file)
### **Size:** ~50-200 MB
### **Why:** Calculate slopes, terrain difficulty, elevation profiles

### **Step-by-Step Download:**

#### **Option A: USGS Earth Explorer (Recommended)**

1. **Go to:** https://earthexplorer.usgs.gov/

2. **Create Account (if you don't have one):**
   - Click "Login" (top right)
   - Click "Register for an account"
   - Fill in details, verify email

3. **Search for Uttarkashi:**
   - In the "Search Criteria" tab (left panel)
   - Under "Address/Place"
   - Type: `Uttarkashi, Uttarakhand, India`
   - Click "Show" button
   - Map will zoom to Uttarkashi

4. **Set Date Range:**
   - Click "Date Range" tab
   - Select: Any date (DEM doesn't change)
   - Or leave default

5. **Select Dataset:**
   - Click "Data Sets" tab
   - Expand "Digital Elevation"
   - Expand "SRTM"
   - Check: ✅ **"SRTM 1 Arc-Second Global"** (30m resolution)
   - Click "Results" button at bottom

6. **Download:**
   - You'll see a list of tiles covering Uttarkashi
   - Look for tiles with names like: `N30E078` (Uttarkashi coordinates)
   - Click the download icon (💾)
   - Select "GeoTIFF 1 Arc-second"
   - Save as: `uttarkashi_dem.tif`

#### **Option B: OpenTopography (Alternative)**

1. **Go to:** https://opentopography.org/

2. **Click:** "Data" → "Find Data"

3. **Search:**
   - Type: `Uttarkashi` or coordinates: `30.7268, 78.4354`
   - Select "SRTM GL1 (30m)"

4. **Download:**
   - Select area by drawing rectangle on map
   - Choose output format: GeoTIFF
   - Click "Submit"
   - Download the file

**✅ Expected Result:** `uttarkashi_dem.tif` (50-200 MB)

---

## 🛣️ **DATASET 2: OpenStreetMap (OSM) Data**

### **What:** Road networks, settlements, infrastructure
### **Format:** PBF (Protocol Buffer Format) - compressed OSM data
### **Size:** ~100-500 MB
### **Why:** Extract existing roads, villages, schools, hospitals

### **Step-by-Step Download:**

#### **Option A: Geofabrik (Easiest)**

1. **Go to:** https://download.geofabrik.de/asia/india.html

2. **Navigate:**
   - You'll see a map of India divided into regions
   - Look for "Northern Zone" or "Uttarakhand"

3. **Download Northern Zone:**
   - Click on "Northern Zone" link
   - OR direct link: https://download.geofabrik.de/asia/india/northern-zone-latest.osm.pbf
   - File name: `northern-zone-latest.osm.pbf`
   - Size: ~200-300 MB
   - **Save as:** `northern-zone.osm.pbf`

4. **Alternative - Uttarakhand Only (Smaller):**
   - If available, download just Uttarakhand state
   - Smaller file, faster processing

#### **Option B: BBBike Extract (Custom Area)**

1. **Go to:** https://extract.bbbike.org/

2. **Select Area:**
   - Zoom to Uttarkashi on the map
   - Draw a rectangle around Uttarkashi district
   - Coordinates: 
     - Top-left: 31.2°N, 78.2°E
     - Bottom-right: 30.4°N, 78.8°E

3. **Configure:**
   - Format: Select "OSM PBF"
   - Email: Enter your email
   - Click "Extract"

4. **Download:**
   - You'll receive email with download link (5-10 minutes)
   - Download the file
   - **Save as:** `uttarkashi.osm.pbf`

**✅ Expected Result:** `northern-zone.osm.pbf` or `uttarkashi.osm.pbf` (100-500 MB)

---

## 🌧️ **DATASET 3: Rainfall Data**

### **What:** Historical rainfall patterns, monsoon data
### **Format:** CSV (Excel-compatible)
### **Size:** ~1-10 MB
### **Why:** Assess seasonal risks, monsoon impact

### **Step-by-Step Download:**

#### **India Meteorological Department (IMD)**

1. **Go to:** https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html

2. **OR Direct Data Portal:** https://dsp.imdpune.gov.in/

3. **Navigate:**
   - Click "Rainfall Data"
   - Select "District-wise Rainfall"

4. **Download District Data:**
   - State: Select "Uttarakhand"
   - District: Select "Uttarkashi"
   - Year: Select 2020-2024 (last 5 years)
   - Format: CSV
   - Click "Download"

5. **Alternative - Manual Download:**
   - Go to: https://www.indiawaterportal.org/met_data/
   - Search for "Uttarkashi rainfall"
   - Download available CSV files

6. **What to Download:**
   - `uttarkashi_rainfall_2020.csv`
   - `uttarkashi_rainfall_2021.csv`
   - `uttarkashi_rainfall_2022.csv`
   - `uttarkashi_rainfall_2023.csv`
   - `uttarkashi_rainfall_2024.csv`

#### **Alternative: NASA POWER Data**

1. **Go to:** https://power.larc.nasa.gov/data-access-viewer/

2. **Select Location:**
   - Click on map at Uttarkashi location
   - Or enter coordinates: 30.7268, 78.4354

3. **Select Parameters:**
   - Check: ✅ Precipitation
   - Check: ✅ Temperature (optional)

4. **Select Date Range:**
   - Start: 2020-01-01
   - End: 2024-12-31

5. **Download:**
   - Format: CSV
   - Click "Submit"
   - **Save as:** `uttarkashi_rainfall_nasa.csv`

**✅ Expected Result:** 
- Multiple CSV files OR
- One combined CSV with columns: Date, Rainfall_mm, Location

---

## 🌊 **DATASET 4: Flood Hazard Data**

### **What:** Flood-prone zones, historical flood data
### **Format:** PDF (Atlas) or Shapefile/GeoJSON
### **Size:** ~5-50 MB per file
### **Why:** Identify flood risk areas, avoid dangerous zones

### **Step-by-Step Download:**

#### **National Disaster Management Authority (NDMA)**

1. **Go to:** https://ndma.gov.in/

2. **Navigate:**
   - Click "Publications" or "Resources"
   - Look for "Flood Hazard Atlas"

3. **Download Uttarakhand Flood Atlas:**
   - Search for "Uttarakhand Flood Atlas" or "Uttarkashi Flood"
   - Download PDF
   - **Save as:** `uttarakhand_flood_atlas.pdf`

#### **Alternative: India-WRIS (Water Resources)**

1. **Go to:** https://indiawris.gov.in/wris/

2. **Navigate:**
   - Click "Data" → "Flood Data"
   - Select State: Uttarakhand
   - Select District: Uttarkashi

3. **Download:**
   - Available formats: Shapefile, KML, or PDF
   - Prefer Shapefile if available
   - **Save as:** `uttarkashi_flood_zones.shp` (or .pdf)

#### **Alternative: Bhuvan (ISRO)**

1. **Go to:** https://bhuvan.nrsc.gov.in/

2. **Navigate:**
   - Click "Disaster" → "Flood"
   - Zoom to Uttarkashi
   - Select layers: Flood Hazard Zones

3. **Download:**
   - Click "Download" icon
   - Select format: KML or Shapefile
   - **Save as:** `uttarkashi_flood_bhuvan.kml`

**✅ Expected Result:** 
- `uttarakhand_flood_atlas.pdf` (10-50 MB) OR
- `uttarkashi_flood_zones.shp` + associated files

---

## 🏘️ **DATASET 5: Settlement/Village Data**

### **What:** Village locations, population data
### **Format:** CSV or Shapefile
### **Size:** ~1-5 MB
### **Why:** Identify villages needing road connectivity

### **Step-by-Step Download:**

#### **Census of India**

1. **Go to:** https://censusindia.gov.in/

2. **Navigate:**
   - Click "Data" → "Village Directory"
   - Select State: Uttarakhand
   - Select District: Uttarkashi

3. **Download:**
   - Download village list with coordinates
   - Format: Excel/CSV
   - **Save as:** `uttarkashi_villages.csv`

#### **Alternative: Use OSM Data**

- The OSM PBF file you downloaded already contains settlement data
- We'll extract it programmatically
- No separate download needed

**✅ Expected Result:** `uttarkashi_villages.csv` with columns:
- Village_Name
- Latitude
- Longitude
- Population (optional)

---

## 🛰️ **DATASET 6: Satellite Imagery (Optional)**

### **What:** Visual satellite images for map background
### **Format:** GeoTIFF or use online tiles
### **Size:** Can be large (100+ MB)
### **Why:** Visual context for route planning

### **Option A: Use Online Tiles (Recommended)**

**No download needed!** We'll use:
- Mapbox Satellite API
- Esri World Imagery
- OpenStreetMap tiles

**In code, we reference URLs, not files.**

### **Option B: Download Sentinel-2 Imagery**

1. **Go to:** https://scihub.copernicus.eu/

2. **Create Account:**
   - Register for free Copernicus account

3. **Search:**
   - Draw area around Uttarkashi
   - Select: Sentinel-2 (10m resolution)
   - Date: Recent (2024)
   - Cloud cover: < 10%

4. **Download:**
   - Select tile
   - Download: True Color Image (TCI)
   - **Save as:** `uttarkashi_satellite.tif`

**⚠️ Note:** Satellite imagery files are HUGE (500MB - 2GB). For hackathon, use online tiles instead!

---

## 📁 **FINAL FOLDER STRUCTURE**

After collecting all data, organize like this:

```
data/
├── dem/
│   └── uttarkashi_dem.tif                    (50-200 MB)
├── osm/
│   └── northern-zone.osm.pbf                 (100-500 MB)
├── rainfall/
│   ├── uttarkashi_rainfall_2020.csv          (1-2 MB)
│   ├── uttarkashi_rainfall_2021.csv
│   ├── uttarkashi_rainfall_2022.csv
│   ├── uttarkashi_rainfall_2023.csv
│   └── uttarkashi_rainfall_2024.csv
├── floods/
│   ├── uttarakhand_flood_atlas.pdf           (10-50 MB)
│   └── uttarkashi_flood_zones.shp            (optional)
└── settlements/
    └── uttarkashi_villages.csv               (1-5 MB)
```

**Total Size:** ~200-800 MB (manageable for S3 upload)

---

## ✅ **DATA VALIDATION CHECKLIST**

Before proceeding, verify:

- [ ] DEM file opens in QGIS or similar tool
- [ ] OSM PBF file is not corrupted (check file size > 50MB)
- [ ] Rainfall CSV has proper columns (Date, Rainfall)
- [ ] Flood PDF is readable
- [ ] Village CSV has coordinates

---

## 🚀 **NEXT STEPS**

Once you have all data:

1. **Create S3 bucket** (I'll guide you)
2. **Upload data to S3** (I'll provide script)
3. **Update code to use S3 paths** (I'll modify code)
4. **Deploy backend** (I'll create deployment guide)

---

## 💡 **QUICK START (Minimum Data)**

**If you're short on time, download ONLY these:**

1. **DEM:** `uttarkashi_dem.tif` (USGS Earth Explorer)
2. **OSM:** `northern-zone.osm.pbf` (Geofabrik)
3. **Rainfall:** One CSV file (NASA POWER)

**This is enough for a working demo!**

---

## ❓ **TROUBLESHOOTING**

### **Problem: Can't find Uttarkashi on map**
**Solution:** Use coordinates: `30.7268, 78.4354`

### **Problem: Download requires registration**
**Solution:** Create free account (5 minutes)

### **Problem: File too large**
**Solution:** Download smaller region or lower resolution

### **Problem: Link doesn't work**
**Solution:** Try alternative source listed in each section

---

## 📞 **NEED HELP?**

If you get stuck on any step:
1. Take a screenshot
2. Note which step you're on
3. Ask me for help!

**Let's collect this data together!** 🎯
