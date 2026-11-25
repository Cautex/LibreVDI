"""Runs the LibreVDI self-test (``uds.plugins.librevdi.selfcheck``) – see ADR-0008.

  python -m librevdi_ext.selfcheck            # print all checks, exit 1 if one fails
  python -m librevdi_ext.selfcheck --quiet    # print only failures and the summary

LIBREVDI_SELFCHECK=warn turns failures into warnings (exit 0), e.g. to start a broker after an
OpenUDS update on purpose while a hook is being fixed. Default: strict.
"""

import os
import sys

import django


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    django.setup()  # loads the OpenUDS app and with it every LibreVDI plugin
    from uds.plugins.librevdi import selfcheck  # pylint: disable=import-outside-toplevel

    results = selfcheck.run()
    failed = [what for ok, what in results if not ok]
    for ok, what in results:
        if not ok or not quiet:
            print(f"librevdi: selfcheck {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    print(f"librevdi: selfcheck {len(results) - len(failed)}/{len(results)} ok", flush=True)
    if not failed:
        return 0
    if os.environ.get("LIBREVDI_SELFCHECK", "strict").lower() == "warn":
        print("librevdi: WARNING: selfcheck failures ignored (LIBREVDI_SELFCHECK=warn)", flush=True)
        return 0
    print("librevdi: ERROR: selfcheck failed – an OpenUDS change broke a LibreVDI extension (see ADR-0008)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
