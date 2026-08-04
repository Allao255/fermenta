#include "PluginProcessor.h"

juce::AudioProcessorValueTreeState::ParameterLayout WdfViolaProcessor::layout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> p;
    p.push_back(std::make_unique<juce::AudioParameterFloat>(
        "volume", "Volume", juce::NormalisableRange<float>(0.f, 2.f, 0.001f), 1.f));
    for (int k = 0; k < Circuit::NPOTS; ++k)
        p.push_back(std::make_unique<juce::AudioParameterFloat>(
            "pot" + juce::String(k), juce::String(Circuit::POTLABEL[k]),
            juce::NormalisableRange<float>(0.f, 1.f, 0.001f), 0.5f));
    p.push_back(std::make_unique<juce::AudioParameterBool>("enable", "Enable", true));
    return { p.begin(), p.end() };
}

WdfViolaProcessor::WdfViolaProcessor()
    : AudioProcessor(BusesProperties()
        .withInput ("Input",  juce::AudioChannelSet::stereo(), true)
        .withOutput("Output", juce::AudioChannelSet::stereo(), true)),
      apvts(*this, nullptr, "PARAMS", layout())
{
    for (int k = 0; k < Circuit::NPG; ++k) lastPot[k] = -1.f;
}

void WdfViolaProcessor::prepareToPlay(double sampleRate, int)
{
    for (auto& d : dsp) { d.reset(); d.setSampleRate(sampleRate); }
    for (int k = 0; k < Circuit::NPG; ++k) lastPot[k] = -1.f;
}

void WdfViolaProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    const int nCh = buffer.getNumChannels();
    const int n = buffer.getNumSamples();

    if (! apvts.getRawParameterValue("enable")->load())
        return;                                              // bypass

    for (int k = 0; k < Circuit::NPOTS; ++k)                 // knob moves at block rate
    {
        float x = apvts.getRawParameterValue("pot" + juce::String(k))->load();
        if (x != lastPot[k]) { for (auto& d : dsp) d.setPot(k, (double) x); lastPot[k] = x; }
    }
    const double vol = (double) apvts.getRawParameterValue("volume")->load();

#if WDFVIOLA_STEREO
    // STEREO: each channel through its own circuit instance
    const int use = juce::jmin(nCh, 2);
    for (int ch = 0; ch < use; ++ch)
    {
        float* x = buffer.getWritePointer(ch);
        for (int s = 0; s < n; ++s)
            x[s] = (float) (vol * dsp[ch].process((double) x[s]));
    }
    for (int ch = use; ch < nCh; ++ch) buffer.clear(ch, 0, n);
#else
    // MONO (like VIOLA): sum inputs to mono, process ONE circuit, copy to all outputs
    for (int s = 0; s < n; ++s)
    {
        double in = 0.0;
        for (int ch = 0; ch < nCh; ++ch) in += buffer.getSample(ch, s);
        if (nCh > 0) in /= nCh;
        double y = vol * dsp[0].process(in);
        for (int ch = 0; ch < nCh; ++ch) buffer.setSample(ch, s, (float) y);
    }
#endif
}

void WdfViolaProcessor::getStateInformation(juce::MemoryBlock& dest)
{ if (auto xml = apvts.copyState().createXml()) copyXmlToBinary(*xml, dest); }
void WdfViolaProcessor::setStateInformation(const void* data, int size)
{ if (auto xml = getXmlFromBinary(data, size)) apvts.replaceState(juce::ValueTree::fromXml(*xml)); }

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new WdfViolaProcessor(); }
