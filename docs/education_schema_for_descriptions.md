# Education Database - Table Schemas for Description Writing

This document contains the schema for each table in `education.duckdb`. Use this to write intent-focused descriptions for each table and column.

---

## 1. courses

**Row Count:** 280

### Columns:
- `Course Code` (VARCHAR) NOT NULL
- `Course Title` (VARCHAR) NOT NULL
- `Credits` (BIGINT) NULL
- `Department` (VARCHAR) NULL

### Sample Data:
- Course Code: EDR101, Course Title: Engineering Drawing, Credits: 4, Department: Civil Engineering
- Course Code: BCE101, Course Title: Basic Civil Eng., Credits: 3, Department: Civil Engineering
- Course Code: MAT101, Course Title: M1, Credits: 4, Department: Civil Engineering

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## 2. faculty_info

**Row Count:** 204

### Columns:
- `Faculty ID` (VARCHAR) NOT NULL
- `Name` (VARCHAR) NULL
- `Department` (VARCHAR) NULL
- `Contact Info` (VARCHAR) NULL
- `Courses Taught` (VARCHAR) NULL
- `Course Code` (VARCHAR) NOT NULL

### Sample Data:
- Faculty ID: F5001, Name: Dr. A. Desai, Department: Electronics Engineering, Contact Info: da.@ssmcollege.co.in, Courses Taught: BEE, Course Code: BEE101

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## 3. feedue

**Row Count:** 80

### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Fee Type` (VARCHAR) NOT NULL
- `Amount Due` (BIGINT) NULL
- `Due Date` (TIMESTAMP) NULL

### Sample Data:
- Student ID: TUCIV1032, Fee Type: Transport, Amount Due: 15000, Due Date: 2025-10-01
- Student ID: TUCIV1047, Fee Type: Transport, Amount Due: 15000, Due Date: 2025-10-01

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## 4. grades

**Row Count:** 52,906

### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Course Code` (VARCHAR) NOT NULL
- `Semester` (BIGINT) NOT NULL
- `Marks` (BIGINT) NULL
- `GPA` (DOUBLE) NULL

### Sample Data:
- Student ID: TUCE1001, Course Code: PPS101, Semester: 1, Marks: 65, GPA: 7.87
- Student ID: TUCE1001, Course Code: BEE101, Semester: 1, Marks: 86, GPA: 7.87

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## 5. hostel

**Row Count:** 658

### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Room Number` (BIGINT) NULL
- `Hostel Name` (VARCHAR) NULL
- `Date of Allotment` (VARCHAR) NULL

### Sample Data:
- Student ID: TUCE1002, Room Number: 705, Hostel Name: Girls Hostel, Date of Allotment: 2024-07-01
- Student ID: TUCE1004, Room Number: 250, Hostel Name: Girls Hostel, Date of Allotment: 2024-07-02

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## 6. parent_info

**Row Count:** 1,278

### Columns:
- `Parent ID` (VARCHAR) NOT NULL
- ` Parent Name` (VARCHAR) NULL
- `Student ID` (VARCHAR) NOT NULL

### Sample Data:
- Parent ID: PACE1001, Parent Name: Sathish Acharya, Student ID: TUCE1001
- Parent ID: PACE1002, Parent Name: Bhavya Sinha, Student ID: TUCE1002

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## 7. registration

**Row Count:** 52,906

### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Course Code` (VARCHAR) NOT NULL
- `Semester` (BIGINT) NOT NULL
- `Status` (VARCHAR) NULL

### Sample Data:
- Student ID: TUCE1001, Course Code: PPS101, Semester: 1, Status: Completed
- Student ID: TUCE1001, Course Code: BEE101, Semester: 1, Status: Completed

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## 8. students_info

**Row Count:** 1,278

### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Name` (VARCHAR) NOT NULL
- `Date of Birth` (VARCHAR) NULL
- `Contact Info` (VARCHAR) NULL
- `Batch` (BIGINT) NOT NULL
- `Program/Degree` (VARCHAR) NULL

### Sample Data:
- Student ID: TUCE1001, Name: Nithya Rangaswamy, Date of Birth: 2003-07-15, Contact Info: Nithya_Rangaswamy@ssmcollege.co.in, Batch: 2024, Program/Degree: Computer Engineering
- Student ID: TUCE1002, Name: Madhavi Sharma, Date of Birth: 2003-08-09, Contact Info: Madhavi_Sharma@ssmcollege.co.in, Batch: 2024, Program/Degree: Computer Engineering

### Description (to be filled):
_Write a description that captures the conceptual meaning and purpose of this table in the education system._

---

## Guidelines for Writing Descriptions

When writing descriptions, focus on:

1. **Intent and Meaning**: What does this table represent in the real world?
2. **Conceptual Role**: What is the purpose of this table in the education system?
3. **Avoid Structure**: Don't mention column names, foreign keys, relationships, or technical details
4. **Use Natural Language**: Write as if explaining to someone who doesn't know the database structure



