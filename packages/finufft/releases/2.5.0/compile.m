% compile.m
% Compile FINUFFT MEX file for MIP package distribution.
%
% This script is intended to be run by mip-core's compile_packages.m.
% The working directory is the .dir root, which contains:
%   finufft_src/     - full finufft repo (build_only)
%   finufft_matlab/  - matlab/ subdirectory from finufft

fprintf('=== Compiling FINUFFT MEX file ===\n');

scriptDir = fileparts(mfilename('fullpath'));
finufftSrc = fullfile(scriptDir, 'finufft_src');
finufftMatlab = fullfile(scriptDir, 'finufft_matlab');
buildDir = fullfile(scriptDir, 'build_mex');
extraCFlags = strtrim(getenv('MIP_CFLAGS'));
extraCxxFlags = strtrim(getenv('MIP_CXXFLAGS'));
extraLdFlags = strtrim(getenv('MIP_LDFLAGS'));
cmakeGenerator = strtrim(getenv('MIP_CMAKE_GENERATOR'));
cmakeBuildProgram = strtrim(getenv('MIP_CMAKE_BUILD_PROGRAM'));
externalEnvPrefix = makeExternalEnvPrefix(matlabroot, getenv('LD_LIBRARY_PATH'));

% Step 1: Build FINUFFT static libraries using CMake
fprintf('Configuring FINUFFT with CMake...\n');
if ~exist(buildDir, 'dir')
    mkdir(buildDir);
end

generatorArgs = '';
if ~isempty(cmakeGenerator)
    generatorArgs = sprintf(' -G "%s"', cmakeGenerator);
end
if ~isempty(cmakeBuildProgram)
    generatorArgs = sprintf('%s -DCMAKE_MAKE_PROGRAM="%s"', generatorArgs, cmakeBuildProgram);
end

flagArgs = '';
if ~isempty(extraCFlags)
    flagArgs = sprintf('%s -DCMAKE_C_FLAGS="%s"', flagArgs, extraCFlags);
end
if ~isempty(extraCxxFlags)
    flagArgs = sprintf('%s -DCMAKE_CXX_FLAGS="%s"', flagArgs, extraCxxFlags);
end

cmakeCmd = sprintf([ ...
    '%s cmake "%s" -B "%s"' ...
    '%s' ...
    ' -DCMAKE_BUILD_TYPE=Release' ...
    ' -DFINUFFT_USE_OPENMP=OFF' ...
    ' -DFINUFFT_USE_DUCC0=ON' ...
    ' -DFINUFFT_STATIC_LINKING=ON' ...
    ' -DFINUFFT_POSITION_INDEPENDENT_CODE=ON' ...
    ' -DFINUFFT_BUILD_TESTS=OFF' ...
    ' -DFINUFFT_BUILD_EXAMPLES=OFF' ...
    ' -DFINUFFT_ENABLE_INSTALL=OFF' ...
    ' -DFINUFFT_ARCH_FLAGS=""' ...
    '%s'], ...
    externalEnvPrefix, finufftSrc, buildDir, generatorArgs, flagArgs);

runExternalCommand(cmakeCmd, 'CMake configuration');

% Build static library
fprintf('Building FINUFFT static library...\n');
nproc = maxNumCompThreads;
buildCmd = sprintf('%s cmake --build "%s" --target finufft -j%d', externalEnvPrefix, buildDir, nproc);
runExternalCommand(buildCmd, 'CMake build');

% Step 2: Find static libraries
libFinufft = fullfile(buildDir, 'src', 'libfinufft.a');
libCommon = fullfile(buildDir, 'src', 'common', 'libfinufft_common.a');
if ~exist(libFinufft, 'file')
    error('libfinufft.a not found at %s', libFinufft);
end
if ~exist(libCommon, 'file')
    error('libfinufft_common.a not found at %s', libCommon);
end

% Find libducc0.a
[~, ducc0Path] = system(sprintf('find "%s" -name "libducc0.a" -print -quit 2>/dev/null', buildDir));
ducc0Path = strtrim(ducc0Path);

fprintf('Libraries found:\n');
fprintf('  finufft: %s\n', libFinufft);
fprintf('  common:  %s\n', libCommon);
if ~isempty(ducc0Path) && exist(ducc0Path, 'file')
    fprintf('  ducc0:   %s\n', ducc0Path);
end

% Step 3: Compile MEX file
fprintf('Compiling MEX file...\n');

mexSrc = fullfile(finufftMatlab, 'finufft.cpp');
includeDir = fullfile(finufftSrc, 'include');

mexArgs = {mexSrc, ...
    ['-I' includeDir], ...
    '-R2018a', ...
    '-DR2008OO', ...
    libFinufft, libCommon};

if ~isempty(ducc0Path) && exist(ducc0Path, 'file')
    mexArgs{end+1} = ducc0Path;
end

% Platform-specific flags
if isunix && ~ismac
    mexArgs{end+1} = 'LDFLAGS=$LDFLAGS -static-libstdc++ -static-libgcc';
end
if ~isempty(extraLdFlags)
    mexArgs{end+1} = ['LDFLAGS=$LDFLAGS ' extraLdFlags];
end

% Output MEX file into finufft_matlab/ (which is on the addpath)
mexArgs{end+1} = '-output';
mexArgs{end+1} = fullfile(finufftMatlab, 'finufft');

mex(mexArgs{:});

fprintf('=== FINUFFT MEX compilation complete ===\n');

function envPrefix = makeExternalEnvPrefix(matlabRoot, currentLdLibraryPath)
% Strip MATLAB's runtime libraries before invoking host build tools.
cleanLdLibraryPath = stripMatlabPaths(currentLdLibraryPath, matlabRoot);
if isempty(cleanLdLibraryPath)
    envPrefix = 'env -u LD_PRELOAD -u LD_LIBRARY_PATH';
else
    envPrefix = sprintf('env -u LD_PRELOAD LD_LIBRARY_PATH=%s', shellQuote(cleanLdLibraryPath));
end
end

function cleanLdLibraryPath = stripMatlabPaths(ldLibraryPath, matlabRoot)
if isempty(ldLibraryPath)
    cleanLdLibraryPath = '';
    return;
end

pathEntries = strsplit(ldLibraryPath, pathsep);
keepEntries = {};
normalizedMatlabRoot = strrep(matlabRoot, '\', '/');
for i = 1:numel(pathEntries)
    entry = strtrim(pathEntries{i});
    if isempty(entry)
        continue;
    end
    normalizedEntry = strrep(entry, '\', '/');
    if contains(normalizedEntry, normalizedMatlabRoot)
        continue;
    end
    keepEntries{end + 1} = entry; %#ok<AGROW>
end

cleanLdLibraryPath = strjoin(keepEntries, pathsep);
end

function quoted = shellQuote(text)
quoted = ['''' strrep(text, '''', '''"''"''') ''''];
end

function runExternalCommand(command, stepName)
[status, output] = system(command);
fprintf('%s', output);
if status ~= 0
    error('%s failed (exit code %d)', stepName, status);
end
end
