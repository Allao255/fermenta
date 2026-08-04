% viola_export_nl.m
% ----------------------------------------------------------------------------
% Same idea as viola_export.m but for a circuit with ONE diode (one_non_lin),
% e.g. DEMO. Reproduces VIOLA's exact numeric path: VIOLA's parser (Q,B,params),
% VIOLA's diode adaptation (Thevenin port resistance), and VIOLA's own
% extendedSchockleyDiodeScat / enhancedOmegaW (both on the function path).
%
% HOW TO RUN
%   1. DEMO.txt already ships in viola/windows/Data/Input/Netlist/
%   2. Copy this file into viola/windows/ and run it there.
% ----------------------------------------------------------------------------
clear; clc;
rng(21);
addpath(genpath("Functions"), genpath("Data"));
for d = ["Data/Output/NetlistParsing","Data/Output/Assets", ...
         "Data/Output/PluginCode","Data/Output/Compare"]
    if ~exist(d,'dir'); mkdir(d); end
end

netlist = 'DEMO';
outNode = 'N003';
fs      = 48000;  dur = 0.05;
tolSLV  = 1e-5;   tolDSR = 1000;
exportDir = fullfile("Data","Output","Compare_DEMO");
if ~exist(exportDir,'dir'); mkdir(exportDir); end

[Tree, Cotree, outNode, potsData, circuitClass] = netlistParse(netlist, outNode);
fprintf('circuitClass = %s\n', circuitClass);
[typeOrder, params, potsOrder, Q, B, outPath] = ...
    getPluginParams(Tree, Cotree, outNode, potsData, tolSLV, tolDSR);
Qm = Q.Q;  Bm = B.B;  n = numel(typeOrder);

% ---- linear port resistances Z (linearRefScat mapping) ----
Z = zeros(n,1);
for k = 1:n
    switch typeOrder(k)
        case 1, Z(k) = params(k,1);            % Vin -> 1e-9
        case 2, Z(k) = params(k,2);
        case 5, Z(k) = params(k,1);            % R
        case 6, Z(k) = 1/(2*params(k,1)*fs);   % C
        case 7, Z(k) = 2*params(k,1)*fs;       % L
        case 8, Z(k) = 1;                      % diode placeholder (set below)
    end
end

% ---- diode adapted port resistance = Thevenin R of the linear network ----
% Build incidence from the ordered edges (same order as Q/B/typeOrder).
edges = [Tree.tree.Edges ; Cotree.cotree.Edges];
EN = edges.EndNodes;                 % node ids (+1 offset), n x 2
allNodes = unique(EN(:));
nN = numel(allNodes);
nodeMap = containers.Map(num2cell(allNodes'), num2cell(1:nN));
posD = find(typeOrder==8);
Y = zeros(nN);
for k = 1:n
    if k==posD, continue; end
    g = 1/Z(k);
    a = nodeMap(EN(k,1));  b = nodeMap(EN(k,2));
    Y(a,a)=Y(a,a)+g; Y(b,b)=Y(b,b)+g; Y(a,b)=Y(a,b)-g; Y(b,a)=Y(b,a)-g;
end
da = nodeMap(EN(posD,1));  db = nodeMap(EN(posD,2));
keep = setdiff(1:nN, db);
Yr = Y(keep,keep);
rhs = zeros(numel(keep),1);  rhs(keep==da) = 1;
v = Yr\rhs;
Z_D = v(keep==da);
Z(posD) = Z_D;
fprintf('Z_D (adapted diode port resistance) = %.6f ohm\n', Z_D);

Zmat = diag(Z);

% ---- scattering matrix (setMatrices) ----
t = size(Qm,1); l = size(Bm,1);
if t < l
    S = 2*Qm'*((Qm*(Zmat\Qm'))\Qm)/Zmat - eye(n);
else
    S = eye(n) - 2*Zmat*Bm'*((Bm*Zmat*Bm')\Bm);
end
fprintf('S(d,d) = %.3e (should be ~0, adapted)\n', S(posD,posD));

% ---- signals ----
N = round(fs*dur); tt=(0:N-1)'/fs;
signals = struct( ...
  'sine_250_0v2', 0.2*sin(2*pi*250*tt), ...
  'sine_1k_0v5',  0.5*sin(2*pi*1000*tt), ...
  'sine_100_2v0', 2.0*sin(2*pi*100*tt), ...
  'sweep_20_2k',  0.5*sin(2*pi*(20*tt+(2000-20)/(2*dur)*tt.^2)) );

posVin=find(typeOrder==1); posR=find(typeOrder==5);
posC=find(typeOrder==6);   posL=find(typeOrder==7);
O = outPath;  Volume = 1;
Pd = params(posD,:);   % [Is eta Vth Rs Rp]

names = fieldnames(signals);
for s = 1:numel(names)
    in = signals.(names{s});  a=zeros(n,1); b=zeros(n,1); out=zeros(N,1);
    for ii=1:N
        b(posVin)=in(ii);
        if ~isempty(posR), b(posR)=0; end
        if ~isempty(posC), b(posC)=a(posC); end
        if ~isempty(posL), b(posL)=-a(posL); end
        b(posD) = extendedSchockleyDiodeScat(S(posD,:)*b, Z(posD), ...
                     Pd(1),Pd(2),Pd(3),Pd(4),Pd(5));
        a = S*b;
        out(ii) = Volume*sum((a(O(:,1))+b(O(:,1))).*O(:,2))/2;
    end
    writematrix(in,  fullfile(exportDir,"input_"+names{s}+".csv"));
    writematrix(out, fullfile(exportDir,"viola_"+names{s}+".csv"));
end
writematrix(Qm,fullfile(exportDir,"Q.csv"));  writematrix(Bm,fullfile(exportDir,"B.csv"));
writematrix(Z, fullfile(exportDir,"Z.csv"));  writematrix(S, fullfile(exportDir,"S.csv"));
writematrix(typeOrder,fullfile(exportDir,"typeOrder.csv"));
writematrix(O,fullfile(exportDir,"outPath.csv")); writematrix(fs,fullfile(exportDir,"fs.csv"));
writematrix(Z_D,fullfile(exportDir,"Z_D.csv"));
fprintf('Exported %d signals + matrices to %s\n', numel(names), exportDir);
