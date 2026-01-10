#!/bin/bash

if [ "$#" -eq 0 ]; then
    echo "The script expects the course code. Exiting"
    exit 1
fi
COURSE=$1

directory="/mnt/ssd/Applications/ulwazi"
database="ulwazi.db"

# See if database exists
if [ ! -f "${directory}/${database}" ]; then
    echo "Database not found: ${directory}/${database}"
    exit 9
fi

echo "========================================================================"

sqlite3 ${directory}/${database} <<EOF
SELECT standard, code, category, description
FROM ksbs
WHERE standard = '${COURSE}'
EOF

echo "------------------------------------------------------------------------"

sqlite3 ${directory}/${database} <<EOF
SELECT standard, ksb_code, phase, module_number
FROM module_ksbs
WHERE standard = '${COURSE}'
EOF

echo "------------------------------------------------------------------------"

sqlite3 ${directory}/${database} <<EOF
SELECT standard, ksb_code, module_number, day_number, session_number, notes 
FROM session_ksbs
WHERE standard = '${COURSE}'
EOF

echo "------------------------------------------------------------------------"

