#!/usr/bin/env python3
"""
Enrich ARP entries with vendor and device_type using scoring rules.
Inputs: cli_out/*/arp.csv, neighbors_{cdp,lldp}.csv, vlans.csv
Output: cli_out/_enriched/arp_device_types.csv
"""
import csv, glob, os, re, sys
from collections import defaultdict

OUI = {}
if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    with open(sys.argv[1]) as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#'): continue
            p = [x.strip() for x in line.split(',')]
            if len(p) >= 2:
                OUI[p[0].upper().replace('-',':')] = p[1]

mac_oui = lambda m: ':'.join(m.upper().replace('.', '').replace('-', ':')[i:i+2] for i in range(0,12,2))[:8]

TOKENS = {
    'ip_phone':    ['ip phone','telephone','sip','lldp-med','poly','polycom','cisco ip phone','avaya'],
    'camera':      ['axis','hikvision','hanwha','onvif','rtsp','camera'],
    'printer':     ['printer','hp inc','hewlett','brother','xerox','ricoh','kyocera','canon'],
    'wireless_ap': ['aironet','catalyst 9','meraki','aruba ap','ruckus','access point','ap-'],
    'switch':      ['cisco catalyst','nexus','switch'],
    'router':      ['asr','isr','router'],
}

VENDOR_HINTS = {
    'ip_phone':    ['POLY','POLYCOM','CISCO','AVAYA','YEALINK','MITEL'],
    'camera':      ['AXIS','HIKVISION','HANWHA','AVIGILON','DAHUA'],
    'printer':     ['HP','HEWLETT','BROTHER','XEROX','RICOH','KYOCERA','CANON'],
}

def classify(platform: str, vendor: str, in_voice_vlan: bool):
    s = (platform or '').lower()
    v = (vendor or '').lower()
    score, reasons, dtype = 0, [], 'unknown'

    for t, lst in VENDOR_HINTS.items():
        if any(x.lower() in v for x in lst):
            score += 25; reasons.append(f'vendor->{t}')
            if dtype == 'unknown': dtype = t

    for t, toks in TOKENS.items():
        if any(tok in s for tok in toks):
            score += 30; reasons.append(f'platform->{t}')
            if dtype == 'unknown' or t in ('ip_phone','camera','printer'):
                dtype = t if t != 'switch' else 'access_switch'

    if in_voice_vlan:
        score += 20; reasons.append('voice_vlan')
        if dtype == 'unknown': dtype = 'ip_phone'

    conf = 90 if score >= 70 else (60 if score >= 40 else 25)
    return dtype, conf, reasons

platform_by_local = defaultdict(str)
voice_members = set()

for devdir in glob.glob('cli_out/*'):
    if not os.path.isdir(devdir) or devdir.endswith('_enriched'): continue
    for nb in ('neighbors_lldp.csv','neighbors_cdp.csv'):
        p = os.path.join(devdir, nb)
        if os.path.exists(p):
            with open(p) as f:
                r = csv.DictReader(f)
                for row in r:
                    key = (os.path.basename(devdir), row.get('local_intf',''))
                    platform_by_local[key] = row.get('platform','')
    vb = os.path.join(devdir, 'vlans.csv')
    if os.path.exists(vb):
        with open(vb) as f:
            r = csv.DictReader(f)
            for row in r:
                name = (row.get('name') or '').lower()
                if 'voice' in name:
                    ports = (row.get('ports') or '')
                    for p in [x.strip() for x in ports.split(',') if x.strip()]:
                        voice_members.add((os.path.basename(devdir), p))

out_rows = []
for devdir in glob.glob('cli_out/*'):
    if not os.path.isdir(devdir) or devdir.endswith('_enriched'): continue
    arp_path = os.path.join(devdir, 'arp.csv')
    if not os.path.exists(arp_path): continue
    with open(arp_path) as f:
        r = csv.DictReader(f)
        for row in r:
            mac = row['mac'].lower().replace('.', '')
            mac_fmt = ':'.join(mac[i:i+2] for i in range(0,12,2))
            oui = mac_oui(mac_fmt)
            vendor = OUI.get(oui, '')
            local = (os.path.basename(devdir), row.get('iface',''))
            platform = platform_by_local.get(local, '')
            in_voice = local in voice_members
            dtype, conf, reasons = classify(platform, vendor, in_voice)
            out_rows.append({
                'switch_dir': os.path.basename(devdir),
                'ip': row['ip'], 'mac': mac_fmt, 'vendor': vendor,
                'platform_hint': platform, 'device_type': dtype,
                'confidence': conf, 'reasons': '|'.join(reasons)
            })

os.makedirs('cli_out/_enriched', exist_ok=True)
with open('cli_out/_enriched/arp_device_types.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=['switch_dir','ip','mac','vendor','platform_hint','device_type','confidence','reasons'])
    w.writeheader(); w.writerows(out_rows)
print(f"wrote {len(out_rows)} rows -> cli_out/_enriched/arp_device_types.csv")