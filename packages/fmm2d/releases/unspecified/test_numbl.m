% Test script for the numbl builds of fmm2d.
% Only rfmm2d is currently supported (lfmm2d/hfmm2d/cfmm2d/stfmm2d are
% not yet ported via numbl), so this test exercises rfmm2d only.
%
% The reference is a direct sum of charge_i * log(|x - x_i|) computed
% in plain MATLAB — we cannot use r2ddir here because that also goes
% through the MEX path which numbl doesn't have.

eps = 1e-6;

ns = 200;
nt = 150;
rng('default');
sources = rand(2, ns);
charges = rand(1, ns);
targ = rand(2, nt);

%% Test rfmm2d (sources, charges, pot)
fprintf('Testing rfmm2d (sources, charges, pot)...\n');
srcinfo = struct();
srcinfo.sources = sources;
srcinfo.charges = charges;
pg = 1;
U1 = rfmm2d(eps, srcinfo, pg);
assert(numel(U1.pot) == ns, 'rfmm2d pot should have ns entries');
assert(~any(isnan(U1.pot(:))), 'rfmm2d pot should not contain NaN');

% Compare against direct sum on a few source points (excluding self).
ntest = 5;
ref = zeros(1, ntest);
for j = 1:ntest
  s = 0;
  for i = 1:ns
    if i == j, continue; end
    dx = sources(1,j) - sources(1,i);
    dy = sources(2,j) - sources(2,i);
    s = s + charges(i) * 0.5 * log(dx*dx + dy*dy);
  end
  ref(j) = s;
end
err = norm(U1.pot(1:ntest) - ref) / norm(ref);
assert(err < 1e-4, sprintf('rfmm2d sources vs direct error too large: %g', err));

%% Test rfmm2d (sources to targets, charges, pot+grad)
fprintf('Testing rfmm2d (targets, charges, pot+grad)...\n');
pg = 0;
pgt = 2;
U1 = rfmm2d(eps, srcinfo, pg, targ, pgt);
assert(all(size(U1.pottarg) == [1, nt]), 'rfmm2d pottarg size mismatch');
assert(all(size(U1.gradtarg) == [2, nt]), 'rfmm2d gradtarg size mismatch');
assert(~any(isnan(U1.pottarg(:))), 'rfmm2d pottarg should not contain NaN');

% Direct-sum reference at a few target points.
ref_pot = zeros(1, ntest);
for j = 1:ntest
  s = 0;
  for i = 1:ns
    dx = targ(1,j) - sources(1,i);
    dy = targ(2,j) - sources(2,i);
    s = s + charges(i) * 0.5 * log(dx*dx + dy*dy);
  end
  ref_pot(j) = s;
end
err = norm(U1.pottarg(1:ntest) - ref_pot) / norm(ref_pot);
assert(err < 1e-4, sprintf('rfmm2d targ pot error too large: %g', err));

fprintf('SUCCESS\n');
