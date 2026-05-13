# Test Questions for Table Picker

This document contains a comprehensive set of test questions organized by category.

## Simple Single-Table Queries

1. **Show me all students**
   - Expected: `students_info`

2. **List all courses**
   - Expected: `courses`

3. **Get faculty information**
   - Expected: `faculty_info`

4. **Show student grades**
   - Expected: `grades`

5. **Display hostel details**
   - Expected: `hostel`

## Synonym Matching (Manual Synonyms)

6. **Show me learners**
   - Expected: `students_info`
   - Tests: "learners" → "student" synonym

7. **Find pupil information**
   - Expected: `students_info`
   - Tests: "pupil" → "student" synonym

8. **Get enrollee details**
   - Expected: `students_info`
   - Tests: "enrollee" → "student" synonym

9. **List all classes**
   - Expected: `courses`
   - Tests: "classes" → "course" synonym

10. **Show subjects**
    - Expected: `courses`
    - Tests: "subjects" → "course" synonym

## Multi-Table Queries (with relationships)

11. **Show student grades and their courses**
    - Expected: `students_info`, `grades`, `courses`

12. **Get students with their hostel information**
    - Expected: `students_info`, `hostel`

13. **List students and their registration status**
    - Expected: `students_info`, `registration`

14. **Show courses taught by faculty**
    - Expected: `courses`, `faculty_info`

15. **Get student grades with course details**
    - Expected: `grades`, `courses`, `students_info`

## Aggregation Queries

16. **Count students by batch**
    - Expected: `students_info`

17. **Calculate average GPA by course**
    - Expected: `grades`, `courses`

18. **Show total marks per student**
    - Expected: `grades`, `students_info`

19. **List number of courses per department**
    - Expected: `courses`

## Filtering Queries

20. **Find students in Computer Science batch**
    - Expected: `students_info`

21. **Show courses with more than 3 credits**
    - Expected: `courses`

22. **Get students with GPA above 3.5**
    - Expected: `grades`, `students_info`

23. **List active registrations**
    - Expected: `registration`

## Complex Queries

24. **Show students who are enrolled in courses and their grades**
    - Expected: `students_info`, `registration`, `grades`, `courses`

25. **Get student contact information and their parent details**
    - Expected: `students_info`, `parent_info`

26. **List students with hostel and fee information**
    - Expected: `students_info`, `hostel`, `feedue`

27. **Show course enrollment with student and faculty details**
    - Expected: `courses`, `registration`, `students_info`, `faculty_info`

## Edge Cases

28. **What tables contain student data?**
    - Expected: `students_info`, `grades`, `registration`, `hostel`, `parent_info`, `feedue`

29. **Show academic records**
    - Expected: `grades`, `students_info`

30. **Get educator details**
    - Expected: `faculty_info`

31. **List all educational information**
    - Expected: `students_info`, `courses`, `grades`, `faculty_info`

## Usage

Run the test suite:
```bash
# Full output
python helpers/test_table_picker.py

# Quiet mode (summary only)
python helpers/test_table_picker.py --quiet

# Without embeddings (manual synonyms only)
python helpers/test_table_picker.py --no-embeddings
```


