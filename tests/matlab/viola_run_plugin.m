% viola_run_plugin.m
% ----------------------------------------------------------------------------
% Runs a circuit through VIOLA's OWN generated plug-in code (no re-transcription
% of the algorithm), then exports the input and output so the Python port can be
% compared bit-for-bit. Works for any class, including op-amp + diode(s)
% (MXR, DOD), because it uses exactly the code VIOLA's customizePlugin emits.
%
% It does NOT deploy/compile a VST (no generateAudioPlugin) -- it instantiates
% the generated audioPlugin class directly in MATLAB and processes a signal.
% Requires the Audio Toolbox (which VIOLA needs anyway).
%
% HOW TO RUN: copy this file into viola/windows/ and run it there.
% Change `netlist`, `outNode`, `code` for a different circuit.
% ----------------------------------------------------------------------------
clear; clc; rng(21);
addpath(genpath("Functions"), genpath("Data"));
for d = ["Data/Output/NetlistParsing","Data/Output/Assets", ...
         "Data/Output/PluginCode","Data/Output/Compare"]
    if ~exist(d,'dir'); mkdir(d); end
end

% ---------------- configuration ----------------
netlist = 'MXR';        % try 'MXR' (one_non_lin_opamp) or 'DOD' (non_lin_opamp)
outNode = 'N010';       % MXR -> N010 ; DOD -> N009
code    = 'MXRtest';    % a valid MATLAB identifier for the generated class
fs      = 48000;
dur     = 0.05;
tolSLV  = 1e-5;  tolDSR = 1000;

% ---------------- VIOLA pipeline: parse -> WD model -> generate plug-in ----------------
[Tree, Cotree, outNode, potsData, circuitClass] = netlistParse(netlist, outNode);
fprintf('circuitClass = %s\n', circuitClass);
[typeOrder, params, potsOrder, Q, B, outPath] = ...
    getPluginParams(Tree, Cotree, outNode, potsData, tolSLV, tolDSR);

% ---- shadow Computer Vision Toolbox's insertText (only used to draw the plugin
%      name on the GUI background image; not needed for the numeric export). This
%      lets customizePlugin run without the Computer Vision Toolbox. ----
fid = fopen("insertText.m","w");
fprintf(fid, "function Z = insertText(Z, varargin)\n");
fprintf(fid, "%% stub to skip Computer Vision Toolbox dependency during GUI gen\n");
fprintf(fid, "end\n");
fclose(fid);
clear insertText; rehash;

nPots = size(potsOrder, 1);
potLabels = "K" + string(1:max(nPots,1));
pluginName = string(netlist) + " test";
customizePlugin(circuitClass, code, pluginName, potsOrder, typeOrder, potLabels, Q, B);

addpath("Data/Output/PluginCode");
rehash;                                   % make MATLAB see the just-written class

% ---------------- instantiate + run VIOLA's generated plug-in ----------------
plugin = feval(code);
setSampleRate(plugin, fs);
reset(plugin);

N = round(fs*dur); tt = (0:N-1)'/fs;
in = 0.1 * sin(2*pi*440*tt);              % keep knobs at their defaults (x=0.5)

out = zeros(N,1); blk = 256;
for i = 1:blk:N
    j = min(i+blk-1, N);
    out(i:j) = process(plugin, in(i:j));
end

% ---------------- export ----------------
exportDir = fullfile("Data","Output","Compare_" + string(netlist));
if ~exist(exportDir,'dir'); mkdir(exportDir); end
writematrix(in,  fullfile(exportDir,"input_sine440.csv"));
writematrix(out, fullfile(exportDir,"viola_sine440.csv"));
writematrix(fs,  fullfile(exportDir,"fs.csv"));
fprintf('Exported input/output to %s\n', exportDir);
fprintf('out range [%.5f, %.5f]\n', min(out), max(out));
