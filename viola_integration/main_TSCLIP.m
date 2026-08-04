% main_TSCLIP.m  --  generate the op-amp diode clipper (Drive + Level) with VIOLA
% Run this from  viola/windows/  in MATLAB (needs Audio Toolbox + MATLAB Coder
% + a C++ compiler, e.g. the MSVC that ships with Visual Studio 2022).
close all
clearvars
clc

rng( 21 );
addpath( genpath( "Functions" ) , genpath( "Data" ) );

% make sure VIOLA's output folders exist (a fresh clone lacks them)
for d = ["Data/Output/NetlistParsing","Data/Output/Assets", ...
         "Data/Output/PluginCode","Data/Output/Compare"]
    if ~exist(d,'dir'); mkdir(d); end
end

%% CONFIGURATION PARAMETERS
netlist    = 'TSCLIP';                 % Data/Input/Netlist/TSCLIP.txt
outNode    = 'N005';                   % Level pot wiper = output
tolSLV     = 10 ^ ( -5 );
tolDSR     = 1000;
pluginType = "vst3";                   % vst | vst3 | exe | au | auv3
pluginCode = "TSCLIP";                 % DAW code / generated class name
pluginName = "TS CLIPPER";             % title in the plugin UI
potLabels  = [ "Drive" , "Level" ];    % order = XPlog1, XPlog2

%% NETLIST PROCESSING
[ Tree , Cotree , outNode , potsData , circuitClass ] = netlistParse( netlist , outNode );

%% WD MODEL GENERATION
[ typeOrder , params , potsOrder , Q , B , outPath ] = getPluginParams( Tree , Cotree , outNode , potsData , tolSLV , tolDSR );

%% CODE OPTIMIZATION & GUI CUSTOMIZATION
customizePlugin( circuitClass , pluginCode , pluginName , potsOrder , typeOrder , potLabels , Q , B );

%% PLUGIN DEPLOYMENT
disp("Audio plug-in deployment...")
eval( strcat( "generateAudioPlugin " , "-" , pluginType , " " , pluginCode ) );
