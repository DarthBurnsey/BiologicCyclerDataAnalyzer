# Full Cell Project - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### 1. Create a Full Cell Project (30 seconds)
```
1. Open the application
2. Click "Create New Project" in the sidebar
3. Name: "My Full Cell Test"
4. Project Type: Select "Full Cell"
5. Click Create
```

### 2. Enter Mass Balance Data (2 minutes)
Navigate to **Cell Inputs** tab and enter:

#### Anode (Left Column)
```
Active Material Mass: 10.0 mg
Loading: 2.0 mg/cm²
Electrode Thickness: 50.0 μm
Areal Dimensions: 5.0 cm²
```

#### Cathode (Right Column)
```
Active Material Mass: 12.0 mg
Loading: 2.5 mg/cm²
Electrode Thickness: 60.0 μm
Areal Dimensions: 4.5 cm²
```

✅ **Check**: You should see:
- Overhang Ratio: ~1.111
- N/P Ratio (Estimate): ~1.033
- Color-coded validation message

### 3. Upload Cell Data (1 minute)
Scroll down to **Cell Inputs** expander:
```
1. Upload your cycling file (.csv or .xlsx)
2. Enter cell parameters:
   - Disc loading (mg): Use your actual value
   - % Active material: e.g., 90%
   - Formation Cycles: e.g., 4
   - Test Number: e.g., "Cell i"
3. Set electrolyte, substrate, separator
4. Add formulation data (optional)
```

### 4. Save & Analyze (1 minute)
```
1. Scroll to bottom of Cell Inputs
2. Enter Experiment Name: "Test 1"
3. Click "Save Experiment"
4. Navigate to "Plots" tab
```

### 5. View Full Cell Analysis (30 seconds)
In the **Plots** tab, scroll to bottom:

**🔋 Full Cell Performance Analysis**
- ⚡ High-Precision CE Tracking (99-100% range)
- ⚡ Energy Efficiency Plot
- 📊 N/P Ratio Analysis with validation

---

## ⚠️ Key Validation Checks

### N/P Ratio Interpretation
| Display | Meaning | Action |
|---------|---------|--------|
| 🚨 Red (< 1.0) | CRITICAL - Plating risk | Increase anode mass or capacity |
| ⚠️ Orange (1.0-1.05) | WARNING - Low margin | Consider increasing N/P ratio |
| ✅ Green (≥ 1.05) | SAFE | Good to proceed |

### Overhang Ratio
| Value | Status | Note |
|-------|--------|------|
| < 1.0 | ⚠️ Warning | Anode smaller than cathode |
| 1.02-1.10 | ✅ Good | Standard range |
| > 1.10 | ✅ Safe | Conservative design |

---

## 📊 Reading the Plots

### High-Precision CE Plot
- **Y-axis**: 99.0% - 100.0% (high precision)
- **Green line (99.5%)**: Excellent performance
- **Orange line (99.0%)**: Good performance
- **Red line (98.5%)**: Concerning - investigate degradation

**What to look for:**
- Stable CE ≥ 99.5% = excellent cell health
- Declining CE trend = early warning of degradation
- CE < 99.0% = cell issues likely

### Energy Efficiency Plot
- **Y-axis**: Typically 85% - 100%
- **Green line (95%)**: Excellent
- **Orange line (90%)**: Good
- **Red line (85%)**: Poor - voltage polarization issues

**What to look for:**
- EE 2-5% lower than CE is normal
- Widening CE-EE gap = increasing polarization
- EE < 90% = investigate cell degradation

### N/P Ratio Analysis
- Shows calculated N/P from your formation data
- Compares estimate vs. actual measured ratio
- Provides validation warnings
- Guides sensitivity analysis for multi-experiment studies

---

## 🔧 Troubleshooting

### "N/P Ratio: To be calculated"
✅ **Solution**: Upload cycling data first

### Full Cell section not showing
✅ **Solution**: 
1. Click project name in sidebar
2. Select "Change Type" 
3. Choose "Full Cell"

### Overhang warning showing
✅ **Solution**: Verify areal dimensions are correct (anode should be larger)

---

## 💡 Pro Tips

1. **Start with N/P ~1.10-1.15** for balanced performance and safety
2. **Monitor CE in 99-100% range** for early degradation detection
3. **Track EE alongside CE** for comprehensive cell health assessment
4. **Use Comparison tab** to analyze N/P ratio sensitivity across experiments
5. **Export data** includes all Full Cell metrics for external analysis

---

## 📚 Need More Help?

- **Full Documentation**: See `FULL_CELL_IMPLEMENTATION.md`
- **Inline Help**: Hover over 🛈 icons in the application
- **Tooltips**: Available on all input fields
- **Validation Messages**: Color-coded warnings guide you

---

## ✅ Success Checklist

After setup, you should see:
- [ ] Mass Balance section visible in Cell Inputs
- [ ] Overhang ratio calculated and displayed
- [ ] N/P ratio estimate shown (green checkmark)
- [ ] Cell cycling data uploaded
- [ ] N/P ratio calculated from formation data
- [ ] Full Cell Performance Analysis section in Plots tab
- [ ] High-precision CE plot rendered
- [ ] Energy Efficiency plot rendered
- [ ] N/P validation messages displayed

**All checked?** 🎉 You're ready to analyze Full Cell data!

---

**Happy analyzing!** 🔋⚡
