#!/usr/bin/env python3
import os, json, time, csv, yaml, re
from netmiko import ConnectHandler

def ensure_dir(p): os.makedirs(p, exist_ok=True)

COMMANDS = {
  "version":              "show version | inc (uptime|Version)",
  "ip_int_brief":         "show ip interface brief",
  "vlan_brief":           "show vlan brief",
  "switchport":           "show interfaces switchport",
  "mac_table":            "show mac address-table dynamic",
  "arp":                  "show ip arp",
  "route":                "show ip route",
  "route_all":            "show ip route vrf *",
  "cdp_detail":           "show cdp neighbors detail",
  "lldp_detail":          "show lldp neighbors detail"
}

def run_cmd(conn, cmd, use_textfsm=True):
  try:
    return conn.send_command(cmd, use_textfsm=use_textfsm)
  except Exception:
    return conn.send_command(cmd, use_textfsm=False)

# Fallback parsers for common tables
import re

def normalize_vlan(obj):
  if isinstance(obj, list): return obj
  rows = []
  for line in str(obj).splitlines():
    m = re.match(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(.*)$", line)
    if m and m.group(1).isdigit():
      rows.append({"vlan_id": m.group(1), "name": m.group(2), "status": m.group(3), "ports": m.group(4)})
  return rows

def normalize_mac(obj):
  if isinstance(obj, list): return obj
  rows = []
  for line in str(obj).splitlines():
    m = re.match(r"^\s*(\d+)\s+([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+\S+\s+(\S+)$", line, re.I)
    if m:
      rows.append({"vlan": m.group(1), "mac": m.group(2).lower(), "port": m.group(3)})
  return rows

def normalize_arp(obj):
  if isinstance(obj, list): return obj
  rows = []
  for line in str(obj).splitlines():
    m = re.match(r"^Internet\s+(\d+\.\d+\.\d+\.\d+)\s+\d+\s+([0-9a-f\.]{14})\s+\S+\s+(\S+)$", line, re.I)
    if m:
      rows.append({"ip": m.group(1), "mac": m.group(2).lower(), "iface": m.group(3)})
  return rows

def main():
  with open("devices.yaml") as f: spec = yaml.safe_load(f)
  auth = spec["auth"]; opts = spec.get("options", {})
  outdir = "cli_out"; ensure_dir(outdir)
  summary = []
  for dev in spec["devices"]:
    device_dir = os.path.join(outdir, f"{dev['name']}_{dev['host']}"); ensure_dir(device_dir)
    try:
      conn = ConnectHandler(host=dev['host'], device_type=dev.get('device_type','cisco_ios'),
                            username=auth['username'], password=auth['password'],
                            global_cmd_timeout=opts.get('global_cmd_timeout', 120))
      use_tf = bool(opts.get('use_textfsm', True))
      out = {k: run_cmd(conn, c, use_textfsm=use_tf) for k,c in COMMANDS.items()}
      # normalize key tables
      vlans = normalize_vlan(out["vlan_brief"]) 
      macs  = normalize_mac(out["mac_table"]) 
      arp   = normalize_arp(out["arp"]) 
      # write CSVs
      def to_csv(path, rows, headers):
        if not rows: return
        with open(path, "w", newline="") as f:
          import csv
          w = csv.DictWriter(f, fieldnames=headers)
          w.writeheader(); w.writerows(rows)
      to_csv(os.path.join(device_dir, "vlans.csv"), vlans, ["vlan_id","name","status","ports"])
      to_csv(os.path.join(device_dir, "mac_table.csv"), macs, ["vlan","mac","port"])
      to_csv(os.path.join(device_dir, "arp.csv"), arp, ["ip","mac","iface"])
      # neighbors (TextFSM usually parses these)
      for key, fname in [("cdp_detail","neighbors_cdp.csv"),("lldp_detail","neighbors_lldp.csv")]:
        val = out[key]
        if isinstance(val, list) and val and isinstance(val[0], dict):
          headers = sorted({k for d in val for k in d.keys()})
          to_csv(os.path.join(device_dir, fname), val, headers)
        else:
          with open(os.path.join(device_dir, fname.replace('.csv','.txt')), 'w') as f: f.write(str(val))
      with open(os.path.join(device_dir, "raw.json"), "w") as f: json.dump(out, f, indent=2)
      conn.disconnect()
      summary.append({"device": dev['name'], "host": dev['host'], "status": "ok"})
    except Exception as e:
      summary.append({"device": dev['name'], "host": dev['host'], "status": "error", "error": str(e)})
  with open(os.path.join(outdir, "_summary.json"), 'w') as f: json.dump(summary, f, indent=2)

if __name__ == "__main__":
  main()