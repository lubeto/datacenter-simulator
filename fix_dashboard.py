import re

with open('/app/frontend/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Fix 1: SSL days remaining
old_ssl = "const days = c.days_until_expiry ?? c.days_remaining ?? '?';"
new_ssl = "const days = c.days_until_expiry ?? c.days_remaining ?? (c.expires_at ? Math.round((new Date(c.expires_at) - new Date()) / 86400000) : '?');"
if old_ssl in c:
    c = c.replace(old_ssl, new_ssl)
    print("SSL fix OK")
else:
    print("SSL: already applied or not found")

# Fix 2: SST handler - replace with regex
new_sst = '''function handleSSTAlert(data) {
  var alerts = data.alerts || [];
  if (!alerts.length) return;
  var units = {temperature:'C', humidity:'%', smoke:'ppm', ups:'V', power:'kW', access_control:''};
  var ranges = {temperature:{min:18,max:35}, humidity:{min:30,max:70}, smoke:{min:0,max:10}};
  var mapped = alerts.map(function(s) {
    var val = s.temperature_c !== undefined ? s.temperature_c
            : s.humidity_pct !== undefined ? s.humidity_pct
            : s.smoke_ppm !== undefined ? s.smoke_ppm
            : s.value !== undefined ? s.value : '--';
    var r = ranges[s.type] || {min:0, max:100};
    return {id:s.sensor_id, name:s.sensor_name||s.sensor_id, zone:s.zone||'',
      type:s.type||'sensor',
      status:s.alert_level==='critical'?'critical':s.alert_level==='warning'?'warning':'ok',
      value:val, unit:units[s.type]||'', normal_min:r.min, normal_max:r.max};
  });
  updateSST(mapped);
  var crit = mapped.filter(function(s){ return s.status==='critical'; });
  var warn = mapped.filter(function(s){ return s.status==='warning'; });
  if (crit.length) notify('SST Critico', crit[0].name+': fuera de rango', 'crit');
  else if (warn.length) notify('SST Alerta', String(warn.length)+' sensores con advertencia', 'warn');
}'''

pattern = r'function handleSSTAlert\(data\)\s*\{[^}]*\}'
if re.search(pattern, c):
    c = re.sub(pattern, new_sst, c)
    print("SST handler OK")
else:
    print("SST: pattern not found, trying longer match...")
    pattern2 = r'function handleSSTAlert\(data\)\s*\{.*?\n\}'
    if re.search(pattern2, c, re.DOTALL):
        c = re.sub(pattern2, new_sst, c, flags=re.DOTALL)
        print("SST handler OK (fallback)")
    else:
        idx = c.find('function handleSSTAlert')
        print(f"Found at idx={idx}: {repr(c[idx:idx+200])}")

with open('/app/frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
print("Done.")
