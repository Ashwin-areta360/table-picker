# 🔗 Education Database - Relationship Map & Foreign Key Recommendations

## 📊 Current State
**❌ NO FOREIGN KEY CONSTRAINTS DEFINED**
- All tables have no primary keys
- No foreign key relationships
- No referential integrity enforcement

---

## 🎯 Recommended Relationship Map

### **Central Entities (Dimension Tables)**

#### 1. **students_info** (Student Master)
```sql
Primary Key: "Student ID"
Columns: Student ID, Name, Date of Birth, Contact Info, Batch, Program/Degree
Rows: 1,278
```

#### 2. **courses** (Course Catalog)
```sql
Primary Key: "Course Code"
Columns: Course Code, Course Title, Credits, Department
Rows: 280
```

---

### **Relationship Tables (Fact Tables)**

#### 3. **grades** (Student-Course Performance)
```sql
Composite Primary Key: ("Student ID", "Course Code", "Semester")
Foreign Keys:
  - "Student ID" → students_info."Student ID"
  - "Course Code" → courses."Course Code"
Cardinality: Many-to-One with students_info
Cardinality: Many-to-One with courses
Rows: 52,906
```

#### 4. **registration** (Student-Course Enrollment)
```sql
Composite Primary Key: ("Student ID", "Course Code", "Semester")
Foreign Keys:
  - "Student ID" → students_info."Student ID"
  - "Course Code" → courses."Course Code"
Cardinality: Many-to-One with students_info
Cardinality: Many-to-One with courses
Rows: 52,906
```

#### 5. **hostel** (Student Accommodation)
```sql
Primary Key: "Student ID" (one hostel per student)
Foreign Keys:
  - "Student ID" → students_info."Student ID"
Cardinality: One-to-One with students_info
Rows: 658
```

#### 6. **feedue** (Student Fee Records)
```sql
Composite Primary Key: ("Student ID", "Fee Type")
Foreign Keys:
  - "Student ID" → students_info."Student ID"
Cardinality: One-to-Many with students_info (multiple fee types per student)
Rows: 84
```

#### 7. **parent_info** (Student Parents/Guardians)
```sql
Primary Key: "Parent ID"
Foreign Keys:
  - "Student ID" → students_info."Student ID"
Cardinality: Many-to-One with students_info (multiple parents per student)
Rows: 1,278
```

#### 8. **faculty_info** (Faculty Teaching Assignments)
```sql
Primary Key: ("Faculty ID", "Course Code")
Foreign Keys:
  - "Course Code" → courses."Course Code"
Cardinality: Many-to-Many (faculty teaches multiple courses, course has multiple faculty)
Rows: 204
Note: Faculty ID is not linked to a faculty master table (doesn't exist)
```

---

## 🗺️ Visual Entity-Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     CENTRAL ENTITIES                            │
└─────────────────────────────────────────────────────────────────┘

        ┌──────────────────┐              ┌──────────────────┐
        │  students_info   │              │     courses      │
        │  (PK: Student ID)│              │ (PK: Course Code)│
        └────────┬─────────┘              └────────┬─────────┘
                 │                                  │
        ┌────────┴────────────────────────┬────────┴────────┐
        │                                 │                  │
        │                                 │                  │
┌───────▼────────┐              ┌────────▼─────────┐  ┌─────▼──────────┐
│     grades     │              │  registration    │  │ faculty_info   │
│ FK: Student ID │◄────┐        │ FK: Student ID   │  │ FK: Course Code│
│ FK: Course Code│     │        │ FK: Course Code  │  └────────────────┘
└────────────────┘     │        └──────────────────┘
                       │
┌───────────────┐      │        ┌──────────────────┐
│    hostel     │      │        │    parent_info   │
│FK: Student ID │◄─────┤        │  FK: Student ID  │
└───────────────┘      │        │  PK: Parent ID   │
                       │        └──────────────────┘
┌───────────────┐      │
│    feedue     │      │
│FK: Student ID │◄─────┘
└───────────────┘


LEGEND:
═══════
[PK] = Primary Key
[FK] = Foreign Key
──► = One-to-Many relationship
◄─► = Many-to-Many relationship
```

---

## 📋 Detailed Relationship Specifications

### **1. students_info → grades**
- **Type**: One-to-Many
- **Relationship**: One student has many grade records
- **Foreign Key**: `grades."Student ID"` REFERENCES `students_info."Student ID"`
- **Join Type**: INNER (all grades must have valid student)
- **Cascade**: ON DELETE CASCADE (if student deleted, remove grades)

### **2. courses → grades**
- **Type**: One-to-Many
- **Relationship**: One course has many grade records
- **Foreign Key**: `grades."Course Code"` REFERENCES `courses."Course Code"`
- **Join Type**: INNER (all grades must have valid course)
- **Cascade**: ON DELETE RESTRICT (cannot delete course with grades)

### **3. students_info → registration**
- **Type**: One-to-Many
- **Relationship**: One student has many registrations
- **Foreign Key**: `registration."Student ID"` REFERENCES `students_info."Student ID"`
- **Join Type**: INNER (all registrations must have valid student)
- **Cascade**: ON DELETE CASCADE

### **4. courses → registration**
- **Type**: One-to-Many
- **Relationship**: One course has many registrations
- **Foreign Key**: `registration."Course Code"` REFERENCES `courses."Course Code"`
- **Join Type**: INNER (all registrations must have valid course)
- **Cascade**: ON DELETE RESTRICT

### **5. students_info → hostel**
- **Type**: One-to-One (or One-to-Zero-or-One)
- **Relationship**: One student can have one hostel allocation
- **Foreign Key**: `hostel."Student ID"` REFERENCES `students_info."Student ID"`
- **Join Type**: LEFT (not all students have hostel)
- **Cascade**: ON DELETE CASCADE
- **Constraint**: UNIQUE on "Student ID"

### **6. students_info → feedue**
- **Type**: One-to-Many
- **Relationship**: One student can have multiple fee records (different types)
- **Foreign Key**: `feedue."Student ID"` REFERENCES `students_info."Student ID"`
- **Join Type**: LEFT (not all students have pending fees)
- **Cascade**: ON DELETE CASCADE

### **7. students_info → parent_info**
- **Type**: One-to-Many
- **Relationship**: One student can have multiple parents/guardians
- **Foreign Key**: `parent_info."Student ID"` REFERENCES `students_info."Student ID"`
- **Join Type**: LEFT (some students might not have parent info)
- **Cascade**: ON DELETE CASCADE

### **8. courses → faculty_info**
- **Type**: One-to-Many
- **Relationship**: One course can be taught by multiple faculty (different sections/semesters)
- **Foreign Key**: `faculty_info."Course Code"` REFERENCES `courses."Course Code"`
- **Join Type**: INNER (all teaching assignments must have valid course)
- **Cascade**: ON DELETE RESTRICT

---

## 🔢 Cardinality Summary

| From Table | To Table | Relationship | Cardinality |
|------------|----------|--------------|-------------|
| **students_info** | grades | One-to-Many | 1:41 (avg 41 grades per student) |
| **students_info** | registration | One-to-Many | 1:41 (avg 41 registrations per student) |
| **students_info** | hostel | One-to-Zero-or-One | 1:0.51 (51% have hostel) |
| **students_info** | feedue | One-to-Zero-or-Many | 1:0.07 (6.3% have dues) |
| **students_info** | parent_info | One-to-One-or-Many | 1:1 (each student has 1+ parent) |
| **courses** | grades | One-to-Many | 1:189 (avg 189 grades per course) |
| **courses** | registration | One-to-Many | 1:189 (avg 189 registrations per course) |
| **courses** | faculty_info | One-to-Many | 1:0.73 (some courses shared) |

---

## 🛠️ Recommended Primary Keys

```sql
-- 1. Add Primary Key to students_info
ALTER TABLE students_info ADD CONSTRAINT pk_students PRIMARY KEY ("Student ID");

-- 2. Add Primary Key to courses
ALTER TABLE courses ADD CONSTRAINT pk_courses PRIMARY KEY ("Course Code");

-- 3. Add Composite Primary Key to grades
ALTER TABLE grades ADD CONSTRAINT pk_grades PRIMARY KEY ("Student ID", "Course Code", "Semester");

-- 4. Add Composite Primary Key to registration
ALTER TABLE registration ADD CONSTRAINT pk_registration PRIMARY KEY ("Student ID", "Course Code", "Semester");

-- 5. Add Primary Key to hostel
ALTER TABLE hostel ADD CONSTRAINT pk_hostel PRIMARY KEY ("Student ID");

-- 6. Add Composite Primary Key to feedue
ALTER TABLE feedue ADD CONSTRAINT pk_feedue PRIMARY KEY ("Student ID", "Fee Type");

-- 7. Add Primary Key to parent_info
ALTER TABLE parent_info ADD CONSTRAINT pk_parent_info PRIMARY KEY ("Parent ID");

-- 8. Add Composite Primary Key to faculty_info
ALTER TABLE faculty_info ADD CONSTRAINT pk_faculty_info PRIMARY KEY ("Faculty ID", "Course Code");
```

---

## 🔗 Recommended Foreign Keys

```sql
-- grades → students_info
ALTER TABLE grades 
ADD CONSTRAINT fk_grades_student 
FOREIGN KEY ("Student ID") REFERENCES students_info("Student ID") 
ON DELETE CASCADE;

-- grades → courses
ALTER TABLE grades 
ADD CONSTRAINT fk_grades_course 
FOREIGN KEY ("Course Code") REFERENCES courses("Course Code") 
ON DELETE RESTRICT;

-- registration → students_info
ALTER TABLE registration 
ADD CONSTRAINT fk_registration_student 
FOREIGN KEY ("Student ID") REFERENCES students_info("Student ID") 
ON DELETE CASCADE;

-- registration → courses
ALTER TABLE registration 
ADD CONSTRAINT fk_registration_course 
FOREIGN KEY ("Course Code") REFERENCES courses("Course Code") 
ON DELETE RESTRICT;

-- hostel → students_info
ALTER TABLE hostel 
ADD CONSTRAINT fk_hostel_student 
FOREIGN KEY ("Student ID") REFERENCES students_info("Student ID") 
ON DELETE CASCADE;

-- feedue → students_info
ALTER TABLE feedue 
ADD CONSTRAINT fk_feedue_student 
FOREIGN KEY ("Student ID") REFERENCES students_info("Student ID") 
ON DELETE CASCADE;

-- parent_info → students_info
ALTER TABLE parent_info 
ADD CONSTRAINT fk_parent_student 
FOREIGN KEY ("Student ID") REFERENCES students_info("Student ID") 
ON DELETE CASCADE;

-- faculty_info → courses
ALTER TABLE faculty_info 
ADD CONSTRAINT fk_faculty_course 
FOREIGN KEY ("Course Code") REFERENCES courses("Course Code") 
ON DELETE RESTRICT;
```

---

## ⚠️ Data Integrity Issues to Fix

### **1. Column Name with Leading Space**
```
parent_info." Parent Name" (has leading space!)
```
**Fix:** Rename column to remove space

### **2. Missing NOT NULL Constraints**
Key columns should be NOT NULL:
- All Primary Key columns
- All Foreign Key columns

### **3. No Data Type Constraints**
Consider adding:
- CHECK constraints for valid values (e.g., Semester > 0)
- CHECK constraints for GPA range (0.0 - 10.0)
- CHECK constraints for Credits range

---

## 📊 Validation Results

| Relationship | Match Rate | Valid |
|--------------|------------|-------|
| grades → students_info | 100% | ✅ |
| grades → courses | 100% | ✅ |
| registration → students_info | 100% | ✅ |
| registration → courses | 100% | ✅ |
| hostel → students_info | 100% | ✅ |
| feedue → students_info | 100% | ✅ |
| parent_info → students_info | 100% | ✅ |
| faculty_info → courses | 100% | ✅ |

**All relationships have 100% referential integrity!** ✅

---

## 🎯 Next Steps

1. **Backup the database** before making schema changes
2. **Add Primary Keys** to all tables
3. **Add Foreign Keys** with appropriate cascade rules
4. **Fix column name** (Parent Name with leading space)
5. **Add NOT NULL constraints** on key columns
6. **Add CHECK constraints** for data validation
7. **Rerun table_picker** - relationships will be auto-detected!

---

Generated: 2026-01-09
Database: education.duckdb
Status: Ready for schema enhancement

