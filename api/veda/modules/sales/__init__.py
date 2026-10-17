"""Sales & Customer Acquisition Experience (SCA, decision log 48).

A read-only sales layer over the records the other modules own: the lead (CRM), the budget estimate, the measurement
visit, the quotation, the customer proposal link and the project. It derives a sales stage from that evidence, reports
the acquisition funnel, counts the site's anonymous funnel beacons and serves a synthetic customer-journey demo. It
never changes a lead's status, never prices anything and holds no customer data of its own.
"""
