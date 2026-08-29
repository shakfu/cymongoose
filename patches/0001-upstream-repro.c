// Reproducer for mongoose built-in TLS: certificate chain verification fails
// when the CA's ECDSA signature has a short r or s.
//
//   cc -DMG_TLS=MG_TLS_BUILTIN -I. repro.c mongoose.c -o repro && ./repro
//
// Expected: "OK: handshake completed"
// Actual:   "FAIL: ..." with "failed to verify CA" logged.

#include "mongoose.h"

// P-256 CA and leaf, valid 10 years. The CA's signature over the leaf has a
// 31-byte r (leading zero byte dropped by DER minimal encoding).
static const char *s_ca_pem =
    "-----BEGIN CERTIFICATE-----\n"
    "MIIBdzCCAR2gAwIBAgIUC9EJL4ESUxySERIJ7JU0vqLI5NMwCgYIKoZIzj0EAwIw\n"
    "ETEPMA0GA1UEAwwGVGVzdENBMB4XDTI2MDgyOTIyMDExM1oXDTM2MDgyNjIyMDEx\n"
    "M1owETEPMA0GA1UEAwwGVGVzdENBMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE\n"
    "sYr0xLEWCBC5ifsqUBZX0KiVLd+KSEiePGMZZbqoVZnJ264Z/nbVAppcsG5CTwk5\n"
    "aOhaJtextivZeqYH5NzzIaNTMFEwHQYDVR0OBBYEFOwn161yMS8tLE10cDuAbpnq\n"
    "Kmo0MB8GA1UdIwQYMBaAFOwn161yMS8tLE10cDuAbpnqKmo0MA8GA1UdEwEB/wQF\n"
    "MAMBAf8wCgYIKoZIzj0EAwIDSAAwRQIgYm7VHDlQ6ugVRqqL2MqLIPhsKwgbWrGe\n"
    "8c6JSl2R/0oCIQDOTmlx/H+dMEc+tIusGvNdTTUBl42AcrQgFZOr4AoyJA==\n"
    "-----END CERTIFICATE-----\n";

static const char *s_cert_pem =
    "-----BEGIN CERTIFICATE-----\n"
    "MIIBaDCCAQ+gAwIBAgIUYrQaPOzECsG2sohP69qA94hrK8YwCgYIKoZIzj0EAwIw\n"
    "ETEPMA0GA1UEAwwGVGVzdENBMB4XDTI2MDgyOTIyMDExM1oXDTM2MDgyNjIyMDEx\n"
    "M1owFDESMBAGA1UEAwwJbG9jYWxob3N0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcD\n"
    "QgAEE2xSzQXuIzlt2+BCFlm2iogSAcRFduWlfznuvaf1ADYXlbOVR3JFnm5245vc\n"
    "daUor1jWSbUokdq3zbh39+6Y7qNCMEAwHQYDVR0OBBYEFHCs8gAsSVzS+tC7oYl0\n"
    "7rwaRZQjMB8GA1UdIwQYMBaAFOwn161yMS8tLE10cDuAbpnqKmo0MAoGCCqGSM49\n"
    "BAMCA0cAMEQCHz9ZZPhF2eHETOFeal586uKaNOyRjuajV8eBmLWNhLACIQDxhx/0\n"
    "00tn1TQMLzbgoeoCpfN/3LEAJ8UEE3lpfXskAw==\n"
    "-----END CERTIFICATE-----\n";

static const char *s_key_pem =
    "-----BEGIN EC PRIVATE KEY-----\n"
    "MHcCAQEEINZzLlSrkVssocsj1JcixpTN3nvOcWhD4vhVmYBbiuIUoAoGCCqGSM49\n"
    "AwEHoUQDQgAEE2xSzQXuIzlt2+BCFlm2iogSAcRFduWlfznuvaf1ADYXlbOVR3JF\n"
    "nm5245vcdaUor1jWSbUokdq3zbh39+6Y7g==\n"
    "-----END EC PRIVATE KEY-----\n";

static const char *s_url = "https://127.0.0.1:18443";
static int s_done = 0, s_ok = 0;

static void sfn(struct mg_connection *c, int ev, void *ev_data) {
  if (ev == MG_EV_ACCEPT) {
    struct mg_tls_opts opts;
    memset(&opts, 0, sizeof(opts));
    opts.cert = mg_str(s_cert_pem);
    opts.key = mg_str(s_key_pem);
    mg_tls_init(c, &opts);
  } else if (ev == MG_EV_HTTP_MSG) {
    mg_http_reply(c, 200, "", "hi");
  }
}

static void cfn(struct mg_connection *c, int ev, void *ev_data) {
  if (ev == MG_EV_CONNECT) {
    struct mg_tls_opts opts;
    memset(&opts, 0, sizeof(opts));
    opts.ca = mg_str(s_ca_pem);
    opts.name = mg_str("localhost");
    mg_tls_init(c, &opts);
  } else if (ev == MG_EV_TLS_HS) {
    mg_printf(c, "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n");
  } else if (ev == MG_EV_HTTP_MSG) {
    s_ok = 1;
    s_done = 1;
  } else if (ev == MG_EV_ERROR) {
    printf("client error: %s\n", (char *) ev_data);
    s_done = 1;
  }
}

int main(void) {
  struct mg_mgr mgr;
  int i;
  mg_log_set(MG_LL_DEBUG);
  mg_mgr_init(&mgr);
  if (mg_http_listen(&mgr, s_url, sfn, NULL) == NULL) {
    printf("FAIL: cannot listen\n");
    return 1;
  }
  mg_http_connect(&mgr, s_url, cfn, NULL);
  for (i = 0; i < 500 && !s_done; i++) mg_mgr_poll(&mgr, 10);
  mg_mgr_free(&mgr);
  printf(s_ok ? "OK: handshake completed\n" : "FAIL: handshake did not complete\n");
  return s_ok ? 0 : 1;
}
