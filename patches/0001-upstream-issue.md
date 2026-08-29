# Upstream issue draft: cesanta/mongoose

Not yet filed. Post the body below to https://github.com/cesanta/mongoose/issues, attaching `0001-upstream-repro.c` (or pasting it inline). Record the issue number here once filed, and note it in `patches/README.md`.

---

**Title:** Built-in TLS: certificate verification fails when an ECDSA signature has a short r or s

**Version:** 7.21 (also present in 7.19) **Component:** built-in TLS (`MG_TLS_BUILTIN`), `mg_tls_verify_cert_signature()` **Platform:** independent. Reproduced on macOS/arm64 and Linux/x86_64 and aarch64.

### Summary

A client configured with `opts.ca` rejects roughly 1 in 128 otherwise valid P-256 certificate chains with `failed to verify CA`. Which chains fail depends only on the CA signature's byte encoding, so the same certificate fails consistently while a regenerated one usually succeeds.

### Cause

`mg_tls_verify_cert_signature()` converts the DER `SEQUENCE { r, s }` signature
into the fixed 64-byte `r||s` buffer that `mg_uecc_verify()` expects:

```c
if (issuer->pubkey.len == 64) {
  const uint32_t N = 32;
  if (a.len > N) a.value += (a.len - N), a.len = N;
  if (b.len > N) b.value += (b.len - N), b.len = N;
  memmove(sig, a.value, N);
  memmove(sig + N, b.value, N);
```

DER INTEGERs are minimally encoded, so for P-256 `r` and `s` are:

- 33 bytes when the top bit is set, with a `0x00` prefix. Handled by the `a.len > N` trim.

- 32 bytes in the common case.

- 31 bytes or fewer when the top byte is zero. **Not handled.**

For the short case the code still copies `N` bytes from a buffer holding fewer than `N`. The value ends up left-aligned rather than left-padded, with trailing bytes read from the following TLV, and verification fails. The copy also reads up to 2 bytes past the INTEGER's contents.

`r` and `s` are uniform modulo the group order, so `P(top byte == 0) = 1/256` for each and `P(either is short) = 2/256 = 0.78%`.

### Reproducer

`repro.c` (attached) embeds a P-256 CA and leaf, valid until 2036, whose CA signature over the leaf has a 31-byte `r`. It runs a mongoose HTTPS server and client in one event loop.

```
cc -DMG_TLS=MG_TLS_BUILTIN -I. repro.c mongoose.c -o repro && ./repro
```

Actual, on 7.21:

```
mongoose.c:783:mg_error        2 4 failed to verify CA
client error: failed to verify CA
FAIL: handshake did not complete
```

Expected: `OK: handshake completed`.

To generate your own failing pair, create P-256 CA and leaf certificates in a loop and stop when `openssl asn1parse` reports an `r` or `s` shorter than 32 bytes in the leaf signature.

### Proposed fix

Zero the buffer and right-align both integers:

```c
if (issuer->pubkey.len == 64) {
  const uint32_t N = 32;
  if (a.len > N) a.value += (a.len - N), a.len = N;
  if (b.len > N) b.value += (b.len - N), b.len = N;
  memset(sig, 0, 2 * N);
  memmove(sig + N - a.len, a.value, a.len);
  memmove(sig + 2 * N - b.len, b.value, b.len);
```

With this change the reproducer prints `OK: handshake completed`.

### The correct handling already exists elsewhere in the file

`mg_tls_recv_cert_verify()` decodes the `ecdsa_secp256r1_sha256` CertificateVerify signature and gets this right:

```c
memset(sig, 0, 64);
...
// Integers may be padded with zeroes
if (r.len > 32) r.value = r.value + (r.len - 32), r.len = 32;
if (s.len > 32) s.value = s.value + (s.len - 32), s.len = 32;

// r or s may be shorter than 32 bytes, "right-justify" (network order)
memmove(sig + (32 - r.len), r.value, r.len);
memmove(sig + 32 + (32 - s.len), s.value, s.len);
```

The proposed fix just brings `mg_tls_verify_cert_signature()` in line with it.
