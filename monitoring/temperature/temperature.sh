#!/bin/sh
# Publica la temperatura de la instancia para node-exporter (textfile collector).
#
# 1) Si el hardware expone sensores (/sys/class/thermal o /sys/class/hwmon) se usa la lectura real
#    -> node_temperature_celsius{source="sensor"}
# 2) Las instancias EC2 virtualizadas normalmente NO exponen sensores térmicos al sistema
#    invitado; en ese caso se publica una estimación a partir del uso de CPU
#    -> node_temperature_celsius{source="estimado"}   (35 °C en reposo + 0.45 °C por cada % de CPU)

OUT_DIR=${OUT_DIR:-/textfile}
OUT="$OUT_DIR/temperature.prom"
INTERVAL=${INTERVAL:-15}
SYS=${SYS_PATH:-/host/sys}

PREV_TOTAL=0
PREV_IDLE=0
USAGE=0

update_cpu_usage() {
  # /proc/stat no está aislado por contenedor: refleja la CPU del host
  read -r _ user nice system idle iowait irq softirq steal _ < /proc/stat
  total=$((user + nice + system + idle + iowait + irq + softirq + steal))
  idle_all=$((idle + iowait))
  dt=$((total - PREV_TOTAL))
  di=$((idle_all - PREV_IDLE))
  PREV_TOTAL=$total
  PREV_IDLE=$idle_all
  if [ "$dt" -gt 0 ]; then USAGE=$(( (100 * (dt - di)) / dt )); else USAGE=0; fi
}

read_sensor() {
  sum=0
  n=0
  for f in "$SYS"/class/thermal/thermal_zone*/temp "$SYS"/class/hwmon/hwmon*/temp*_input; do
    [ -r "$f" ] || continue
    v=$(cat "$f" 2>/dev/null) || continue
    case "$v" in ''|*[!0-9]*) continue ;; esac
    [ "$v" -gt 0 ] || continue
    sum=$((sum + v))
    n=$((n + 1))
  done
  [ "$n" -gt 0 ] && awk -v s="$sum" -v n="$n" 'BEGIN { printf "%.1f", s / n / 1000 }'
}

mkdir -p "$OUT_DIR"
update_cpu_usage
echo "temperature-exporter: escribiendo $OUT cada ${INTERVAL}s"

while true; do
  sleep "$INTERVAL"
  update_cpu_usage
  temp=$(read_sensor)
  if [ -n "$temp" ]; then
    source="sensor"
  else
    source="estimado"
    temp=$(awk -v u="$USAGE" 'BEGIN { printf "%.1f", 35 + u * 0.45 }')
  fi
  cat > "$OUT.tmp" <<EOF
# HELP node_temperature_celsius Temperatura de la instancia en grados Celsius (source=sensor|estimado).
# TYPE node_temperature_celsius gauge
node_temperature_celsius{source="$source"} $temp
# HELP node_temperature_cpu_usage_percent Uso de CPU (%) usado para la estimación de temperatura.
# TYPE node_temperature_cpu_usage_percent gauge
node_temperature_cpu_usage_percent $USAGE
EOF
  mv "$OUT.tmp" "$OUT"
done
