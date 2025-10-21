# CMake script to embed a genlib file as a C++ header
# Usage: cmake -DINPUT_FILE=<genlib_file> -DOUTPUT_FILE=<header_file> -DVARIABLE_NAME=<var_name> -P embed_genlib.cmake

if(NOT VARIABLE_NAME)
    set(VARIABLE_NAME "EMBEDDED_GENLIB")
endif()

file(READ "${INPUT_FILE}" GENLIB_CONTENT)

# Escape backslashes and quotes for C++ string
string(REPLACE "\\" "\\\\" GENLIB_CONTENT "${GENLIB_CONTENT}")
string(REPLACE "\"" "\\\"" GENLIB_CONTENT "${GENLIB_CONTENT}")

# Write the header file
file(WRITE "${OUTPUT_FILE}" "// Auto-generated header file - DO NOT EDIT
// Generated from: ${INPUT_FILE}

#ifndef ${VARIABLE_NAME}_H
#define ${VARIABLE_NAME}_H

constexpr const char* ${VARIABLE_NAME} = R\"GENLIB_DELIMITER(
${GENLIB_CONTENT}
)GENLIB_DELIMITER\";

#endif // ${VARIABLE_NAME}_H
")

message("Generated header ${OUTPUT_FILE} with variable ${VARIABLE_NAME}")
