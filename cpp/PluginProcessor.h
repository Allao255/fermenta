// fermenta VST wrapper -- matches VIOLA's control scheme + channel mode.
// Channel mode is selected at compile time:
//   #define WDFVIOLA_STEREO 0  -> MONO (like VIOLA: 1 circuit, L+R summed, duplicated)
//   #define WDFVIOLA_STEREO 1  -> STEREO (independent circuit per channel)
#pragma once
#ifndef WDFVIOLA_STEREO
  #define WDFVIOLA_STEREO 0        // default: mono, identical to VIOLA
#endif
#include <juce_audio_processors/juce_audio_processors.h>
#include "MxrDsp.h"
using Circuit = fermenta::MxrDsp;      // swap for another generated circuit

class WdfViolaProcessor : public juce::AudioProcessor
{
public:
    WdfViolaProcessor();
    ~WdfViolaProcessor() override = default;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override {}
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    juce::AudioProcessorEditor* createEditor() override
    { return new juce::GenericAudioProcessorEditor(*this); }
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return "fermenta MXR"; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*, int) override;

    juce::AudioProcessorValueTreeState apvts;

private:
    static juce::AudioProcessorValueTreeState::ParameterLayout layout();
    Circuit dsp[2];                              // [0] used in mono, [0]&[1] in stereo
    float lastPot[Circuit::NPG];
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(WdfViolaProcessor)
};
