% compile_packages.m
% Compile prepared MATLAB packages that require compilation.
%
% This script:
% 1. Discovers all .dir directories in build/prepared/
% 2. For each .dir, reads mip.json to check if compilation is needed
% 3. Applies any compiler environment captured at prepare time
% 4. Executes the compile script if specified
% 5. Updates mip.json with compilation duration

function compile_packages()
    % Get the script directory and project root
    scriptDir = fileparts(mfilename('fullpath'));
    projectRoot = fileparts(scriptDir);
    preparedDir = fullfile(projectRoot, 'build', 'prepared');
    fprintf('Starting package compilation process...\n');
    fprintf('Prepared packages directory: %s\n', preparedDir);

    % Check if prepared directory exists
    if ~exist(preparedDir, 'dir')
        error('Prepared packages directory not found: %s', preparedDir);
    end

    % Get all .dir directories
    dirEntries = dir(fullfile(preparedDir, '*.dir'));
    dirPaths = {};
    for i = 1:length(dirEntries)
        if dirEntries(i).isdir
            dirPaths{end+1} = fullfile(preparedDir, dirEntries(i).name);
        end
    end

    if isempty(dirPaths)
        fprintf('No .dir directories found in %s\n', preparedDir);
        return;
    end

    fprintf('Found %d .dir package(s)\n', length(dirPaths));

    % Process each package
    packagesWithCompile = 0;
    for i = 1:length(dirPaths)
        dirPath = dirPaths{i};
        [~, dirName, ~] = fileparts(dirPath);
        mipJsonPath = fullfile(dirPath, 'mip.json');
        if ~exist(mipJsonPath, 'file')
            fprintf('\n%s: mip.json not found - skipping\n', dirName);
            continue;
        end

        mipData = readMipJson(mipJsonPath);
        compileScript = '';
        if isfield(mipData, 'compile_script')
            compileScript = mipData.compile_script;
        end

        if isempty(compileScript)
            fprintf('\n%s: No compilation needed\n', dirName);
            continue;
        end

        % Check if compile script exists
        compileScriptPath = fullfile(dirPath, compileScript);
        if ~exist(compileScriptPath, 'file')
            fprintf('\n%s: Compile script not found: %s - skipping\n', dirName, compileScriptPath);
            % raise error
            error('Compile script not found: %s', compileScriptPath);
        end

        packagesWithCompile = packagesWithCompile + 1;
        fprintf('\n%s: Found %s - compiling...\n', dirName, compileScript);

        % Compile the package
        success = compilePackage(dirPath, dirName, compileScript, mipData);
        if ~success
            error('Compilation failed for %s', dirName);
        end
    end

    fprintf('\nPackages requiring compilation: %d\n', packagesWithCompile);
    fprintf('\nAll packages compiled successfully\n');
end

function success = compilePackage(dirPath, dirName, compileScript, mipData)
    % Compile a single package
    success = false;

    try
        % Save current directory
        originalDir = pwd;

        % Change to package directory
        cd(dirPath);
        originalEnv = struct();
        if isfield(mipData, 'compiler_env')
            originalEnv = applyCompilerEnv(mipData.compiler_env);
        end

        fprintf('  Running %s...\n', compileScript);
        compileStart = tic;

        % Run the compile script directly.
        run(compileScript);

        compileDuration = toc(compileStart);
        fprintf('  Compilation completed in %.2f seconds\n', compileDuration);

        % Restore original directory
        cd(originalDir);
        restoreCompilerEnv(originalEnv);

        % Update mip.json with compilation time
        updateMipJsonCompilationTime(dirPath, compileDuration);

        success = true;

    catch ME
        % Restore original directory on error
        cd(originalDir);
        if exist('originalEnv', 'var')
            restoreCompilerEnv(originalEnv);
        end

        fprintf('  Error during compilation: %s\n', ME.message);
        fprintf('  Stack trace:\n');
        for j = 1:length(ME.stack)
            fprintf('    In %s at line %d\n', ME.stack(j).name, ME.stack(j).line);
        end
        success = false;
    end
end

function mipData = readMipJson(mipJsonPath)
    fid = fopen(mipJsonPath, 'r');
    if fid == -1
        error('Could not open mip.json for reading');
    end
    jsonText = fread(fid, '*char')';
    fclose(fid);
    mipData = jsondecode(jsonText);
end

function originalEnv = applyCompilerEnv(compilerEnv)
    originalEnv = struct();
    envNames = fieldnames(compilerEnv);
    for i = 1:length(envNames)
        envName = envNames{i};
        originalEnv.(envName) = getenv(envName);
        envValue = compilerEnv.(envName);
        if ~ischar(envValue) && ~isstring(envValue)
            envValue = string(envValue);
        end
        setenv(envName, char(envValue));
        fprintf('  Setting %s=%s\n', envName, char(envValue));
    end
end

function restoreCompilerEnv(originalEnv)
    envNames = fieldnames(originalEnv);
    for i = 1:length(envNames)
        envName = envNames{i};
        envValue = originalEnv.(envName);
        if isempty(envValue)
            setenv(envName, '');
        else
            setenv(envName, envValue);
        end
    end
end

function updateMipJsonCompilationTime(dirPath, compileDuration)
    % Update mip.json with compilation duration
    mipJsonPath = fullfile(dirPath, 'mip.json');

    if ~exist(mipJsonPath, 'file')
        fprintf('  Warning: mip.json not found at %s\n', mipJsonPath);
        return;
    end

    try
        % Read existing mip.json
        fid = fopen(mipJsonPath, 'r');
        if fid == -1
            error('Could not open mip.json for reading');
        end
        jsonText = fread(fid, '*char')';
        fclose(fid);

        % Parse JSON
        mipData = jsondecode(jsonText);

        % Update compile_duration
        mipData.compile_duration = round(compileDuration, 2);

        % Write updated JSON
        fid = fopen(mipJsonPath, 'w');
        if fid == -1
            error('Could not open mip.json for writing');
        end
        jsonText = jsonencode(mipData);
        fwrite(fid, jsonText);
        fclose(fid);

        fprintf('  Updated mip.json with compile_duration: %.2fs\n', compileDuration);

    catch ME
        fprintf('  Error updating mip.json: %s\n', ME.message);
    end
end
