function out = gear_contact_ratio_spur(m, alpha_deg, z1, z2, Ck, Cf, N)
%GEAR_CONTACT_RATIO_SPUR  Involute spur gear transverse contact ratio (2 checks)
%
%   out = gear_contact_ratio_spur(m, alpha_deg, z1, z2, Ck, Cf, N)
%
% Inputs
%   m         : module [mm]
%   alpha_deg : pressure angle [deg]
%   z1, z2    : teeth numbers
%   Ck        : addendum coefficient
%   Cf        : dedendum coefficient
%   N         : sampling points for rack/contact-path discretization
%
% Output (struct)
%   out.ok
%   out.message
%   out.inputs
%   out.geometry
%   out.contact   (eps_LOA, eps_arcs, L_LOA, p_b, t0, tg, arcs, ea, idxP, B/P/C)
%   out.curves    (optional arrays useful for plotting / load-sharing later)

    try
        % ---------- Validation ----------
        validateattributes(m, {'numeric'}, {'scalar','real','finite','positive'});
        validateattributes(alpha_deg, {'numeric'}, {'scalar','real','finite','>',0,'<',90});
        validateattributes(z1, {'numeric'}, {'scalar','integer','>=',3});
        validateattributes(z2, {'numeric'}, {'scalar','integer','>=',3});
        validateattributes(Ck, {'numeric'}, {'scalar','real','finite','positive'});
        validateattributes(Cf, {'numeric'}, {'scalar','real','finite','positive'});
        validateattributes(N, {'numeric'}, {'scalar','integer','>=',200});

        alpha = deg2rad_local(alpha_deg);

        % ---------- Core geometry / raw CP / LOA extraction ----------
        base = compute_involute_loa_profile(m, z1, z2, alpha, Ck, Cf, N);

        % ---------- Contact-ratio metrics ----------
        contact = compute_contact_metrics(base);

        % ---------- Output ----------
        out = struct();
        out.ok = true;
        out.message = 'OK';

        out.inputs = struct( ...
            'm', m, ...
            'alpha_deg', alpha_deg, ...
            'alpha_rad', alpha, ...
            'z1', z1, ...
            'z2', z2, ...
            'Ck', Ck, ...
            'Cf', Cf, ...
            'N', N);

        out.geometry = struct( ...
            'ro1', base.ro1, 'ro2', base.ro2, ...
            'rb1', base.rb1, 'rb2', base.rb2, ...
            'ra1', base.ra1, 'ra2', base.ra2, ...
            'rf1', base.rf1, 'rf2', base.rf2);

        out.contact = contact;

        % Arrays for plotting / downstream usage (keep them if you want future load-sharing backend)
        out.curves = struct( ...
            'xcp', base.xcp, ...
            'ycp', base.ycp, ...
            'xLOA', base.xLOA, ...
            'yLOA', base.yLOA, ...
            'theta_pinion_LOA', contact.theta_pinion_LOA, ...
            'theta_gear_LOA', contact.theta_gear_LOA, ...
            's_LOA', contact.s_LOA, ...
            's_from_pitch', contact.s_from_pitch);

    catch ME
        out = struct();
        out.ok = false;
        out.message = ME.message;
    end
end

% =====================================================================
% Local helpers
% =====================================================================

function base = compute_involute_loa_profile(m, z1, z2, alphaRad, Ck, Cf, N)

    ro1 = z1*m/2;
    ro2 = z2*m/2;
    rb1 = ro1*cos(alphaRad);
    rb2 = ro2*cos(alphaRad);

    hk  = Ck*m;
    hf  = Cf*m;
    ra1 = ro1 + hk;
    ra2 = ro2 + hk;
    rf1 = ro1 - hf;
    rf2 = ro2 - hf;

    % Rack line sampling
    yr = linspace_local(-Cf*m, Ck*m, N);
    xr = -tan(alphaRad) .* yr;

    % dy/dx for rack line x = -tan(a)*y  =>  y = -(1/tan(a))*x
    dydx = (-1 / tan(alphaRad)) * ones(size(yr));

    % Kinematic mapping
    K = -(yr .* dydx + xr);
    theta = K / ro1;

    % Raw contact path in pitch-point frame
    xcp = xr + K;
    ycp = yr;

    % Feasibility mask: inside both addendum circles
    rA1 = hypot(xcp, ycp + ro1);
    rA2 = hypot(xcp, ycp - ro2);
    mask = (rA1 <= ra1) & (rA2 <= ra2);

    % Longest contiguous run
    runs = longest_true_runs(mask);
    if isempty(runs)
        error('LOA extraction failed: no points inside both addendum circles.');
    end

    bestLen = -inf;
    best = runs(1,:);
    for k = 1:size(runs,1)
        i0 = runs(k,1); i1 = runs(k,2);
        L = polyline_length(xcp(i0:i1), ycp(i0:i1));
        if L > bestLen
            bestLen = L;
            best = [i0, i1];
        end
    end

    i0 = best(1); i1 = best(2);

    xLOA = xcp(i0:i1);
    yLOA = ycp(i0:i1);
    thLOA = theta(i0:i1);
    KLOA  = K(i0:i1);

    % Pinion profile points in pitch-point frame (same convention as your JS)
    xPP = zeros(size(xLOA));
    yPP = zeros(size(xLOA));
    for i = 1:numel(xLOA)
        x = xLOA(i);
        y = yLOA(i);
        th = thLOA(i);

        xPP(i) =  x*cos(th) - (y + ro1)*sin(th);
        yPP(i) =  x*sin(th) + (y + ro1)*cos(th) - ro1;
    end

    base = struct( ...
        'm',m,'z1',z1,'z2',z2,'alphaRad',alphaRad,'Ck',Ck,'Cf',Cf, ...
        'ro1',ro1,'ro2',ro2,'rb1',rb1,'rb2',rb2,'ra1',ra1,'ra2',ra2,'rf1',rf1,'rf2',rf2, ...
        'xcp',xcp,'ycp',ycp,'mask',mask, ...
        'thetaFull',theta,'xrFull',xr,'yrFull',yr, ...
        'xLOA',xLOA,'yLOA',yLOA,'thLOA',thLOA,'KLOA',KLOA, ...
        'xrLOA',xLOA - KLOA,'yrLOA',yLOA, ...
        'xPP',xPP,'yPP',yPP, ...
        'loaLen',bestLen, ...
        'pb',pi*m*cos(alphaRad));
end

function contact = compute_contact_metrics(base)

    theta_pinion_LOA = base.thLOA(:);
    theta_gear_LOA   = -(base.ro1/base.ro2) .* theta_pinion_LOA;

    dist2P = base.xLOA(:).^2 + base.yLOA(:).^2;
    [~, idxP] = min(dist2P);

    theta_B  = theta_pinion_LOA(1);
    theta_P  = theta_pinion_LOA(idxP);
    theta_C  = theta_pinion_LOA(end);

    theta2_B = theta_gear_LOA(1);
    theta2_P = theta_gear_LOA(idxP);
    theta2_C = theta_gear_LOA(end);

    arc_GEAR1 = base.ro1 * abs(theta_P - theta_B);   % B->P on pinion pitch circle
    arc_GEAR2 = base.ro2 * abs(theta2_C - theta2_P); % P->C on gear pitch circle
    ea = arc_GEAR1 + arc_GEAR2;

    t0 = pi * base.m;
    tg = t0 * cos(base.alphaRad);   % same numeric value as base pitch in transverse plane

    eps_LOA  = base.loaLen / tg;
    eps_arcs = ea / t0;

    s_LOA = cumulative_arc_length(base.xLOA(:), base.yLOA(:));
    s_from_pitch = s_LOA - s_LOA(idxP);

    contact = struct( ...
        'eps_LOA', eps_LOA, ...
        'eps_arcs', eps_arcs, ...
        'L_LOA', base.loaLen, ...
        'p_b', base.pb, ...
        't0', t0, ...
        'tg', tg, ...
        'arc_GEAR1', arc_GEAR1, ...
        'arc_GEAR2', arc_GEAR2, ...
        'ea', ea, ...
        'idxP', idxP, ... % MATLAB index (1-based)
        'B', [base.xLOA(1), base.yLOA(1)], ...
        'P', [base.xLOA(idxP), base.yLOA(idxP)], ...
        'C', [base.xLOA(end), base.yLOA(end)], ...
        'theta_pinion_LOA', theta_pinion_LOA.', ...
        'theta_gear_LOA', theta_gear_LOA.', ...
        's_LOA', s_LOA.', ...
        's_from_pitch', s_from_pitch.');
end

function a = deg2rad_local(d)
    a = d*pi/180;
end

function v = linspace_local(a, b, n)
    if n <= 1
        v = a;
        return;
    end
    v = a + (0:n-1) * (b-a)/(n-1);
end

function runs = longest_true_runs(mask)
    mask = logical(mask(:));
    runs = zeros(0,2);
    inRun = false;
    s = 1;
    for i = 1:numel(mask)
        if ~inRun && mask(i)
            inRun = true;
            s = i;
        end
        if inRun && (~mask(i) || i == numel(mask))
            if mask(i) && i == numel(mask)
                e = i;
            else
                e = i - 1;
            end
            runs(end+1,:) = [s, e]; %#ok<AGROW>
            inRun = false;
        end
    end
end

function L = polyline_length(x, y)
    dx = diff(x(:));
    dy = diff(y(:));
    L = sum(hypot(dx, dy));
end

function s = cumulative_arc_length(x, y)
    x = x(:); y = y(:);
    s = zeros(size(x));
    if numel(x) < 2, return; end
    s(2:end) = cumsum(hypot(diff(x), diff(y)));
end
