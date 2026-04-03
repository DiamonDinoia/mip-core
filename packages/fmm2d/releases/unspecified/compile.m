% Compile MEX files for fmm2d
% compile.m runs with cwd set to the package source root

% Add Homebrew path so that gfortran can be found on macOS
setenv('PATH', ['/opt/homebrew/bin:' getenv('PATH')]);

fprintf('Compiling fmm2d MEX files...\n');

% Set up gfortran compiler
make_inc = {
    'FDIR=$$(dirname `gfortran --print-file-name libgfortran.dylib`)'
    'MFLAGS+=-L${FDIR}'
    'OMPFLAGS=-fopenmp';
    'OMPLIBS=-lgomp';
    'FFLAGS=-fPIC -O3 -funroll-loops -std=legacy -w';
    ['MEX=' fullfile(matlabroot, 'bin', 'mex')]
};
writelines(make_inc, 'make.inc');

% Make the static and dynamic libraries
system('make lib');

% Build the MEX file
system('make matlab');

fprintf('fmm2d MEX compilation completed.\n');
