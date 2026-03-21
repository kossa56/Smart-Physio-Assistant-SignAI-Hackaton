import serial
import csv
import sys
import time

# Konfiguracja
PORT       = 'COM3'
BAUDRATE   = 115200
OUTPUT_FILE = '../dane.csv'


def open_serial(port: str, baudrate: int) -> serial.Serial:
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"[OK] Połączono z {port} @ {baudrate} baud.")
        return ser
    except serial.SerialException as e:
        print(f"[BŁĄD] Nie można otworzyć portu {port}: {e}")
        sys.exit(1)


def open_csv(filepath: str) -> tuple[csv.writer, object]:
    f = open(filepath, 'w', newline='', buffering=1)  # buffering=1 = flush co linię
    writer = csv.writer(f)
    writer.writerow(['timestamp_ms', 'distance_mm', 'session_time_s', 'repetition_count'])
    f.flush()
    return writer, f


def parse_line(line: str) -> list[str] | None:
    """Zwraca listę 4 wartości lub None jeśli linia jest nieprawidłowa."""
    if not line or not line[0].isdigit():
        return None
    parts = line.split(',')
    if len(parts) != 4:
        return None
    return parts


def collect(ser: serial.Serial, writer: csv.writer, csvfile) -> None:
    print("Zbieranie danych... Wciśnij Ctrl+C, aby zakończyć.\n")
    rows_saved = 0
    try:
        while True:
            raw = ser.readline().decode('utf-8', errors='ignore').strip()
            parts = parse_line(raw)
            if parts:
                writer.writerow(parts)
                csvfile.flush()  # natychmiastowy zapis na dysk po każdym wierszu
                rows_saved += 1
                print(f"\r[{rows_saved:>5} próbek]  "
                      f"t={parts[0]} ms  dist={parts[1]} mm  "
                      f"rep={parts[3]}      ", end='', flush=True)
    except KeyboardInterrupt:
        print(f"\n\nZatrzymano. Zapisano {rows_saved} próbek → {OUTPUT_FILE}")


def main() -> None:
    ser    = open_serial(PORT, BAUDRATE)
    writer, csvfile = open_csv(OUTPUT_FILE)

    try:
        collect(ser, writer, csvfile)
    finally:
        csvfile.flush()
        csvfile.close()
        ser.close()
        print(f"Port i plik zamknięte.")


if __name__ == '__main__':
    main()