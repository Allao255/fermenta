cmake_minimum_required(VERSION 3.22)
project(WdfViolaMXR VERSION 0.1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG        8.0.4          # any recent JUCE 7/8 works
    GIT_SHALLOW    TRUE)
FetchContent_MakeAvailable(JUCE)

juce_add_plugin(WdfViolaMXR
    COMPANY_NAME               "Fermenta"
    PLUGIN_MANUFACTURER_CODE   Wdfv
    PLUGIN_CODE                Mxr1
    FORMATS                    VST3 Standalone
    PRODUCT_NAME               "fermenta MXR"
    IS_SYNTH                   FALSE
    NEEDS_MIDI_INPUT           FALSE
    COPY_PLUGIN_AFTER_BUILD    FALSE)   # avoid needing admin to write into Program Files

target_sources(WdfViolaMXR PRIVATE PluginProcessor.cpp)

target_compile_definitions(WdfViolaMXR PUBLIC
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0)

target_link_libraries(WdfViolaMXR
    PRIVATE juce::juce_audio_utils
    PUBLIC  juce::juce_recommended_config_flags
            juce::juce_recommended_lto_flags
            juce::juce_recommended_warning_flags)
