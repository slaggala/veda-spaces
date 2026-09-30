"""Release floor identity of this image (FC-12, runbook §2.1).

RELEASE_SEQUENCE increases by one for every release that ships a security fix which must never be undone by a
deployment of an older image. deploy.sh refuses, in every mode, an image whose sequence is below its
RELEASE_FLOOR or that cannot report one. 1 = 9236aa3 (IR-01 open), 2 = 2f6b59a (RR-02/RR-03 open),
3 = the final merge-blocker remediation and later.
"""

RELEASE_SEQUENCE = 3
