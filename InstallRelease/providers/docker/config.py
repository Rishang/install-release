from __future__ import annotations

# Shell wrapper written to dest/<toolname>.
# {ref}  — image CLI ref (e.g. alpine:latest)
# {args} — "$@" when image has ENTRYPOINT; "toolname "$@"" when it does not
# ${{PWD}} becomes ${PWD} after .format() — intentional shell variable reference.
WRAPPER_TEMPLATE = """\
#!/bin/sh
termflag=$([ -t 0 ] && echo -n "-t")
docker run --rm -i $termflag -v "${{PWD}}:/tmp/cmd" -w /tmp/cmd {ref} {args}
"""
