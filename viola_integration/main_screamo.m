% main_screamo.m -- gera o estagio de clipping do Tube Screamer (Screamo) via VIOLA
% Rode de dentro de viola/windows/ no MATLAB.
close all; clearvars; clc
rng(21);
addpath( genpath("Functions"), genpath("Data") );
for d = ["Data/Output/NetlistParsing","Data/Output/Assets", ...
         "Data/Output/PluginCode","Data/Output/Compare"]
    if ~exist(d,'dir'); mkdir(d); end
end

%% CONFIG
netlist    = 'screamo';       % Data/Input/Netlist/screamo.txt
outNode    = 'N002';          % saida do amp-op
tolSLV     = 10^(-5);
tolDSR     = 1000;
pluginType = "vst3";
pluginCode = "Screamo";
pluginName = "SCREAMO";
potLabels  = [ "Drive" ];     % 1 knob

%% PIPELINE
[ Tree, Cotree, outNode, potsData, circuitClass ] = netlistParse( netlist, outNode );
[ typeOrder, params, potsOrder, Q, B, outPath ] = getPluginParams( Tree, Cotree, outNode, potsData, tolSLV, tolDSR );
customizePlugin( circuitClass, pluginCode, pluginName, potsOrder, typeOrder, potLabels, Q, B );
disp("Audio plug-in deployment...")
eval( strcat( "generateAudioPlugin ", "-", pluginType, " ", pluginCode ) );
