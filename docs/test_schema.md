## 1. courses
### Columns:
- `Course Code` (VARCHAR) NOT NULL
- `Course Title` (VARCHAR) NOT NULL
- `Credits` (BIGINT) NULL
- `Department` (VARCHAR) NULL

## 2. faculty_info
### Columns:
- `Faculty ID` (VARCHAR) NOT NULL
- `Name` (VARCHAR) NULL
- `Department` (VARCHAR) NULL
- `Contact Info` (VARCHAR) NULL
- `Courses Taught` (VARCHAR) NULL
- `Course Code` (VARCHAR) NOT NULL

## 3. feedue
### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Fee Type` (VARCHAR) NOT NULL
- `Amount Due` (BIGINT) NULL
- `Due Date` (TIMESTAMP) NULL

## 4. grades
### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Course Code` (VARCHAR) NOT NULL
- `Semester` (BIGINT) NOT NULL
- `Marks` (BIGINT) NULL
- `GPA` (DOUBLE) NULL

## 5. hostel
### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Room Number` (BIGINT) NULL
- `Hostel Name` (VARCHAR) NULL
- `Date of Allotment` (VARCHAR) NULL

## 6. parent_info
### Columns:
- `Parent ID` (VARCHAR) NOT NULL
- ` Parent Name` (VARCHAR) NULL
- `Student ID` (VARCHAR) NOT NULL

## 7. registration
### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Course Code` (VARCHAR) NOT NULL
- `Semester` (BIGINT) NOT NULL
- `Status` (VARCHAR) NULL

## 8. students_info
### Columns:
- `Student ID` (VARCHAR) NOT NULL
- `Name` (VARCHAR) NOT NULL
- `Date of Birth` (VARCHAR) NULL
- `Contact Info` (VARCHAR) NULL
- `Batch` (BIGINT) NOT NULL
- `Program/Degree` (VARCHAR) NULL