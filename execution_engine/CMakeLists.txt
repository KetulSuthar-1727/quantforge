cmake_minimum_required(VERSION 3.16)

project(QuantForgeExecutionEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(execution_engine
    src/OrderBook.cpp
    src/MatchingEngine.cpp
    src/ExecutionEngine.cpp
)

target_include_directories(execution_engine
    PUBLIC include
)

include(CTest)

add_executable(test_matching_engine
    ../tests/test_matching_engine.cpp
)

target_link_libraries(test_matching_engine
    PRIVATE execution_engine
)

add_test(
    NAME MatchingEngineTests
    COMMAND test_matching_engine
)

add_executable(test_execution_engine
    ../tests/test_execution_engine.cpp
)

target_link_libraries(test_execution_engine
    PRIVATE execution_engine
)

add_test(
    NAME ExecutionEngineTests
    COMMAND test_execution_engine
)