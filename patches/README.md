# Patches to vendored mongoose

`thirdparty/mongoose/` is vendored source, not a submodule. The patches here are
applied to it in place and are already present in the committed tree. They exist
so that a mongoose update does not silently drop them.

Each patched site carries a `cymongoose patch NNNN` comment. To find them:

    grep -rn "cymongoose patch" thirdparty/mongoose/

Because the patches are already applied, `git apply` against the current tree
fails with "patch does not apply". That is expected. To confirm a patch is
present rather than broken:

    git apply --reverse --check patches/0001-tls-pad-short-ecdsa-r-s.patch

The patches apply forward only to pristine upstream sources, which is the state
after step 1 below. Apply them from the repository root; `git apply` assumes
`-p1`, matching the `a/`/`b/` prefixes in the patch files.

## Updating mongoose

1. Copy the new `mongoose.c` and `mongoose.h` into `thirdparty/mongoose/`.
2. For each patch below, check whether upstream fixed it. If so, drop the patch
   file and record that in this README.
3. Re-apply the remaining patches:

       git apply patches/0001-tls-pad-short-ecdsa-r-s.patch

   `git apply` requires exact context. When line drift makes it fail, use
   `patch -p1 --fuzz=3 < patches/0001-...` or apply the change by hand.
4. Run `make test`, then run the verification listed under each patch.

## 0001-tls-pad-short-ecdsa-r-s.patch

Applies to mongoose 7.19 through 7.21. Not reported upstream yet; the report is
drafted in `0001-upstream-issue.md` with a standalone C reproducer in
`0001-upstream-repro.c`. Record the issue number in both files once filed.

`mg_tls_verify_cert_signature()` converts a DER ECDSA signature into the fixed
64-byte `r||s` form that `mg_uecc_verify()` requires. DER INTEGERs are minimally
encoded, so `r` and `s` are 33 bytes when the top bit is set and fewer than 32
bytes when the top byte is zero. The original code handled only the 33-byte
case. For a shorter value it still copied 32 bytes, which left-aligned the
integer and appended a byte read from the following TLV. Verification then
failed.

Consequences without the patch:

- A built-in-TLS client that passes `ca` rejects roughly 0.8% of otherwise valid
  EC certificate chains. `P(r or s short) = 2/256`.
- The failure is per-certificate, not per-platform, so it presents as an
  intermittent CI failure. It first appeared in run 33274015728, in
  `tests/test_tls.py::test_tls_https_handshake`, which is the only test that
  passes `ca` and so the only one that verifies a chain.

Verification: `tests/test_tls.py::test_tls_verify_chain_with_short_sig` pins the
case with the committed certificates in `tests/certs/short_sig_*`, whose CA
signature has a 31-byte `r`. Without the patch it fails with
`TLS error: 'failed to verify CA'`; with it, it passes.
`test_short_sig_fixture_still_has_short_r_or_s` guards the fixture's defining
property, so regenerating those certificates without a short `r` or `s` fails
loudly instead of silently dropping the coverage.

The bug was originally measured by generating 400 P-256 CA and leaf pairs: 4 had
a short `r` or `s`, and all 4 failed before the patch and passed after.
