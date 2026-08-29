# Patches to vendored mongoose

`thirdparty/mongoose/` is vendored source, not a submodule. Patches in this
directory are applied to it in place and are already present in the committed
tree. They exist so that a mongoose update does not silently drop them.

**There are currently no active patches.** The vendored tree is pristine
mongoose 7.23.

Each patched site carries a `cymongoose patch NNNN` comment. To find them:

    grep -rn "cymongoose patch" thirdparty/mongoose/

Because patches are already applied, `git apply` against the current tree fails
with "patch does not apply". That is expected. To confirm a patch is present
rather than broken:

    git apply --reverse --check patches/NNNN-name.patch

Patches apply forward only to pristine upstream sources, which is the state
after step 1 below. Apply them from the repository root; `git apply` assumes
`-p1`, matching the `a/`/`b/` prefixes in the patch files.

## Updating mongoose

1. Copy the new `mongoose.c` and `mongoose.h` into `thirdparty/mongoose/`.
2. Bump `MONGOOSE_VERSION` in `CMakeLists.txt`. The build fails if it disagrees
   with `MG_VERSION` in the new header.
3. For each active patch, check whether upstream fixed it. If so, delete the
   patch file and record it under "Retired patches" below.
4. Re-apply the remaining patches:

       git apply patches/NNNN-name.patch

   `git apply` requires exact context. When line drift makes it fail, use
   `patch -p1 --fuzz=3 < patches/NNNN-...` or apply the change by hand.
5. Run `make test`, then run the verification listed under each patch.

## Retired patches

### 0001-tls-pad-short-ecdsa-r-s.patch

Applied to mongoose 7.19 through 7.21. Fixed upstream in 7.22 as
[CVE-2026-52071](https://github.com/cesanta/mongoose/releases/tag/7.22),
"mg_tls_verify_cert_signature OOB read for short ECDSA integers". Patch file
deleted during the 7.21 to 7.23 upgrade; upstream's fix is functionally
identical.

`mg_tls_verify_cert_signature()` converts a DER ECDSA signature into the fixed
64-byte `r||s` form that `mg_uecc_verify()` requires. DER INTEGERs are minimally
encoded, so `r` and `s` are 33 bytes when the top bit is set and fewer than 32
bytes when the top byte is zero. The original code handled only the 33-byte
case. For a shorter value it still copied 32 bytes, which left-aligned the
integer and appended a byte read from the following TLV. Verification then
failed for roughly 0.8% of otherwise valid EC chains, `P(r or s short) = 2/256`.

`tests/test_tls.py::test_tls_verify_chain_with_short_sig` and
`test_short_sig_fixture_still_has_short_r_or_s` are retained as upstream
regression coverage. They pin the case with the committed certificates in
`tests/certs/short_sig_*`, whose CA signature has a 31-byte `r`.

The same defect is still present in 7.23 for secp384r1, which 7.22 added:
the `issuer->pubkey.len == 96` branch copies `N = 48` bytes without padding.
`MG_UECC_SUPPORTS_secp384r1` defaults to 1, so it is reachable.
`0001-upstream-issue.md` and `0001-upstream-repro.c` are kept for retargeting
that report at the P-384 branch; both currently describe the closed P-256 case.
