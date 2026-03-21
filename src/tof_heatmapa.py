import serial
import numpy as np
import matplotlib.pyplot as plt

PORT = "COM3"
BAUD = 115200
GRID_SIZE = 8

ser = serial.Serial(PORT, BAUD, timeout=0.1)  # Krótszy timeout

plt.ion()
fig, ax = plt.subplots()

data = np.zeros((GRID_SIZE, GRID_SIZE))
im = ax.imshow(data, cmap='plasma', vmin=0, vmax=2000)

ax.set_xticks([])
ax.set_yticks([])

# Przygotuj tablicę tekstów
texts = np.empty((GRID_SIZE, GRID_SIZE), dtype=object)
for i in range(GRID_SIZE):
    for j in range(GRID_SIZE):
        texts[i, j] = ax.text(j, i, "0", ha="center", va="center", fontsize=8)

buffer = bytearray()  # Użyj bytearray zamiast string
print("Start...")

try:
    while True:
        # Czytaj wszystkie dostępne dane naraz
        buffer.extend(ser.read(ser.in_waiting or 1))
        
        # Szukaj linii zakończonej \n
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            
            # Filtruj tylko cyfry i spacje
            clean_line = bytearray()
            for c in line:
                if 48 <= c <= 57 or c == 32:  # cyfry lub spacja
                    clean_line.append(c)
            
            if clean_line:
                # Konwertuj bezpośrednio na liczby
                values = list(map(int, clean_line.split()))
                if values:
                    # Bierzemy tylko co drugi element (distance)
                    distances = values[::2]
                    
                    if len(distances) >= 64:
                        frame = distances[:64]
                        data = np.array(frame).reshape((GRID_SIZE, GRID_SIZE))
                        
                        im.set_data(data)
                        
                        # Aktualizuj teksty - tylko gdy wartość się zmieniła
                        for i in range(GRID_SIZE):
                            for j in range(GRID_SIZE):
                                val = data[i, j]
                                texts[i, j].set_text(str(int(val)))
                                texts[i, j].set_color("black" if val > 1000 else "white")
                        
                        ax.set_title("VL53L8A1 Heatmap 8x8", fontsize=14)
                        fig.canvas.draw_idle()
                        plt.pause(0.001)  # Minimalne opóźnienie

except KeyboardInterrupt:
    print("Stop")
finally:
    ser.close()
    plt.close(fig)