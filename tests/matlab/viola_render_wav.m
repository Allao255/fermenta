% viola_render_wav.m
% ----------------------------------------------------------------------------
% Hear VIOLA's pedal WITHOUT deploying a VST (no MATLAB Coder / Visual Studio
% needed). It generates VIOLA's plug-in code, instantiates it in MATLAB, runs a
% WAV file through it and writes the processed WAV. Uses only audioread/
% audiowrite (base MATLAB) + Audio Toolbox (for the audioPlugin class).
%
% HOW TO RUN: copy into viola/windows/ , set the config below, run.
% ----------------------------------------------------------------------------
clear; clc; rng(21);
addpath(genpath("Functions"), genpath("Data"));
for d = ["Data/Output/NetlistParsing","Data/Output/Assets", ...
         "Data/Output/PluginCode","Data/Output/Compare"]
    if ~exist(d,'dir'); mkdir(d); end
end

% ---------------- configuration ----------------
netlist = 'MXR';           % 'MXR', 'DOD', 'DEMO', ...
outNode = 'N010';          % MXR->N010, DOD->N009, DEMO->N003
code    = 'MXRrender';     % any valid MATLAB identifier
inWav   = 'guitarra.wav';  % your input WAV (put it in viola/windows/)
outWav  = 'saida_mxr.wav'; % output WAV to be written
driveDB = 12;              % gain before the circuit
volDB   = -6;              % gain after the circuit
tolSLV  = 1e-5;  tolDSR = 1000;

% ---------------- VIOLA: parse + generate plug-in ----------------
[Tree, Cotree, outNode, potsData, circuitClass] = netlistParse(netlist, outNode);
[typeOrder, params, potsOrder, Q, B, outPath] = ...
    getPluginParams(Tree, Cotree, outNode, potsData, tolSLV, tolDSR);

% shadow Computer Vision Toolbox's insertText (GUI-only; not needed here)
fid=fopen("insertText.m","w");
fprintf(fid,"function Z = insertText(Z, varargin)\nend\n"); fclose(fid);
clear insertText; rehash;

nPots = size(potsOrder,1);
customizePlugin(circuitClass, code, string(netlist)+" render", ...
                potsOrder, typeOrder, "K"+string(1:max(nPots,1)), Q, B);
addpath("Data/Output/PluginCode"); rehash;

% ---------------- instantiate + process the WAV ----------------
plugin = feval(code);
[x, fs] = audioread(inWav);
if size(x,2) > 1, x = mean(x,2); end          % mono
setSampleRate(plugin, fs);                    % tune circuit to the file's rate
reset(plugin);

g = 10^(driveDB/20);  vg = 10^(volDB/20);
N = size(x,1);  out = zeros(N,1);  blk = 256;
for i = 1:blk:N
    j = min(i+blk-1, N);
    out(i:j) = vg * process(plugin, g * x(i:j));
end

pk = max(abs(out));  if pk > 1, out = out / pk; end   % avoid clipping
audiowrite(outWav, out, fs);
fprintf('Wrote %s  (%d samples, %.0f Hz). Circuit: %s\n', outWav, N, fs, circuitClass);
