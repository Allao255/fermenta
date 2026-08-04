% viola_export.m
% ----------------------------------------------------------------------------
% Runs VIOLA's numeric pipeline on a LINEAR netlist and exports everything the
% Python comparator needs: the input signal, VIOLA's output signal, and the
% intermediate objects (Q, B, port resistances Z, scattering matrix S,
% typeOrder, outPath, fs).
%
% This reproduces VIOLA's EXACT numeric path -- it uses VIOLA's own parser
% (netlistParse/getPluginParams -> Q, B), VIOLA's own port-resistance mapping
% (linearRefScat) and VIOLA's own scattering formula (setMatrices), and runs the
% per-sample loop of LinearPluginTemplate.processBlock. No Audio Toolbox needed,
% so it is robust to run headless. (To instead validate the *compiled* plugin,
% see the note at the bottom.)
%
% HOW TO RUN
%   1. Copy tests/matlab/rc_lowpass.txt into  viola/windows/Data/Input/Netlist/
%   2. Copy this file into  viola/windows/  and run it there.
% ----------------------------------------------------------------------------
clear; clc;
rng(21);                                   % same seed main_windows.m uses
addpath(genpath("Functions"), genpath("Data"));

% ensure VIOLA's output directories exist (not created by a fresh clone)
for d = ["Data/Output/NetlistParsing", "Data/Output/Assets", ...
         "Data/Output/PluginCode", "Data/Output/Compare"]
    if ~exist(d, 'dir'); mkdir(d); end
end

% ---------------- configuration ----------------
netlist = 'rc_lowpass';
outNode = 'N002';
fs      = 48000;
dur     = 0.05;
tolSLV  = 1e-5;   tolDSR = 1000;
exportDir = fullfile("Data","Output","Compare");
if ~exist(exportDir,'dir'); mkdir(exportDir); end

% ---------------- VIOLA parsing + WDF model ----------------
[Tree, Cotree, outNode, potsData, circuitClass] = netlistParse(netlist, outNode);
if ~(strcmp(circuitClass,'lin') || strcmp(circuitClass,'lin_opamp'))
    error('viola_export:notLinear', ...
      'This harness is for LINEAR circuits; got class "%s".', circuitClass);
end
[typeOrder, params, potsOrder, Q, B, outPath] = ...
    getPluginParams(Tree, Cotree, outNode, potsData, tolSLV, tolDSR);

% unwrap struct (single-graph linear case)
Qm = Q.Q;   Bm = B.B;
n  = numel(typeOrder);

% ---------------- port reference resistances Z (linearRefScat) ----------------
% typeOrder: 1 Vin, 2 V, 3 Iin, 4 I, 5 R, 6 C, 7 L
Z = zeros(n,1);
for k = 1:n
    switch typeOrder(k)
        case 1, Z(k) = params(k,1);            % Vin -> 1e-9
        case 2, Z(k) = params(k,2);            % V   -> 1e-9
        case 3, Z(k) = params(k,1);            % Iin -> 1e9
        case 4, Z(k) = params(k,2);
        case 5, Z(k) = params(k,1);            % R
        case 6, Z(k) = 1/(2*params(k,1)*fs);   % C  (bilinear)
        case 7, Z(k) = 2*params(k,1)*fs;       % L  (bilinear)
        otherwise, error('Nonlinear element in a linear harness.');
    end
end
Zmat = diag(Z);

% ---------------- scattering matrix (setMatrices) ----------------
t = size(Qm,1);  l = size(Bm,1);
if t < l
    S = 2*Qm'*((Qm*(Zmat\Qm'))\Qm)/Zmat - eye(n);   % cutset (Q) form
else
    S = eye(n) - 2*Zmat*Bm'*((Bm*Zmat*Bm')\Bm);      % loop (B) form
end

% ---------------- input signals ----------------
N  = round(fs*dur);  tt = (0:N-1)'/fs;
sine  = 0.8*sin(2*pi*1000*tt);
stepv = ones(N,1);  stepv(1) = 0;
k0=20; k1=2000; sweep = 0.5*sin(2*pi*(k0*tt + (k1-k0)/(2*dur)*tt.^2));
signals = struct('sine_1k',sine, 'step',stepv, 'sweep_20_2k',sweep);

% ---------------- per-sample loop (LinearPluginTemplate.processBlock) ----------------
posVin = find(typeOrder==1);  posV = find(typeOrder==2);
posR   = find(typeOrder==5);  posC = find(typeOrder==6);  posL = find(typeOrder==7);
O = outPath;  Volume = 1;

names = fieldnames(signals);
for s = 1:numel(names)
    in = signals.(names{s});
    a = zeros(n,1);  b = zeros(n,1);  out = zeros(N,1);
    for ii = 1:N
        b(posVin) = in(ii);
        if ~isempty(posV), b(posV) = params(posV,1); end
        if ~isempty(posR), b(posR) = 0; end
        if ~isempty(posC), b(posC) = a(posC); end
        if ~isempty(posL), b(posL) = -a(posL); end
        a = S*b;
        out(ii) = Volume * sum( (a(O(:,1)) + b(O(:,1))) .* O(:,2) ) / 2;
    end
    writematrix(in,  fullfile(exportDir, "input_"  + names{s} + ".csv"));
    writematrix(out, fullfile(exportDir, "viola_"  + names{s} + ".csv"));
end

% ---------------- export intermediates ----------------
writematrix(Qm,        fullfile(exportDir,"Q.csv"));
writematrix(Bm,        fullfile(exportDir,"B.csv"));
writematrix(Z,         fullfile(exportDir,"Z.csv"));
writematrix(S,         fullfile(exportDir,"S.csv"));
writematrix(typeOrder, fullfile(exportDir,"typeOrder.csv"));
writematrix(O,         fullfile(exportDir,"outPath.csv"));
writematrix(fs,        fullfile(exportDir,"fs.csv"));
fprintf('Exported %d signals + matrices to %s\n', numel(names), exportDir);

% ----------------------------------------------------------------------------
% OPTIONAL: validate the *compiled* plugin instead of the transcribed loop.
% After running main_windows.m to generate + deploy the plugin class, you can
% instantiate the generated Data/Output/PluginCode/<code>.m object, call its
% processBlock on `in`, and compare -- it should match `out` above to ~eps.
% ----------------------------------------------------------------------------
