import serial
import csv
import sys
import time
import matplotlib.pyplot as plt
import pandas as pd

# Konfiguracja
PORT = 'COM3'
BAUDRATE = 115200
OUTPUT_FILE = 'dane.csv'

# Otwórz port
try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    print(f"Połączono z {PORT} przy {BAUDRATE} baud.")
except serial.SerialException as e:
    print(f"Błąd otwarcia portu {PORT}: {e}")
    sys.exit(1)

# Otwórz plik CSV i zapisz nagłówek
with open(OUTPUT_FILE, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['timestamp_ms', 'distance_mm', 'session_time_s', 'repetition_count'])

    print("Zbieranie danych... Wciśnij Ctrl+C, aby zakończyć.")
    try:
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                # Spodziewamy się 4 kolumn oddzielonych przecinkami
                if line[0].isdigit():
                    parts = line.split(',')
                    if len(parts) == 4:
                        writer.writerow(parts)
                        print(f"Zapisano: {line}")
                    else:
                        print(f"Nieprawidłowa liczba kolumn: {line}")
                else:
                    # Pomijamy inne komunikaty (np. logi startowe)
                    pass
    except KeyboardInterrupt:
        print("\nZatrzymano przez użytkownika.")
    finally:
        ser.close()
        print(f"Dane zapisane w pliku {OUTPUT_FILE}")

# Opcjonalnie – od razu wyświetl prosty wykres
try:
    df = pd.read_csv(OUTPUT_FILE)
    plt.plot(df['session_time_s'], df['distance_mm'])
    plt.xlabel('Czas sesji (s)')
    plt.ylabel('Odległość (mm)')
    plt.title('Przebieg ćwiczenia')
    plt.grid()
    plt.show()
except Exception as e:
    print(f"Nie udało się wyświetlić wykresu: {e}")