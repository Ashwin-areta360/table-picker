# 📊 Centrality Visualization in KG

## Overview

The Knowledge Graph visualization now prominently displays centrality metrics for table nodes, making it easy to identify hub tables and understand the structural importance of each table.

---

## 🎨 Visual Enhancements

### 1. **Node Sizing by Centrality**

**Hub tables are larger:**
- Base size: 12px (for tables)
- Hub tables (centrality = 1.0): Up to ~22px
- Size scales with normalized centrality (0.0 → 1.0)

**Visual Effect:**
- `students_info` (centrality: 1.0) → **Large red circle**
- `courses` (centrality: 0.6) → **Medium-sized circle**
- `grades` (centrality: 0.2) → **Smaller circle**

---

### 2. **Node Coloring**

**Hub tables are highlighted:**
- **Red fill** (`#e74c3c`) for hub tables
- **Gold border** (`#f39c12`) with thicker stroke (3px)
- Regular tables: Default color with white border

**Visual Effect:**
- Hub tables stand out immediately
- Easy to spot the most important tables

---

### 3. **Enhanced Tooltips**

**Centrality metrics displayed prominently:**

When you hover over a **table node**, you'll see:

```
┌─────────────────────────────────────┐
│ students_info                       │
│ Type: table                         │
│                                     │
│ 📊 Centrality Metrics:              │
│   Degree: 5.0                       │
│   Normalized: 100.0% (1.0)          │
│   Incoming FKs: 5                   │
│   Outgoing FKs: 0                   │
│   🌟 Hub Table                      │
│   Betweenness: 0.15                 │
└─────────────────────────────────────┘
```

**For non-hub tables:**
```
┌─────────────────────────────────────┐
│ courses                             │
│ Type: table                         │
│                                     │
│ 📊 Centrality Metrics:              │
│   Degree: 3.0                       │
│   Normalized: 60.0% (0.6)           │
│   Incoming FKs: 3                   │
│   Outgoing FKs: 0                   │
└─────────────────────────────────────┘
```

---

## 🔍 How to View Centrality

### Step 1: Rebuild KG (if not done)

```bash
python helpers/build_education_kg_final.py
```

This will:
- Calculate centrality metrics
- Store them in graph nodes
- Generate visualization with centrality data

### Step 2: Open Visualization

```bash
# Open in browser
open education_kg_final/combined_visualization.html
# or
firefox education_kg_final/combined_visualization.html
```

### Step 3: Explore

1. **Look for large red circles** → These are hub tables
2. **Hover over table nodes** → See detailed centrality metrics
3. **Compare sizes** → Larger = higher centrality
4. **Check tooltips** → Full centrality breakdown

---

## 📊 Centrality Metrics Explained

### Degree Centrality
- **What:** Weighted count of FK relationships
- **Formula:** `incoming_fks * 1.0 + outgoing_fks * 0.5`
- **Range:** 0.0 to max in database
- **Example:** `students_info` = 5.0 (5 incoming, 0 outgoing)

### Normalized Centrality
- **What:** Degree normalized to 0-1 scale
- **Formula:** `degree / max_degree`
- **Range:** 0.0 to 1.0
- **Example:** `students_info` = 1.0 (100%), `courses` = 0.6 (60%)

### Incoming FK Count
- **What:** Number of tables that reference this table
- **Meaning:** Higher = more important (core entity)
- **Example:** `students_info` = 5 (referenced by grades, registration, hostel, etc.)

### Outgoing FK Count
- **What:** Number of tables this table references
- **Meaning:** Indicates fact/junction tables
- **Example:** `grades` = 2 (references students_info, courses)

### Hub Table Flag
- **What:** True if normalized centrality >= 0.8
- **Meaning:** Top 20% of tables by centrality
- **Visual:** Red fill, gold border, larger size

### Betweenness Centrality (Optional)
- **What:** How often table appears on shortest paths
- **Meaning:** Identifies junction/bridge tables
- **Range:** 0.0 to 1.0
- **Example:** `grades` might have high betweenness (connects students to courses)

---

## 🎯 Visual Guide

### Hub Tables (High Centrality)
```
🔴 Large red circle with gold border
   Size: ~22px
   Color: #e74c3c (red)
   Border: #f39c12 (gold), 3px
   
   Examples: students_info, courses
```

### Medium Centrality Tables
```
⚪ Medium-sized circle
   Size: ~15-18px
   Color: Default table color
   Border: White, 2px
   
   Examples: grades, registration
```

### Low Centrality Tables
```
⚪ Small circle
   Size: ~12px
   Color: Default table color
   Border: White, 2px
   
   Examples: hostel, feedue, parent_info
```

---

## 💡 Tips for Using the Visualization

1. **Filter by table type** → Click "Tables" filter to see only table nodes
2. **Hover for details** → Move mouse over any table to see full metrics
3. **Compare visually** → Larger/redder = more central
4. **Check connections** → Click a table to highlight its FK relationships
5. **Export image** → Use export button to save visualization

---

## 🔄 After Rebuilding KG

**What you'll see:**

1. **Centrality calculation output:**
   ```
   CALCULATING TABLE CENTRALITY METRICS
   ======================================
     students_info        | degree:  5.0 | norm: 1.00 | in: 5 | out: 0 | 🌟 HUB
     courses              | degree:  3.0 | norm: 0.60 | in: 3 | out: 0 | 
     grades               | degree:  1.0 | norm: 0.20 | in: 0 | out: 2 |
   ```

2. **Visualization file updated:**
   - `education_kg_final/combined_visualization.html`
   - Now includes centrality data in tooltips
   - Hub tables visually highlighted

3. **Open and explore:**
   - Hub tables are large and red
   - Hover to see detailed metrics
   - Compare sizes to understand importance

---

## ✅ Summary

**You can now see centrality in the visualization:**

✅ **Visual indicators:**
- Hub tables: Large, red, gold border
- Size scales with centrality
- Easy to spot important tables

✅ **Detailed metrics:**
- Hover over any table node
- See full centrality breakdown
- Includes degree, normalized, FK counts, hub flag

✅ **No additional steps needed:**
- Just rebuild KG (if not done)
- Open visualization
- Centrality is automatically displayed

---

**Status: Enhanced visualization ready! 🎨**

