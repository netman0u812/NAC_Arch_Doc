README – NAC SSH Collectors & Device‑Type Enrichment Pipeline
=============================================================

This package provides the SSH‑based network discovery collectors and 
classification enricher used with the Vendor‑Neutral MAB‑only NAC Architecture. 
These tools gather ARP/MAC/VLAN/neighbor data from switches via read‑only SSH, 
normalize it into CSV/JSON, and apply a scoring model to produce actionable 
device_type + confidence labels that can drive Forescout MAB policy decisions.

-----------------------------------------------------------------
CONTENTS
-----------------------------------------------------------------
cli_collect.sh            Lightweight Bash collector (Cisco IOS/IOS‑XE)
nac_cli_collect.py        Full‑featured Python collector (Netmiko + TextFSM)
devices.csv               Device inventory template
show_cmds.txt             Switch commands gathered during collection
classify_from_cli.py      Python enricher to classify devices
cli_out/                  Output directory created by collectors

-----------------------------------------------------------------
1) QUICKSTART
-----------------------------------------------------------------
A. Prepare (Python collector only)
   pip install netmiko textfsm ntc-templates pyyaml pandas
   export NTC_TEMPLATES_DIR=/path/to/ntc-templates

   Ensure a read‑only SSH account that can run the commands in show_cmds.txt.

B. Populate devices.csv
   name,mgmt_ip,username,port
   acc-sw1,10.20.1.11,nac_ro,22
   acc-sw2,10.20.1.12,nac_ro,22

C. (Optional) Edit show_cmds.txt
   Includes: show vlan brief; show mac address-table dynamic; show ip arp;
             show lldp neighbors detail; show cdp neighbors detail; etc.

D. Run a collection

   Option A – Bash (fast, minimal deps):
     ./cli_collect.sh devices.csv show_cmds.txt

   Option B – Python (structured output):
     python3 nac_cli_collect.py

   Outputs appear under:
     cli_out/<switch_name_ip>/

E. Run device‑type enrichment

   1) (Optional) Prepare an OUI vendor file:
        AA:BB:CC,Vendor Name
        00:1B:78,HP Inc.
        3C:5A:B4,Apple Inc.
   2) Execute:
        python3 classify_from_cli.py /path/to/oui.csv

   Result:
        cli_out/_enriched/arp_device_types.csv

-----------------------------------------------------------------
2) OUTPUTS
-----------------------------------------------------------------
Per-switch directory (from collectors):
  vlans.csv               VLAN ID, name, status, ports
  mac_table.csv           VLAN, MAC, access port
  arp.csv                 IP, MAC, SVI interface
  neighbors_lldp.csv      LLDP neighbor data (if parsed)
  neighbors_cdp.csv      CDP neighbor data (if parsed)
  raw.json                Raw outputs for debugging/forensics

Global:
  cli_out/_summary.json                     Collection success/failure summary
  cli_out/_enriched/arp_device_types.csv    Enriched classification output

-----------------------------------------------------------------
3) ENRICHER LOGIC (SUMMARY)
-----------------------------------------------------------------
Signals (example weights):
  +25  Vendor OUI matches class vendor (HP/Xerox → printer; Axis/Hanwha → camera)
  +30  LLDP/CDP platform tokens (“IP Phone”, “ONVIF”, “AP”)
  +20  Voice‑VLAN membership
  +10  Historical placement in voice/camera VLAN

Confidence buckets:
  ≥70        HIGH confidence → auto‑enforce
  40–69      MEDIUM confidence → restricted/remediation
  <40        LOW confidence → quarantine/manual review

Device taxonomy:
  ip_phone, camera, printer, wireless_ap, access_switch, router,
  ot_device, workstation_candidate, unknown

-----------------------------------------------------------------
4) POLICY MAPPING (AT A GLANCE)
-----------------------------------------------------------------
  ip_phone              → Voice/Phone VLAN + ACL‑VOICE
  camera                → Video/CCTV VLAN + ACL‑CAMERA
  printer               → Print VLAN + ACL‑PRINT
  wireless_ap           → Infra/AP VLAN + ACL‑AP
  access_switch/router  → Infra VLAN + ACL‑INFRA
  ot_device             → OT VLAN + ACL‑OT
  workstation_candidate → Remediation + ACL‑REMEDIATION
  unknown               → Quarantine + ACL‑QUAR

-----------------------------------------------------------------
5) OPERATIONAL NOTES
-----------------------------------------------------------------
- Collectors are read‑only (no config mode) and safe for production windows.
- Schedule via cron/systemd for recurring discovery.
- Feed enriched CSV into Forescout, SIEM, and IPAM/CMDB for accuracy.
- Review MEDIUM‑confidence devices during pilot before strict enforcement.

-----------------------------------------------------------------
6) TROUBLESHOOTING
-----------------------------------------------------------------
SSH permission denied:
  • Ensure the collector account exists and is allowed to run show commands.

Missing neighbors CSV:
  • LLDP/CDP may be disabled—enable on switches or rely on OUI‑only logic.

TextFSM parsing errors (Python collector):
  • Verify NTC_TEMPLATES_DIR points to a valid ntc‑templates directory.

-----------------------------------------------------------------
7) OWNERSHIP (GOVERNANCE SNAPSHOT)
-----------------------------------------------------------------
- NetSec Engineering     → Platform operations
- Network Operations     → First‑line triage (tickets, unknown/quarantine)
- Endpoint Engineering   → SecureConnector lifecycle
- App/OT Owners          → IoT inventories & functional baselines

-----------------------------------------------------------------
8) REVISION HISTORY
-----------------------------------------------------------------
- 2026‑02‑06  Initial README quickstart for NAC SSH collectors + enricher