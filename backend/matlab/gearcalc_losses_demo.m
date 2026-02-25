function gearcalc_losses_demo(input_json_path, output_json_path, py_models_dir)
% GEARCALC_LOSSES_DEMO
% MATLAB wrapper for demo pipeline:
%   input.json -> MATLAB pre-processing -> Python model -> MATLAB post-processing -> output.json
    try
        txt = fileread(input_json_path);
        inp = jsondecode(txt);

        required = {'module_mm','z1','z2','alpha_deg','rpm','torque_Nm','face_width_mm','Ck','Cf','N'};
        for k = 1:numel(required)
            if ~isfield(inp, required{k})
                error('Missing required field: %s', required{k});
            end
        end

        m = double(inp.module_mm); z1 = double(inp.z1); z2 = double(inp.z2);
        alpha_deg = double(inp.alpha_deg); %#ok<NASGU>
        rpm = double(inp.rpm); T = double(inp.torque_Nm); b = double(inp.face_width_mm);
        Ck = double(inp.Ck); Cf = double(inp.Cf); N = double(inp.N);

        r1_mm = 0.5 * z1 * m; r1_m = r1_mm * 1e-3; omega = 2*pi*rpm/60;
        P_in  = omega * T; v_t = omega * r1_m;

        py_in = struct();
        py_in.module_mm = m; py_in.z1 = z1; py_in.z2 = z2; py_in.alpha_deg = double(inp.alpha_deg);
        py_in.rpm = rpm; py_in.torque_Nm = T; py_in.face_width_mm = b; py_in.Ck = Ck; py_in.Cf = Cf; py_in.N = N;
        py_in.P_in_W = P_in; py_in.pitchline_speed_mps = v_t; py_in.features_version = 'losses-demo.features.v1';

        [job_dir, ~, ~] = fileparts(output_json_path);
        py_in_path  = fullfile(job_dir, 'py_in.json');
        py_out_path = fullfile(job_dir, 'py_out.json');

        fid = fopen(py_in_path, 'w'); if fid < 0, error('Could not open py_in.json for writing.'); end
        fwrite(fid, jsonencode(py_in), 'char'); fclose(fid);

        py_script = fullfile(py_models_dir, 'loss_nn_demo.py');
        cmd = sprintf('python "%s" --input "%s" --output "%s"', py_script, py_in_path, py_out_path);
        [status, cmdout] = system(cmd);
        if status ~= 0, error('Python inference script failed.\nCommand output:\n%s', cmdout); end
        if ~isfile(py_out_path), error('Python script did not produce py_out.json'); end

        py_txt = fileread(py_out_path); py_res = jsondecode(py_txt);
        if ~isfield(py_res, 'P_loss_W'), error('Python output missing P_loss_W'); end

        P_loss = double(py_res.P_loss_W);
        eta = 1 - P_loss / max(P_in, 1e-12); eta = max(0, min(1, eta));

        out = struct();
        out.ok = true; out.status = 'success';
        out.message = 'Losses demo computed through MATLAB -> Python pipeline';
        out.schema_version = 'losses-demo.response.v1'; out.mode_used = 'matlab wrapper';

        out.inputs = struct('module_mm',m,'z1',z1,'z2',z2,'alpha_deg',double(inp.alpha_deg), ...
                            'rpm',rpm,'torque_Nm',T,'face_width_mm',b,'Ck',Ck,'Cf',Cf,'N',N);

        out.results = struct();
        out.results.P_in_W = P_in; out.results.P_loss_W = P_loss; out.results.efficiency = eta;
        if isfield(py_res, 'mu_mean'), out.results.mu_mean = double(py_res.mu_mean); else, out.results.mu_mean = NaN; end
        if isfield(py_res, 'theta_rad'), out.results.theta_rad = py_res.theta_rad; else, out.results.theta_rad = []; end
        if isfield(py_res, 'P_fric_W'), out.results.P_fric_W = py_res.P_fric_W; else, out.results.P_fric_W = []; end
        if isfield(py_res, 'notes'), out.results.notes = py_res.notes; else, out.results.notes = ''; end

        fid = fopen(output_json_path, 'w'); if fid < 0, error('Could not open output_json_path for writing.'); end
        fwrite(fid, jsonencode(out), 'char'); fclose(fid);

    catch ME
        errOut = struct('ok',false,'status','error','message',ME.message,'identifier',ME.identifier);
        fid = fopen(output_json_path, 'w');
        if fid >= 0, fwrite(fid, jsonencode(errOut), 'char'); fclose(fid); end
        rethrow(ME);
    end
end
